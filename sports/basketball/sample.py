"""Sample data for basketball: a made-up league and one function that writes a believable score sheet.

`scripts/make_sample.py` does the rest (players, schedule, outcomes) with a fixed seed. Nothing here looks like a
real league: the league is "Riverside Masters Basketball", the teams are rivers, birds and trees, and the players
are made-up "First L." names (docs/stage-5-basketball-spec.md, section 6).

`sheet()` is a port of the Masters sample writer (`build_sheet` and `_fill_quarters`): it draws each player's
points, free throws and fouls, chooses quarter totals that honour the outcome, then fills the running score so
every quarter ends exactly on its box. Made free throws are written as 1-point scores (a simplification for
made-up data: under league rules one can be worth more). Like every function of a sport it is pure: the same
arguments give the same sheet, and it changes nothing it is given.
"""
from __future__ import annotations

import zlib

from scripts.core.model import SampleGame, SportContext

LEAGUE_NAME = "Riverside Masters Basketball"
TEAMS = [("rapids", "Rapids", "RAP"), ("herons", "Herons", "HER"), ("foxes", "Foxes", "FOX"),
         ("pines", "Pines", "PIN"), ("comets", "Comets", "COM")]
PLAYERS_PER_TEAM = 8       # read by make_sample.py (optional; 7 is its default)

SIDES = ("home", "away")
SUB_NAMES = ["Hugo V.", "Ines R.", "Jory K.", "Kemal D."]    # a sub written in by hand on a draft: a name, no player id
FLAGRANT_TEXTS = ["hard foul on a drive", "elbow on a rebound", "shove after the whistle"]
FLAGRANT_EVERY = 13        # about one game in thirteen has a flagrant foul (picked from the game id, so it is stable)
TECH_CHANCE = 0.02         # one player in fifty, per game, gets a technical foul
FOUL_WEIGHTS = [14, 24, 26, 20, 11, 5]       # 0 to 5 personal fouls
MAX_FILL_TRIES = 3000
MAX_DRAWS = 60


class _Retry(Exception):
    """A draw that cannot be fitted to its quarter totals: the caller draws again."""


# ------------------------------------------------------------------ the sheet

def sheet(rng, game: SampleGame, ctx: SportContext) -> dict:
    """A basketball sheet that passes check() and ends the way `game.outcome` asks. The outcome is bent to what
    the league's rules allow: with `overtime: none`, "ot" becomes a tie (a win in the playoffs, which never
    tie); with overtime, a tie is a game still level after the overtime (a regular-season game only)."""
    overtime_on = ctx.options.get("overtime", "overtime") == "overtime"
    outcome = game.outcome
    if outcome == "ot" and not overtime_on:
        outcome = "tie"
    if outcome == "tie" and ctx.game_type != "regular":
        outcome = "ot" if overtime_on else rng.choice(["win_home", "win_away"])
    for _ in range(MAX_DRAWS):
        try:
            return _draw(rng, game, ctx, outcome, overtime_on)
        except _Retry:
            continue
    raise RuntimeError(f"could not draw a sheet for {game.game_id} (outcome {outcome!r})")


def _draw(rng, game, ctx, outcome, overtime_on):
    count = _quarter_count(ctx)
    keys = _box_keys(ctx, count)
    regulation, overtime = _scores(rng, outcome, overtime_on)
    final = {s: regulation[s] + (overtime[s] if overtime else 0) for s in SIDES}
    rows = {s: _rows(rng, game, ctx, s) for s in SIDES}
    for side in SIDES:
        _points(rng, rows[side], final[side])
        _free_throws(rng, rows[side])
        _fouls(rng, rows[side], _foul_limit(ctx))

    ends = {}
    for side in SIDES:
        per = _quarter_scores(rng, regulation[side], count)
        ends[side] = [sum(per[:i + 1]) for i in range(count)]
        if overtime:
            ends[side].append(final[side])
    running = {side: _fill_running(rng, rows[side], ends[side]) for side in SIDES}

    notes = _flagrant(rng, game, rows)
    players = {}
    for side in SIDES:
        players[side] = [_row_out(rng, r) for r in rows[side]]
    boxes = {}
    for side in SIDES:
        box = {key: ends[side][i] for i, key in enumerate(keys)}
        box["ot"] = final[side] if overtime else None
        box["final"] = final[side]
        boxes[side] = box
    out = {"players": players, "running": running, "lines": {s: ends[s][:count] for s in SIDES}, "boxes": boxes}
    if notes:
        out["notes"] = notes
    return out


