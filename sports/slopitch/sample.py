"""Sample data for slo-pitch: a made-up rec league and one function that writes a believable score sheet.

`scripts/make_sample.py` does the rest (players, schedule, outcomes) with a fixed seed. Nothing here looks like a
real league: the league is "Maple Park Slo-Pitch" (the made-up league of BRIEF.md and the design system), the teams
are the design system's six and the players are made-up "First L." names (no jersey numbers: the game page's # is the
batting order).

`sheet()` plays a game half-inning by half-inning. A half-inning is mostly 0 to 3 runs, now and then the run limit
(the circled 5); the open last inning (and extra innings, when the league leaves them open) scores more. The game
ends the way `game.outcome` asks, bent to what the league's rules allow:

* the team batting last writes an `X` when it leads after the top of the last inning, and otherwise bats: a
  home win there is a walk-off that stops at the winning run (now and then a home run brings in one or two more);
* a regular-season game level after the last inning is a tie (`extra_innings: 0`, the default); when the league
  plays extra innings (`extra_innings` above 0) a tie is played out inning by inning, all level;
* a playoff game never ends level: it goes to extra innings (and a few playoff games go there on purpose, the way a
  league's final sometimes does), each one level until the last, which is decisive or a walk-off.

Over a season it writes: a mercy-rule game (`called: mercy`: a lead of `mercy_runs` after `mercy_after` innings, an
`X` when the home team led after the top half), the odd game called for time, weather or darkness, walk-offs, limit
innings, and one game with no batting lines when the league lets a sheet leave them out (`batting: optional`). Which
game is which is picked from the game id, so it is stable. The batting lines add up: the R column is the runs, the H
column the H box, RBI at most the runs, home runs within `hr_limit`, plate appearances believable for the innings.
One draft has a batter written in by name (no player id yet). Like every function of a sport it is pure: the same
arguments give the same sheet, and it changes nothing it is given.
"""
from __future__ import annotations

import zlib

from scripts.core.model import SampleGame, SportContext

LEAGUE_NAME = "Maple Park Slo-Pitch"
TEAMS = [("sluggers", "Sluggers", "SLG"), ("mudcats", "Mudcats", "MUD"), ("dugout-dogs", "Dugout Dogs", "DDG"),
         ("line-drives", "Line Drives", "LND"), ("long-balls", "Long Balls", "LGB"), ("bunters", "Bunters", "BUN")]
PLAYERS_PER_TEAM = 12                                   # rec teams bat 10 to 12
NUMBERS = False                                         # the game page's # is the batting order
SURFACES = ["1", "2", "3"]                              # Diamond 1, 2, 3
TIMES = ["18:30", "18:30", "19:45"]                     # two early games, then the late one on Diamond 3
NOTES = ["Played under the lights: the diamond lights came on in the 5th.", "Started ten minutes late: rain delay.",
         "One ball lost over the fence in the 3rd."]

SIDES = ("away", "home")                                # visitors first
SUB_NAMES = ["Hugo V.", "Ines R.", "Jory K.", "Kemal D."]    # a batter written in by hand on a draft: a name, no id
LINEUP_MIN = 10                                         # a sheet has at least ten batters (a team of twelve fields them)

