"""Sample data for hockey: a made-up rec league and one function that writes a believable game sheet.

`scripts/make_sample.py` does the rest (players, schedule, outcomes) with a fixed seed. Nothing here looks like a
real league: the league is "Northside Old-Timers Hockey" (the made-up league of BRIEF.md and the design system),
the teams are the design system's six and the players are made-up "First L." names with jersey numbers.

`sheet()` plays a game goal by goal. It draws each team's goals (mostly two to five a side), puts them in periods
and times, picks scorers weighted toward a few top players, gives most goals one or two assists, and writes the
penalties the goals ask for (a power-play goal follows a penalty to the other team in the same period, a
short-handed one a penalty to its own) beside a handful of ordinary minors and the odd major. The game ends the
way `game.outcome` asks, bent to what the league's rules allow:

* a regular-season game level after the last period is a tie with `overtime: none` (the default), a scoreless or
  decided overtime with `overtime` or `shootout`, and a shootout with `shootout_only` (or after a scoreless
  overtime with `shootout`);
* a playoff game never ends level: it goes to sudden-death overtime (now and then a second one, `OT2`), or to
  overtime and a shootout with `playoff_overtime: shootout`; some playoff wins are overtime wins.

Over a season it writes shutouts, power-play, short-handed and empty-net goals, a penalty shot now and then, a
bench penalty, a game with two goalies for a team, a spare in net when the regular goalie did not dress (or a
skater, when no spare came), and a lopsided game stopped after two periods (the volunteer's note says why; the
sample's notes are the shared random ones, so this game shows an empty third period). Which game is which is
picked from the game id, so it is stable. With `goalie_shots: recorded` every goalie row carries its shots.
Like every function of a sport it is pure: the same arguments give the same sheet, and it changes nothing it is
given.
"""
from __future__ import annotations

import zlib

from scripts.core.model import SampleGame, SportContext

LEAGUE_NAME = "Northside Old-Timers Hockey"
TEAMS = [("blades", "Blades", "BLA"), ("wolves", "Wolves", "WOL"), ("lumberjacks", "Lumberjacks", "LUM"),
         ("ice-dogs", "Ice Dogs", "ICE"), ("grey-owls", "Grey Owls", "OWL"), ("huskies", "Huskies", "HUS")]
PLAYERS_PER_TEAM = 12                                  # a goalie and eleven skaters
POSITIONS = ["goalie"]                                 # the first player of each team is its goalie
SURFACES = ["1", "2", "1"]                             # Pad 1, Pad 2, Pad 1
TIMES = ["20:00", "20:00", "21:15"]                    # the early game on each pad, then the late one on Pad 1
NOTES = ["Started ten minutes late: the ice was being resurfaced.", "Third period played with running time.",
         "A broken pane of glass held the game up for ten minutes."]

SIDES = ("home", "away")
SUB_NAMES = ["Hugo V.", "Ines R.", "Jory K.", "Kemal D."]    # a spare written in by hand on a draft: a name, no player id
GOAL_WEIGHTS = [3, 9, 18, 22, 20, 13, 8, 4, 3]       # a team's goals in a game: 0 to 8
LEVEL_WEIGHTS = [3, 31, 36, 20, 10]                    # each team's goals in a game level after the last period
PERIOD_WEIGHTS = [30, 32, 38]                          # the share of goals by period (the last one gets a few more)
ASSIST_WEIGHTS = [15, 40, 45]                          # a goal with no assist, one or two
PENALTY_COUNTS = ([2, 3, 4, 5, 6], [15, 25, 28, 18, 14])
INFRACTIONS = ["Tripping", "Hooking", "Slashing", "Holding", "Interference", "Body contact", "High sticking"]
MAJORS = ["Fighting", "Boarding", "Roughing"]
BENCH_INFRACTIONS = ["Too many players", "Delay of game"]
PP_CHANCE, SH_CHANCE = 0.17, 0.04                      # a goal in the periods (not an empty-net one) on a power play / short-handed
EN_CHANCE = 0.4                                        # a two-goal win, its last goal late in the last period: empty net
OT_GOAL_CHANCE = {"overtime": 0.65, "shootout": 0.55, "playoff_shootout": 0.6}
OT2_CHANCE = 0.12                                      # a sudden-death playoff overtime that needs a second period
SAVE_PCT = 0.9                                         # when shots are recorded
# Which games are special is picked from the game id (changing a salt moves them; tests/test_hockey_sample.py checks
# that each season has every one).
PLAYOFF_OT_EVERY, PLAYOFF_OT_SALT = 3, "o5"            # one playoff win in three went to overtime
CUT_SHORT_EVERY, CUT_SHORT_SALT = 13, "c1"             # one regular-season game in thirteen is stopped after two periods
BENCH_EVERY, BENCH_SALT = 15, "b2"                     # a bench penalty
SHOT_EVERY, SHOT_SALT = 23, "p3"                       # a goal on a penalty shot
TWO_GOALIES_EVERY, TWO_GOALIES_SALT = 11, "g4"         # a team that used two goalies (picked per side)
GOALIE_FOUND = 0.75                                    # the regular goalie left off the draw comes after all
MAX_TRIES = 400