# ------------------------------------------------------------------ scores

def _scores(rng, outcome, overtime_on):
    """(regulation total per side, overtime points per side or None) for the outcome."""
    if outcome in ("win_home", "win_away"):
        loser = _team_total(rng)
        winner = loser + min(25, max(1, round(abs(rng.gauss(0, 8)))))
        home, away = (winner, loser) if outcome == "win_home" else (loser, winner)
        return {"home": home, "away": away}, None
    level = _team_total(rng)
    regulation = {"home": level, "away": level}
    if outcome == "ot":
        home = rng.randint(2, 9)
        away = rng.choice([n for n in range(2, 10) if n != home])
        return regulation, {"home": home, "away": away}
    if outcome == "tie" and overtime_on:                    # still level after overtime
        extra = rng.randint(2, 8)
        return regulation, {"home": extra, "away": extra}
    return regulation, None                                 # a tie after Q4 and no overtime


def _team_total(rng):
    return min(85, max(38, round(rng.gauss(57, 9))))


def _quarter_scores(rng, total, count):
    weights = [rng.uniform(0.75, 1.25) for _ in range(count)]
    per = [int(total * w / sum(weights)) for w in weights]
    per[rng.randrange(count)] += total - sum(per)
    return per


# ------------------------------------------------------------------ rows

def _rows(rng, game, ctx, side):
    """The roster rows of one side, as working dicts: the team's regulars in roster order (an absent one is
    listed Here: false about half the time), then any spares who played, then (on a draft only) one sub whose
    name was written in by hand and who has no player id yet."""
    team = ctx.sides[side]
    played = list(game.players.get(side, []))
    roster = [p for p in ctx.players.values() if p.team == team and not p.sub]
    taken = {p.number for p in roster if p.number is not None}
    rows = []

    def add(player, here, name=None):
        number = player.number if player is not None else None
        if number is None:                       # a player with no jersey number in players.yml: the sheet needs one
            number = next(str(n) for n in range(99, 0, -1) if str(n) not in taken)
            taken.add(number)
        rows.append({"player": player.id if player else None, "name": name, "num": number, "here": here,
                     "pts": 0, "ftm": 0, "fta": 0, "fouls": 0, "tech": 0})

    for p in roster:
        if p.id in played:
            add(p, True)
        elif rng.random() < 0.5:
            add(p, False)
    for pid in played:
        if not any(r["player"] == pid for r in rows):
            add(ctx.players[pid], True)
    if ctx.folder == "drafts" and side == _sub_side(game):
        add(None, True, name=SUB_NAMES[zlib.crc32(game.game_id.encode()) % len(SUB_NAMES)])
    return rows


def _sub_side(game):
    """The side that has the hand-written sub on a draft: stable for the game."""
    return SIDES[zlib.crc32(game.game_id.encode()) % 2]


def _here(rows):
    return [r for r in rows if r["here"]]


def _points(rng, rows, total):
    """Share the side's final score among the players who are here, by random weight (leftover points to the
    player with the largest share)."""
    here = _here(rows)
    weights = [rng.random() ** 1.3 + 0.3 for _ in here]
    points = [int(total * w / sum(weights)) for w in weights]
    points[weights.index(max(weights))] += total - sum(points)
    for r, pts in zip(here, points):
        r["pts"] = pts