# A half-inning's runs. `LIMITED` is for k below the limit (the limit itself has weight LIMIT_HIT), `OPEN` for an open
# last inning, `UNLIMITED` for every inning of a league with no run limit.
LIMITED = [30, 22, 16, 12, 8, 6, 4, 3, 2, 1]
LIMIT_HIT = 9
OPEN = [22, 18, 15, 12, 10, 8, 6, 4, 3, 2, 1]
UNLIMITED = [26, 20, 16, 13, 9, 6, 4, 3, 2, 1]
FINISH_CHANCE = 0.3                                     # `limit_play: finish`: the play that reached the limit goes on
HOT, COLD = 1.5, -1.5                                   # how a mercy game's winner and loser are weighted
EXTRA_LEVEL = ([0, 1, 2], [70, 22, 8])                  # runs in an extra inning that stays level
EXTRA_COUNT = ([1, 2, 3], [65, 25, 10])                 # extra innings in a game that needs them
WALK_BONUS = 0.2                                        # a walk-off half where a home run brings in more than needed
ERRORS = ([0, 1, 2, 3, 4], [30, 35, 20, 10, 5])
HITS_PER_RUN, HITS_NOISE = 1.25, (-1.5, 2.5)
HOME_RUNS = ([0, 1, 2, 3], [45, 30, 18, 7])
WALKS = ([0, 1, 2, 3], [45, 30, 17, 8])
RBI_LOST = [0, 0, 1, 1, 2]                              # runs that came in with no RBI (an error, a fielder's choice)
# Which games are special is picked from the game id (changing a salt moves them; tests/test_slopitch_sample.py checks
# that each season has every one).
MERCY_EVERY, MERCY_SALT = 11, "m4"                      # one regular-season game in eleven ends on the mercy rule
CALLED_EVERY, CALLED_SALT = 12, "c12"                    # one in twelve is called short (time, weather, darkness)
WALKOFF_EVERY, WALKOFF_SALT = 3, "w5"                   # a home win that leaves the home team batting last
PLAYOFF_EXTRAS_EVERY, PLAYOFF_EXTRAS_SALT = 3, "x2"     # one playoff game in three goes to extra innings
NO_LINES_EVERY, NO_LINES_SALT = 9, "n3"                 # a sheet with no batting lines (`batting: optional`)
MAX_TRIES = 4000
MERCY_X_CHANCE = 0.5                                    # the home team's mercy win ends after the top half (an X)


# ------------------------------------------------------------------ the sheet

def sheet(rng, game: SampleGame, ctx: SportContext) -> dict:
    """A slo-pitch sheet that passes check() and ends the way `game.outcome` asks (bent to the league's rules)."""
    o = _Options(ctx)
    plan = _plan(game, ctx, o)
    runs, called = _play(rng, o, plan)
    batted = {s: sum(1 for v in runs[s] if v != "X") for s in SIDES}
    lineup = {s: _lineup(rng, game, ctx, s) for s in SIDES}
    with_lines = o.batting in ("optional", "every_game") and not (
        o.batting == "optional" and _pick(game.game_id, NO_LINES_SALT, NO_LINES_EVERY) and ctx.folder == "games")
    lines = {}
    for s in SIDES:
        lines[s] = _line_totals(rng, o, runs, s, batted[s], lineup[s], with_lines)
    totals = {}
    for s in SIDES:
        box = {"r": sum(v for v in runs[s] if v != "X")}
        if o.team_hits:
            box["h"] = lines[s]["h"]
        if o.team_errors:
            box["e"] = rng.choices(*ERRORS)[0]
        totals[s] = box
    out: dict = {"runs": {s: list(runs[s]) for s in SIDES}, "totals": totals}
    if called:
        out["called"] = called
    if o.batting != "none":
        out["batting"] = {s: _batting_rows(lineup[s], lines[s], with_lines) for s in SIDES}
        if ctx.folder == "drafts":
            _name_one(game, out["batting"])
    return out


class _Options:
    """The league's options this sheet depends on, with the sport's defaults."""

    def __init__(self, ctx: SportContext):
        g = ctx.options.get
        self.innings = _int(g("innings"), 7)
        self.limit = _int(g("run_limit"), 5)
        self.open_last = (g("open_innings") or "last") == "last"
        self.finish = (g("limit_play") or "stop") == "finish"
        self.mercy_runs = _int(g("mercy_runs"), 15)
        self.mercy_after = _int(g("mercy_after"), 5)
        self.official = _int(g("official_innings"), 4)
        self.extra_innings = _int(g("extra_innings"), 0)
        self.hr_limit = _int(g("hr_limit"), 0)
        self.batting = g("batting") or "optional"
        self.team_hits = (g("team_hits") or "kept") == "kept"
        self.team_errors = (g("team_errors") or "none") == "kept"
        self.playoff = ctx.game_type != "regular"

    def limited(self, i: int) -> bool:
        """Is the inning with 0-based index i limited by the run limit?"""
        return bool(self.limit) and not (self.open_last and i >= self.innings - 1)

    def cap(self, i: int):
        """The most runs a half-inning may hold, or None when it has no limit."""
        return (self.limit + (3 if self.finish else 0)) if self.limited(i) else None