# ------------------------------------------------------------------ the sheet

def sheet(rng, game: SampleGame, ctx: SportContext) -> dict:
    """A hockey sheet that passes check() and ends the way `game.outcome` asks (bent to the league's rules)."""
    opts = _Options(ctx)
    plan = _plan(rng, game, ctx, opts)
    dressed = {side: _dressed(rng, game, ctx, side) for side in SIDES}
    nums, roster_rows = _roster(dressed, ctx)
    nets = {side: _goalies_in_net(game, ctx, side, dressed[side]) for side in SIDES}
    pool = {side: [p for p in dressed[side] if p not in nets[side]] for side in SIDES}

    goals = _goals(rng, game, plan, opts, pool, nums)
    penalties = _penalties(rng, game, plan, opts, pool, nums, goals)
    _clock(goals, penalties, opts)
    for g in goals:
        g["num"], g["assist_nums"] = nums[g["side"]][g["scorer"]], [nums[g["side"]][p] for p in g["assists"]]
    for p in penalties:
        p["num"] = "bench" if p["player"] is None else nums[p["side"]][p["player"]]
        p["served_num"] = None if p["served"] is None else nums[p["side"]][p["served"]]
    if ctx.folder == "drafts":
        _name_one(game, roster_rows, pool, nums)

    out: dict = {"roster": roster_rows}
    out["goals"] = [_goal_row(g) for g in goals]
    out["penalties"] = [_penalty_row(p) for p in penalties]
    out["goalies"] = {side: _goalie_rows(rng, game, opts, side, nets[side], nums[side], goals, plan) for side in SIDES}
    if plan["so"]:
        out["shootout"] = _shootout(rng, opts, plan, pool, nums)
    out["score"] = _score(plan, goals, opts)
    return out


class _Options:
    """The league's options this sheet depends on, with the sport's defaults."""

    def __init__(self, ctx: SportContext):
        o = ctx.options
        self.periods = _int(o.get("periods"), 3)
        self.period_secs = 60 * _int(o.get("period_minutes"), 15)
        self.ot_secs = 60 * _int(o.get("overtime_minutes"), 5)
        self.rounds = _int(o.get("shootout_rounds"), 3)
        self.remaining = o.get("clock", "elapsed") == "remaining"
        self.shots = o.get("goalie_shots", "none") == "recorded"
        self.cap = _int(o.get("goal_cap"), 0)
        self.playoff = ctx.game_type != "regular"
        mode = o.get("playoff_overtime", "sudden_death") if self.playoff else o.get("overtime", "none")
        if self.playoff:
            self.ot_rule, self.so_rule = True, mode == "shootout"
        else:
            self.ot_rule, self.so_rule = mode in ("overtime", "shootout"), mode in ("shootout", "shootout_only")
        self.mode = mode


# ------------------------------------------------------------------ how the game ends