def _free_throws(rng, rows):
    """Circles for each player here: attempts, and made ones (never more than the player's points, and never
    leaving exactly one point for the field goals, which come in 2s and 3s)."""
    for r in _here(rows):
        attempts = rng.choices(range(9), weights=[30, 14, 14, 12, 10, 8, 5, 4, 3])[0]
        rate = rng.uniform(0.4, 0.9)
        made = sum(rng.random() < rate for _ in range(attempts))
        made = min(made, r["pts"])
        if r["pts"] - made == 1:
            made += 1
        r["ftm"], r["fta"] = made, max(attempts, made)


def _fouls(rng, rows, limit):
    for r in _here(rows):
        r["fouls"] = min(rng.choices(range(len(FOUL_WEIGHTS)), weights=FOUL_WEIGHTS)[0], limit)
        r["tech"] = 1 if rng.random() < TECH_CHANCE else 0


def _flagrant(rng, game, rows):
    """About one game in FLAGRANT_EVERY has one flagrant foul: a Notes entry, and the foul box that goes with it
    (a flagrant is also a personal foul)."""
    if zlib.crc32(game.game_id.encode()) % FLAGRANT_EVERY != 0:
        return []
    side = rng.choice(SIDES)
    row = rng.choice([r for r in _here(rows[side]) if r["player"]])
    row["fouls"] = max(row["fouls"], 1)
    return [{"side": side, "num": _jersey(row["num"]), "q": rng.randint(1, 4), "kind": "flagrant",
             "text": rng.choice(FLAGRANT_TEXTS)}]


def _jersey(number):
    """A jersey number as the sheet writes it: a whole number, or "00" in quotes."""
    return number if number == "00" else int(number)


def _row_out(rng, r):
    row = {}
    if r["player"]:
        row["player"] = r["player"]
    else:
        row["name"] = r["name"]
    row["num"] = _jersey(r["num"])
    row["here"] = r["here"]
    if r["here"]:
        circles = list("M" * r["ftm"] + "X" * (r["fta"] - r["ftm"]))
        rng.shuffle(circles)
        if circles:
            row["ft"] = "".join(circles)
        if r["fouls"]:
            row["fouls"] = r["fouls"]
        if r["tech"]:
            row["tech"] = r["tech"]
    return row


# ------------------------------------------------------------------ the running score

def _fill_running(rng, rows, ends):
    """A running score {total: jersey number} that lands exactly on each end (the quarter totals, then the
    final after an overtime). Made free throws are 1-point scores; each player's other points come in 2s and 3s.
    Random tries until every point is placed."""
    fts = {r["num"]: r["ftm"] for r in _here(rows)}
    baskets = {r["num"]: r["pts"] - r["ftm"] for r in _here(rows)}
    for _ in range(MAX_FILL_TRIES):
        ft, fg = dict(fts), dict(baskets)
        order, total = [], 0
        for end in ends:
            while total < end:
                options = [(1, n) for n, c in ft.items() if c]
                options += [(v, n) for n, b in fg.items() for v in (2, 2, 3) if v <= b and b - v != 1 and total + v <= end]
                if not options:
                    break
                v, n = rng.choice(options)
                if v == 1:
                    ft[n] -= 1
                else:
                    fg[n] -= v
                total += v
                order.append((total, n))
            if total != end:
                break
        else:
            if not any(ft.values()) and not any(fg.values()):
                return {t: _jersey(n) for t, n in order}
    raise _Retry()


# ------------------------------------------------------------------ the league's settings

def _quarter_count(ctx):
    value = ctx.sport.get("line_score", {}).get("periods", 4)
    return value if isinstance(value, int) and value > 0 else 4


def _box_keys(ctx, count):
    short = ctx.sport["words"]["period"]["short"].lower()
    return [f"{short}{n}" for n in range(1, count + 1)]


def _foul_limit(ctx):
    value = ctx.options.get("foul_limit", 5)
    return value if isinstance(value, int) and not isinstance(value, bool) else 5