def _int(value, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _pick(game_id: str, salt: str, every: int) -> bool:
    return zlib.crc32(f"{salt}:{game_id}".encode()) % every == 0


# ------------------------------------------------------------------ how the game ends

def _plan(game: SampleGame, ctx: SportContext, o: _Options) -> dict:
    """{"winner": "home" | "away" | None (level after the last inning), "kind": ..., "innings": innings played,
    "extras": extra innings to play, "called": the reason a short game stopped or None}."""
    outcome = game.outcome
    winner = outcome[4:] if outcome.startswith("win_") else None
    gid = game.game_id
    plan = {"winner": winner, "kind": "normal", "innings": o.innings, "extras": 0, "called": None}
    if o.playoff:
        if winner is None or _pick(gid, PLAYOFF_EXTRAS_SALT, PLAYOFF_EXTRAS_EVERY):
            plan["kind"], plan["extras"] = "extras", None           # None: as many as it takes
            plan["winner"] = winner or ("home" if zlib.crc32(gid.encode()) % 2 else "away")
        elif winner == "home" and _pick(gid, WALKOFF_SALT, WALKOFF_EVERY):
            plan["kind"] = "walkoff"
        return plan
    if winner is None and outcome == "ot":
        winner = "home" if zlib.crc32(gid.encode()) % 2 else "away"
        if o.extra_innings:
            plan["winner"], plan["kind"], plan["extras"] = winner, "extras", None
        else:
            plan["winner"] = None
    if plan["winner"] is None:
        plan["extras"] = o.extra_innings                              # a tie: played level, as many as are allowed
        return plan
    mercy_at = max(o.mercy_after, o.official)
    if o.mercy_runs and mercy_at < o.innings and _pick(gid, MERCY_SALT, MERCY_EVERY):
        plan.update(kind="mercy", innings=mercy_at, called="mercy")
    elif o.innings - 1 >= o.official and _pick(gid, CALLED_SALT, CALLED_EVERY):
        reasons = ["time", "weather", "darkness"]
        plan.update(kind="called", innings=o.innings - 1, called=reasons[zlib.crc32(gid.encode()) % 3])
    elif winner == "home" and _pick(gid, WALKOFF_SALT, WALKOFF_EVERY):
        plan["kind"] = "walkoff"
    return plan


# ------------------------------------------------------------------ the runs

def _draw(rng, o: _Options, i: int, bias: float = 0.0) -> int:
    """The runs of one half-inning (index i): mostly 0 to 3, now and then the limit; an open inning scores more.
    `bias` above 0 favours big innings (a team that is running away with the game), below 0 small ones."""
    cap = o.cap(i)
    if not o.limit:
        base = UNLIMITED
    elif cap is None:
        base = OPEN
    else:
        base = (LIMITED + [1] * 20)[:o.limit] + [LIMIT_HIT if o.limit <= 8 else 1]
    weights = [w * (1 + min(k, 8)) ** bias for k, w in enumerate(base)]
    runs = rng.choices(range(len(weights)), weights)[0]
    if o.finish and cap is not None and runs == o.limit and rng.random() < FINISH_CHANCE:
        runs += rng.choice([1, 2, 3])
    return runs


def _lopsided(away: list, home: list, o: _Options) -> bool:
    """A normal game never leads by the mercy rule at the end of an inning it applies to: that game would have been
    called."""
    if not o.mercy_runs:
        return False
    a, h = [0 if v == "X" else v for v in away], [0 if v == "X" else v for v in home]
    return any(abs(sum(h[:k]) - sum(a[:k])) >= o.mercy_runs for k in range(o.mercy_after, len(a) + 1))


def _play(rng, o: _Options, plan: dict):
    """({"away": boxes, "home": boxes}, called) for the plan: regulation (or the short game), then extra innings."""
    for _ in range(MAX_TRIES):
        runs = _regulation(rng, o, plan)
        if runs is None:
            continue
        if plan["kind"] == "extras" or plan["extras"] != 0:
            runs = _extras(rng, o, plan, runs)
            if runs is None:
                continue
        return runs, plan["called"]
    if plan["kind"] != "normal":                                         # the special game cannot be had: play a plain one
        return _play(rng, o, {**plan, "kind": "normal", "innings": o.innings, "called": None, "extras": 0})
    raise RuntimeError("could not draw runs for a slo-pitch game")


def _regulation(rng, o: _Options, plan: dict):
    """One try at the innings of the game (m innings, the last bottom half perhaps an X). None when it does not fit
    the plan. A game that goes to extra innings (`plan["winner"]` is the winner of the extras) is level here."""
    m, kind = plan["innings"], plan["kind"]
    level = plan["kind"] == "extras" or plan["extras"] != 0              # level after the last inning, extras follow
    winner = None if level else plan["winner"]
    mercy = kind == "mercy"
    bias = {s: 0.0 for s in SIDES}
    if mercy:
        bias = {s: (HOT if s == plan["winner"] else COLD) for s in SIDES}
    away = [_draw(rng, o, i, bias["away"]) for i in range(m)]
    home = [_draw(rng, o, i, bias["home"]) for i in range(m - 1)]
    a, h = sum(away), sum(home)
    last = m - 1
    if winner == "home" and h > a:                                      # leads after the top half: not needed
        if kind == "walkoff":
            return None
        if kind == "mercy" and rng.random() < MERCY_X_CHANCE:
            home.append("X")
            return _accept(o, plan, away, home)
        if kind != "mercy":
            home.append("X")
            return _accept(o, plan, away, home)
    if mercy:
        home.append(_draw(rng, o, last, bias["home"]))
        return _accept(o, plan, away, home)
    box = _draw(rng, o, last)
    cap = o.cap(last)
    if winner == "home":                                                # the home team takes the lead: it stops there
        if h + box <= a:
            return None
        needed = a - h + 1
        if kind == "walkoff" and needed > 4:
            return None
        box = needed + (min(box - needed, 3) if rng.random() < WALK_BONUS else 0)
        if cap is not None and box > cap:
            return None
    elif winner == "away":
        if h + box >= a:
            return None
    elif h + box != a:                                                  # level after the last inning
        return None
    home.append(box)
    return _accept(o, plan, away, home)


def _accept(o: _Options, plan: dict, away: list, home: list):
    """The two lists, or None when they do not fit the plan (a mercy lead too small, a normal game that was a rout)."""
    a, h = sum(away), sum(v for v in home if v != "X")
    if plan["kind"] == "mercy":
        lead = (h - a) if plan["winner"] == "home" else (a - h)
        return {"away": away, "home": home} if lead >= o.mercy_runs else None
    if plan["kind"] == "extras" or plan["extras"] != 0:
        return {"away": away, "home": home} if a == h else None
    if plan["winner"] is None and a != h:
        return None
    if _lopsided(away, home, o):
        return None
    return {"away": away, "home": home}


def _extras(rng, o: _Options, plan: dict, runs: dict):
    """Extra innings after a game level through the last inning. Every one stays level until the last, which the
    winner takes (a walk-off for the home team, which stops at the winning run); a tie plays the innings it is allowed,
    all level. None when the inning does not fit the league's limit."""
    n = o.innings
    count = plan["extras"]
    winner = plan["winner"]
    decided = plan["kind"] == "extras"
    if count is None:
        count = rng.choices(*EXTRA_COUNT)[0]
    away, home = list(runs["away"]), list(runs["home"])
    for k in range(count):
        i = n + k
        cap = o.cap(i)
        final = decided and k == count - 1
        if not final:
            e = rng.choices(*EXTRA_LEVEL)[0]
            if cap is not None and e > cap:
                return None
            away.append(e), home.append(e)
        elif winner == "away":
            top = rng.choices([1, 2, 3], [55, 30, 15])[0]
            if cap is not None and top > cap:
                return None
            away.append(top), home.append(rng.randint(0, top - 1))
        else:
            top = rng.choices([0, 1, 2], [50, 35, 15])[0]
            box = top + 1 + (rng.choice([1, 2, 3]) if rng.random() < WALK_BONUS else 0)
            if cap is not None and (box > cap or top > cap):
                return None
            away.append(top), home.append(box)
    return {"away": away, "home": home}


# ------------------------------------------------------------------ batters and their lines

def _lineup(rng, game: SampleGame, ctx: SportContext, side: str) -> list[str]:
    """The batting order: the players make_sample drew for this side, filled up to ten with the team's other regulars,
    in a shuffled order. A spare (sub) bats too when one came."""
    ids = list(game.players.get(side, []))
    team = ctx.sides[side]
    for p, who in ctx.players.items():
        if len(ids) >= LINEUP_MIN:
            break
        if who.team == team and p not in ids:
            ids.append(p)
    rng.shuffle(ids)
    return ids


def _weight(salt: str, pid: str, low: float, high: float) -> float:
    """A made-up, fixed trait of a player (his hitting, his power): the same in every game."""
    return low + (high - low) * (zlib.crc32(f"{salt}:{pid}".encode()) % 100) / 100


def _line_totals(rng, o: _Options, runs: dict, side: str, batted: int, ids: list[str], with_lines: bool) -> dict:
    """{"h": team hits, "rows": a line per batter (when the game has lines)}: lines that add up to the runs."""
    scored = sum(v for v in runs[side] if v != "X")
    limit_boxes = sum(1 for i, v in enumerate(runs[side]) if v != "X" and o.limited(i) and v >= o.limit > 0)
    outs = max(3, 3 * batted - limit_boxes)
    b = len(ids)
    hits = max(0, round(scored * HITS_PER_RUN + rng.uniform(*HITS_NOISE)))
    hits = max(0, min(hits, b * (batted + 1) - outs))                     # no batter comes up more than innings + 2 times
    hr = min(rng.choices(*HOME_RUNS)[0], hits, scored)
    if o.hr_limit:
        hr = min(hr, o.hr_limit)
    bb_total = min(rng.choices(*WALKS)[0], b)
    if not with_lines:
        return {"h": hits, "rows": None}
    skill = [_weight("sk", p, 0.5, 1.5) for p in ids]
    power = [_weight("pw", p, 0.1, 1.0) ** 2 for p in ids]
    ab_total = outs + hits
    base, extra = divmod(ab_total, b)
    ab = [base + (1 if i < extra else 0) for i in range(b)]
    h, hrs, bb, r, rbi = [0] * b, [0] * b, [0] * b, [0] * b, [0] * b
    for _ in range(hits):
        h[_choose(rng, [skill[i] if h[i] < ab[i] else 0 for i in range(b)])] += 1
    hits = sum(h)
    for _ in range(hr):
        hrs[_choose(rng, [power[i] if h[i] > hrs[i] else 0 for i in range(b)])] += 1
    for _ in range(bb_total):
        room = [1 if ab[i] + bb[i] < batted + 2 else 0 for i in range(b)]
        if any(room):
            bb[_choose(rng, room)] += 1
    r = list(hrs)                                                  # a home run scores its hitter
    for _ in range(scored - sum(hrs)):
        reach = [(h[i] + bb[i] + 0.3) * skill[i] if r[i] < min(20, h[i] + bb[i] + 1) else 0 for i in range(b)]
        if not any(reach):                                         # nobody left who reached base that often
            reach = [1 if r[i] < min(20, ab[i] + bb[i]) else 0 for i in range(b)]
        if not any(reach):
            reach = [1 if r[i] < 20 else 0 for i in range(b)]
        r[_choose(rng, reach)] += 1
    batted_in = min(scored, max(hr, scored - rng.choice(RBI_LOST))) if hits else 0
    rbi = list(hrs)
    for _ in range(batted_in - sum(hrs)):
        who = [h[i] * power[i] ** 0.5 if rbi[i] < min(20, 4 * h[i]) else 0 for i in range(b)]
        if not any(who):
            break
        rbi[_choose(rng, who)] += 1
    return {"h": hits, "rows": [{"ab": ab[i], "r": r[i], "h": h[i], "rbi": rbi[i], "hr": hrs[i], "bb": bb[i]}
                                for i in range(b)]}


def _choose(rng, weights: list) -> int:
    return rng.choices(range(len(weights)), weights)[0]


def _batting_rows(ids: list[str], line: dict, with_lines: bool) -> list[dict]:
    if not with_lines:
        return [{"player": p} for p in ids]
    return [{"player": p, **row} for p, row in zip(ids, line["rows"])]


def _name_one(game: SampleGame, batting: dict) -> None:
    """On a draft, one batter is written in by name with no player id yet."""
    h = zlib.crc32(game.game_id.encode())
    side = SIDES[h % 2]
    rows = batting[side]
    spot = h % len(rows)
    row = rows[spot]
    rows[spot] = {"name": SUB_NAMES[h % len(SUB_NAMES)], **{k: v for k, v in row.items() if k != "player"}}