def _plan(rng, game: SampleGame, ctx: SportContext, o: _Options) -> dict:
    """{"reg": goals per side in the periods, "ot": None (no overtime) or {"side": scorer or None, "period": "OT"|"OT2"},
    "so": None or the shootout winner, "cut": a game stopped after two periods}."""
    outcome = game.outcome
    winner = outcome[4:] if outcome.startswith("win_") else None
    if o.playoff and winner and zlib.crc32(f"{PLAYOFF_OT_SALT}:{game.game_id}".encode()) % PLAYOFF_OT_EVERY == 0:
        outcome = "ot"                                   # a playoff game that went to overtime: the winner stays
    if o.playoff and outcome == "tie":
        outcome = "ot"
    level = outcome in ("tie", "ot")
    if outcome == "ot" and not o.playoff and not (o.ot_rule or o.so_rule):
        outcome = "tie"                                  # no overtime in this league: level stays level
    plan = {"reg": None, "ot": None, "so": None, "cut": False}
    if not level:
        cut = (not o.playoff and o.periods >= 3 and
               zlib.crc32(f"{CUT_SHORT_SALT}:{game.game_id}".encode()) % CUT_SHORT_EVERY == 0)
        plan["cut"] = cut
        plan["reg"] = _unlevel(rng, winner or rng.choice(SIDES), cut)
        return plan
    k = rng.choices(range(len(LEVEL_WEIGHTS)), LEVEL_WEIGHTS)[0]
    plan["reg"] = {"home": k, "away": k}
    winner = winner or rng.choice(SIDES)
    if o.ot_rule:
        if o.playoff and not o.so_rule:
            chance = 1.0
        else:
            chance = OT_GOAL_CHANCE["playoff_shootout" if o.playoff else o.mode]
        if rng.random() < chance:
            plan["ot"] = {"side": winner, "period": "OT2" if (o.playoff and not o.so_rule and rng.random() < OT2_CHANCE) else "OT"}
            return plan
        plan["ot"] = {"side": None, "period": "OT"}      # a scoreless overtime
    if o.so_rule:
        plan["so"] = winner
    return plan


def _unlevel(rng, winner: str, cut: bool) -> dict:
    """Goals in the periods for a game with a winner."""
    for _ in range(MAX_TRIES):
        if cut:                                          # a mercy-rule game: one team far ahead after two periods
            won, lost = rng.choice([6, 7, 8, 9]), rng.choice([0, 1, 1, 2])
        else:
            won, lost = (rng.choices(range(len(GOAL_WEIGHTS)), GOAL_WEIGHTS)[0] for _ in range(2))
        if won > lost:
            return {winner: won, ("away" if winner == "home" else "home"): lost}
    raise RuntimeError("could not draw goals for a hockey game")


# ------------------------------------------------------------------ the roster and who is in net

def _dressed(rng, game: SampleGame, ctx: SportContext, side: str) -> list[str]:
    """Who is on the sheet: the players make_sample drew, and the team's own goalie too when he was left out and no
    spare came (a team nearly always finds its goalie; one time in four a skater goes in net instead)."""
    ids = list(game.players.get(side, []))
    team = ctx.sides[side]
    own = [p for p, who in ctx.players.items() if who.team == team and who.position == "goalie"]
    spare = any(ctx.players[p].team != team or ctx.players[p].sub for p in ids)
    if own and own[0] not in ids and not spare and rng.random() < GOALIE_FOUND:
        ids.insert(0, own[0])
    return ids


def _roster(dressed: dict, ctx: SportContext):
    """Jersey numbers {side: {player id: number}} (a player with none gets a free one) and the roster rows."""
    nums, rows = {}, {}
    for side in SIDES:
        ids = dressed[side]
        taken = {ctx.players[p].number for p in ids if ctx.players[p].number is not None}
        nums[side], rows[side] = {}, []
        for p in ids:
            number = ctx.players[p].number
            if number is None:                           # a spare, or a player with no number in players.yml
                number = next(str(n) for n in range(99, 0, -1) if str(n) not in taken)
                taken.add(number)
            nums[side][p] = _jersey(number)
            rows[side].append({"player": p, "num": nums[side][p]})
    return nums, rows


def _goalies_in_net(game: SampleGame, ctx: SportContext, side: str, ids: list[str]) -> list[str]:
    """The goalie who started, then (some games) a second one who finished: the team's own goalie when he dressed,
    else a spare, else a skater."""
    team = ctx.sides[side]
    own = [p for p in ids if ctx.players[p].team == team and ctx.players[p].position == "goalie"]
    spares = [p for p in ids if ctx.players[p].team != team or ctx.players[p].sub]
    skaters = [p for p in ids if p not in own and p not in spares]
    first = own[0] if own else (spares[0] if spares else skaters[len(skaters) // 2])
    net = [first]
    if len(ids) >= 6 and zlib.crc32(f"{TWO_GOALIES_SALT}:{game.game_id}:{side}".encode()) % TWO_GOALIES_EVERY == 0:
        others = [p for p in (spares + skaters) if p != first]
        net.append(others[-1])                           # relief from the back of the roster: a spare or a skater
    return net


def _name_one(game, rows, pool, nums) -> None:
    """On a draft, one skater of one side is written in by name with no player id yet."""
    side = SIDES[zlib.crc32(game.game_id.encode()) % 2]
    skaters = pool[side]
    if len(skaters) < 2:
        return
    who = skaters[zlib.crc32(game.game_id.encode()) % len(skaters)]
    name = SUB_NAMES[zlib.crc32(game.game_id.encode()) % len(SUB_NAMES)]
    rows[side] = [{"name": name, "num": r["num"]} if r["player"] == who else r for r in rows[side]]


# ------------------------------------------------------------------ goals

def _goals(rng, game, plan, o: _Options, pool, nums) -> list[dict]:
    """Every goal of the game as {period, secs, side, scorer, assists, mark, en, ps}, in time order."""
    last = o.periods - 1 if plan["cut"] else o.periods
    slots: dict[tuple, set] = {}
    goals = []
    for side in SIDES:
        for _ in range(plan["reg"][side]):
            period = rng.choices(range(1, last + 1), PERIOD_WEIGHTS[:last] if last <= 3 else [1] * last)[0]
            goals.append({"period": period, "secs": _free_time(rng, slots, period, o.period_secs), "side": side})
    if plan["ot"] and plan["ot"]["side"]:
        period = plan["ot"]["period"]
        goals.append({"period": period, "secs": _free_time(rng, slots, period, o.ot_secs), "side": plan["ot"]["side"]})
    goals.sort(key=lambda g: (_order(g["period"], o), g["secs"]))

    scored = {side: {} for side in SIDES}
    for g in goals:
        side = g["side"]
        skaters = [p for p in pool[side] if not o.cap or scored[side].get(p, 0) < o.cap] or pool[side]
        weights = [1 / (i + 1) ** 0.9 for i in range(len(skaters))]
        g["scorer"] = rng.choices(skaters, weights)[0]
        scored[side][g["scorer"]] = scored[side].get(g["scorer"], 0) + 1
        others = [p for p in pool[side] if p != g["scorer"]]
        count = rng.choices([0, 1, 2], ASSIST_WEIGHTS)[0]
        picks = []
        for _ in range(min(count, len(others))):
            options = [p for p in others if p not in picks]
            picks.append(rng.choices(options, [1 / (others.index(p) + 1) ** 0.7 for p in options])[0])
        g["assists"], g["mark"], g["en"], g["ps"] = picks, None, False, False

    reg_goals = [g for g in goals if g["period"] in range(1, o.periods + 1)]
    _empty_net(rng, goals, plan, o)
    for g in reg_goals:
        if g["en"]:
            continue
        roll = rng.random()
        g["mark"] = "PP" if roll < PP_CHANCE else ("SH" if roll < PP_CHANCE + SH_CHANCE else None)
    if reg_goals and zlib.crc32(f"{SHOT_SALT}:{game.game_id}".encode()) % SHOT_EVERY == 0:
        g = rng.choice([g for g in reg_goals if not g["en"]] or reg_goals)
        g["ps"], g["mark"], g["assists"] = True, None, []
    return goals


def _empty_net(rng, goals, plan, o: _Options) -> None:
    """A two-goal win whose last goal came late in the last period: sometimes into an empty net."""
    if plan["ot"] or plan["so"] or plan["cut"]:
        return
    final = {s: sum(1 for g in goals if g["side"] == s) for s in SIDES}
    won = max(final, key=final.get)
    if final[won] - min(final.values()) < 2:
        return
    mine = [g for g in goals if g["side"] == won]
    g = mine[-1]
    if g["period"] == o.periods and g["secs"] >= o.period_secs - 4 * 60 and rng.random() < EN_CHANCE:
        g["en"] = True


def _free_time(rng, slots, period, length: int) -> int:
    """A second in the period nobody else used (so times never tie), kept away from both ends."""
    used = slots.setdefault(period, set())
    for _ in range(MAX_TRIES):
        secs = rng.randint(15, length - 15)
        if secs not in used:
            used.add(secs)
            return secs
    raise RuntimeError("no free time in the period")


def _order(period, o: _Options) -> int:
    """Sorts 1, 2, 3, OT, OT2."""
    return period if isinstance(period, int) else o.periods + (1 if period == "OT" else int(period[2:]))


def _goal_row(g: dict) -> dict:
    row = {"period": g["period"], "time": g["time"], "side": g["side"], "num": g["num"]}
    if g["assist_nums"]:
        row["assists"] = g["assist_nums"]
    if g["mark"]:
        row["strength"] = g["mark"]
    if g["en"]:
        row["en"] = True
    if g["ps"]:
        row["ps"] = True
    return row


# ------------------------------------------------------------------ penalties

def _penalties(rng, game, plan, o: _Options, pool, nums, goals) -> list[dict]:
    """Penalties as {period, secs, side, player or None (bench), served, infraction, minutes}: the ones the power-play
    and short-handed goals need, then ordinary ones (minors, the odd major), then a bench penalty in some games."""
    slots: dict[tuple, set] = {}
    found = []

    def add(side, period, secs, who, infraction, minutes, served=None):
        slots.setdefault((side, period), set()).add(secs)
        found.append({"period": period, "secs": secs, "side": side, "player": who, "served": served,
                      "infraction": infraction, "minutes": minutes})

    def free(side, period, secs) -> int | None:
        for secs in range(secs, 4, -1):                  # the nearest free second before the goal
            if secs not in slots.get((side, period), set()):
                return secs
        return None

    for g in goals:
        if g["mark"] not in ("PP", "SH"):
            continue
        side = _other(g["side"]) if g["mark"] == "PP" else g["side"]
        secs = free(side, g["period"], g["secs"] - rng.randint(15, 100))
        if secs is None or g["secs"] < 30:
            g["mark"] = None                             # too early in the period for the penalty to come first
            continue
        add(side, g["period"], secs, rng.choice(pool[side]), rng.choice(INFRACTIONS), 2)
    count = rng.choices(*PENALTY_COUNTS)[0]
    for _ in range(count):
        side, period = rng.choice(SIDES), rng.randint(1, o.periods)
        secs = free(side, period, rng.randint(40, o.period_secs - 20))
        if secs is None:
            continue
        roll = rng.random()
        if roll < 0.02:
            infraction, minutes = rng.choice(MAJORS), 5
        elif roll < 0.03:
            infraction, minutes = "Misconduct", 10
        elif roll < 0.06:
            infraction, minutes = "High sticking", 4
        else:
            infraction, minutes = rng.choice(INFRACTIONS), 2
        add(side, period, secs, rng.choice(pool[side]), infraction, minutes)
    if zlib.crc32(f"{BENCH_SALT}:{game.game_id}".encode()) % BENCH_EVERY == 0:
        side, period = rng.choice(SIDES), rng.randint(1, o.periods)
        secs = free(side, period, rng.randint(40, o.period_secs - 20))
        if secs is not None:
            add(side, period, secs, None, rng.choice(BENCH_INFRACTIONS), 2, served=rng.choice(pool[side]))
    found.sort(key=lambda p: (p["period"], p["secs"], p["side"]))
    return found


def _penalty_row(p: dict) -> dict:
    row = {"period": p["period"], "time": p["time"], "side": p["side"], "num": p["num"]}
    if p["served_num"] is not None:
        row["served_by"] = p["served_num"]
    row["infraction"], row["minutes"] = p["infraction"], p["minutes"]
    return row


# ------------------------------------------------------------------ the clock

def _clock(goals, penalties, o: _Options) -> None:
    """Write the numbers and the time of every goal and penalty (time elapsed, or time left with `clock: remaining`)."""
    for g in goals:
        length = o.period_secs if isinstance(g["period"], int) else o.ot_secs
        g["time"] = _time(g["secs"], length, o)
    for p in penalties:
        p["time"] = _time(p["secs"], o.period_secs, o)


def _time(secs: int, length: int, o: _Options) -> str:
    secs = length - secs if o.remaining else secs
    return f"{secs // 60}:{secs % 60:02d}"


# ------------------------------------------------------------------ goalies, score, shootout

def _goalie_rows(rng, game, o: _Options, side, net, nums, goals, plan) -> list[dict]:
    against = [g for g in goals if g["side"] == _other(side) and not g["en"]]
    total = len(against)
    if len(net) == 1:
        splits = [total]
    else:
        first = rng.randint(0, total)
        splits = [first, total - first]
    rows = [{"num": nums[p], "ga": ga} for p, ga in zip(net, splits)]
    if len(rows) == 2:                                   # the finisher gets the decision of a winner, the starter of the rest
        mine = sum(1 for g in goals if g["side"] == side) + (1 if plan["so"] == side else 0)
        theirs = sum(1 for g in goals if g["side"] == _other(side)) + (1 if plan["so"] == _other(side) else 0)
        rows[1 if mine > theirs else 0]["decision"] = True
    if o.shots:
        for row in rows:
            row["shots"] = row["ga"] + _saves(rng, row["ga"])
    return rows


def _saves(rng, ga: int) -> int:
    """Saves for a goalie who let in `ga` goals: about nine in ten shots, at least a few."""
    shots = max(ga + 3, round(ga / (1 - SAVE_PCT)) + rng.randint(-4, 6)) if ga else rng.randint(6, 30)
    return max(shots - ga, 3)


def _score(plan, goals, o: _Options) -> dict:
    out = {}
    for side in SIDES:
        periods = [sum(1 for g in goals if g["side"] == side and g["period"] == n) for n in range(1, o.periods + 1)]
        ot = None
        if plan["ot"]:
            ot = sum(1 for g in goals if g["side"] == side and not isinstance(g["period"], int))
        so = (1 if plan["so"] == side else 0) if plan["so"] else None
        out[side] = {"periods": periods, "ot": ot, "so": so, "final": sum(periods) + (ot or 0) + (so or 0)}
    return out


def _shootout(rng, o: _Options, plan, pool, nums) -> dict:
    """Shooters take turns until it is decided (the rules' own stopping point): three each, then one at a time."""
    winner = plan["so"]
    for _ in range(MAX_TRIES):
        first = rng.choice(SIDES)
        order = {side: rng.sample(pool[side], len(pool[side])) for side in SIDES}
        shots = {side: [] for side in SIDES}
        n = {side: 0 for side in SIDES}
        g = {side: 0 for side in SIDES}
        while not _decided(n, g, o.rounds) and n["home"] < 20:
            side = first if n[first] == n[_other(first)] else _other(first)
            hit = rng.random() < 0.33
            shots[side].append({"num": nums[side][order[side][n[side] % len(order[side])]], "scored": hit})
            n[side] += 1
            g[side] += hit
        if g["home"] != g["away"] and (g["home"] > g["away"]) == (winner == "home"):
            return {"first": first, "home": shots["home"], "away": shots["away"]}
    raise RuntimeError("could not draw a shootout")


def _decided(n, g, rounds) -> bool:
    """Whether the shootout is over after n shots each so far, with g goals."""
    def left(side, other):
        return max(rounds - n[side], 0) if n[side] < rounds else max(n[other] - n[side], 0)
    return g["home"] > g["away"] + left("away", "home") or g["away"] > g["home"] + left("home", "away")


# ------------------------------------------------------------------ small helpers

def _other(side: str) -> str:
    return "away" if side == "home" else "home"


def _jersey(number):
    """A jersey number as the sheet writes it: a whole number, or "00" in quotes."""
    return number if number == "00" else int(number)


def _int(value, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default
