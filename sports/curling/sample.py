"""Sample data for curling: a made-up club and one function that writes a believable score card.

`scripts/make_sample.py` does the rest (players, schedule, outcomes) with a fixed seed. Nothing here looks like a
real club: the league is "Pine Lake Curling Club" (the made-up league of BRIEF.md and the design system), the
rinks have playful names (never a skip's surname: docs/stage-5-curling-spec.md, decision 13) and the players are
made-up "First L." names, four to a rink in throwing order (lead, second, vice, skip), no jersey numbers.

`sheet()` plays a game end by end: it tosses for the hammer, then each end follows club odds (the rink with the
hammer scores one to three most often, sometimes blanks to keep it, now and then a big end; the other rink
steals one end in six). It plays again with the same `rng` until the outcome asked for is met, so the result is
a fair-looking game, not a forced one. Like every function of a sport it is pure: the same arguments give the
same sheet, and it changes nothing it is given.

Over a season it writes steals, blanks and big ends in most games, a game a rink gave up after a late end (a
concession, the ends left X), a game stopped when ice time ran out, a regular-season tie and, in the playoffs
(or every level game when the league sets `extra_end: always`), extra ends. Which game is which is picked from
the game id, so it is stable.
"""
from __future__ import annotations

import zlib

from scripts.core.model import SampleGame, SportContext

LEAGUE_NAME = "Pine Lake Curling Club"
TEAMS = [("button-pushers", "Button Pushers", "BP"), ("hurry-hard", "Hurry Hard", "HH"),
         ("hog-liners", "Hog Liners", "HL"), ("free-guards", "Free Guards", "FG"),
         ("takeouts", "Takeouts", "TO"), ("stone-cold", "Stone Cold", "SC")]
PLAYERS_PER_TEAM = 4                                   # a rink: lead, second, vice, skip
NUMBERS = False                                        # curlers wear no jersey numbers
POSITIONS = ["lead", "second", "vice", "skip"]         # in throwing order: the first player of a rink is its lead
SURFACES = ["A", "B", "C"]                             # three games a night: sheets A, B and C
TIMES = ["18:30", "18:30", "20:45"]                    # sheets A and B at the early draw, sheet C at the late one
NOTES = ["Sheet C was running keen after the second end.", "Started ten minutes late: the ice was being scraped.",
         "A broom was replaced in the fifth end."]

SIDES = ("home", "away")
SUB_NAMES = ["Hugo V.", "Ines R.", "Jory K.", "Kemal D."]    # a spare written in by hand on a draft: a name, no player id
STEAL_CHANCE = 0.17                      # an end where the rink without the hammer scores
STEAL_POINTS = ([1, 2, 3], [88, 11, 1])
HAMMER_POINTS = ([0, 1, 2, 3, 4, 5], [15, 39, 30, 11, 4, 1])      # 0 is a blank end: the hammer is kept
SPECIAL_EVERY = 9                        # one game in nine is conceded, one in nine is stopped by the clock
SPECIAL_SALT = "s13"                     # picks which games (changing it moves them; tests/test_golden.py checks the season has each)
EXTRA_CHANCE = {"playoff": 0.45, "regular": 0.12}      # a decided game that goes to an extra end (when allowed)
MAX_TRIES = 6000


# ------------------------------------------------------------------ the sheet

def sheet(rng, game: SampleGame, ctx: SportContext) -> dict:
    """A curling sheet that passes check() and ends the way `game.outcome` asks. The outcome is bent to what the
    league's rules allow: an extra end exists in the playoffs, or in every game with `extra_end: always`, so
    "ot" is a tie where it does not and a tie is an extra-end game where it does."""
    ends = _int(ctx.options.get("ends"), 8)
    extra_allowed = ctx.game_type != "regular" or ctx.options.get("extra_end", "playoffs") == "always"
    outcome = game.outcome
    if outcome == "ot":
        outcome = "extra" if extra_allowed else "tie"
    elif outcome == "tie" and extra_allowed:
        outcome = "extra"
    elif outcome in ("win_home", "win_away") and extra_allowed and \
            rng.random() < EXTRA_CHANCE["playoff" if ctx.game_type != "regular" else "regular"]:
        outcome = "extra_" + outcome[4:]                # a win in an extra end
    if outcome == "extra":
        outcome = "extra_" + rng.choice(SIDES)
    if outcome == "tie" and ctx.game_type != "regular":     # a playoff game never ends level
        outcome = "extra_" + rng.choice(SIDES)

    stop = None                                          # how a decided game (not an extra-end one) ends early
    if outcome in ("win_home", "win_away"):
        stop = {0: "conceded", 1: "time_called"}.get(zlib.crc32(f"{SPECIAL_SALT}:{game.game_id}".encode()) % SPECIAL_EVERY)

    hammer = rng.choice(SIDES)
    played = _play(rng, ends, hammer, outcome, stop)
    out: dict = {"hammer": hammer, "ends": played["ends"]}
    if played["extra"]:
        out["extra"] = played["extra"]
    if played["stopped"] == "conceded":
        out["conceded"] = played["loser"]
    elif played["stopped"] == "time_called":
        out["time_called"] = True
    out["final"] = played["final"]
    if ctx.options.get("lineups", "recorded") == "recorded":
        out["lineups"] = _lineups(rng, game, ctx)
    return out


# ------------------------------------------------------------------ the ends

def _play(rng, ends: int, hammer: str, outcome: str, stop: str | None) -> dict:
    """Play ends until the game fits the outcome (and the way it stops, when it stops early)."""
    winner = outcome[-4:] if outcome.startswith(("win_", "extra_")) else None
    stop_after = None
    if stop == "conceded":                              # after a late end, a rink far behind shakes hands
        stop_after = rng.choice(range(max(3, -(-ends * 7 // 10)), ends))
    elif stop == "time_called":                         # ice time ran out one or two ends short
        stop_after = rng.choice([k for k in (ends - 2, ends - 1) if k >= 3])
    for _ in range(MAX_TRIES):
        games = _simulate(rng, ends, hammer)
        totals = _totals(games[: stop_after or ends])
        lead = totals["home"] - totals["away"]
        if outcome == "tie" or outcome.startswith("extra_"):          # level after the last end
            fits = lead == 0 and ends <= sum(totals.values()) <= 2 * ends - 2
        elif winner is None:
            continue
        elif stop == "conceded":
            fits = (lead if winner == "home" else -lead) >= max(3, ends // 2)
        elif stop == "time_called":
            fits = 1 <= (lead if winner == "home" else -lead) <= 3         # still a game when the clock ran out
        else:
            margin = lead if winner == "home" else -lead
            fits = 1 <= margin <= 6 and sum(totals.values()) >= ends
        if fits:
            break
    else:
        raise RuntimeError(f"could not play a curling game for the outcome {outcome!r}")

    count = stop_after or ends
    boxes = {side: [pts if scorer == side else 0 for scorer, pts, _ in games[:count]] + ["X"] * (ends - count)
             for side in SIDES}
    extra = {}
    if outcome.startswith("extra_"):
        extra = _extra(rng, _hammer_after(games, hammer), winner)
        totals = {side: totals[side] + sum(extra[side]) for side in SIDES}
    loser = None
    if stop == "conceded":
        loser = "away" if winner == "home" else "home"
    return {"ends": boxes, "extra": extra, "stopped": stop, "loser": loser, "final": dict(totals)}


def _simulate(rng, ends: int, hammer: str) -> list[tuple[str | None, int, str]]:
    """(side that scored or None, points, side with the hammer) for each end."""
    played = []
    for _ in range(ends):
        other = "away" if hammer == "home" else "home"
        if rng.random() < STEAL_CHANCE:                 # a steal: the hammer stays where it was
            played.append((other, rng.choices(*STEAL_POINTS)[0], hammer))
            continue
        points = rng.choices(*HAMMER_POINTS)[0]
        played.append((hammer if points else None, points, hammer))
        if points:                                      # scoring with the hammer gives it up; a blank end keeps it
            hammer = other
    return played


def _hammer_after(games, first: str) -> str:
    """Who has the hammer in the end after the last of `games`."""
    hammer = first
    for scorer, _, _ in games:
        if scorer == hammer:
            hammer = "away" if hammer == "home" else "home"
    return hammer


def _totals(games) -> dict[str, int]:
    return {side: sum(pts for scorer, pts, _ in games if scorer == side) for side in SIDES}


def _extra(rng, hammer: str, winner: str) -> dict:
    """Extra ends: an occasional blank one (the hammer stays), then the end the winner scores in."""
    blanks = rng.choices([0, 1, 2], [78, 19, 3])[0]
    if winner == hammer:
        points = rng.choices([1, 2, 3], [62, 30, 8])[0]
    else:
        points = rng.choices([1, 2], [92, 8])[0]                 # a steal
    return {side: [0] * blanks + [points if side == winner else 0] for side in SIDES}


# ------------------------------------------------------------------ the lineups

def _lineups(rng, game: SampleGame, ctx: SportContext) -> dict:
    """Each rink's lineup in throwing order: its regulars by position, a spare in place of the regular they
    replaced (`spare_for`), and, on a draft, one spare written in by name with no player id yet."""
    positions = ctx.sport.get("positions") or list(POSITIONS)
    rows = {}
    for side in SIDES:
        team = ctx.sides[side]
        ids = list(game.players.get(side, []))
        regulars = [p for p in ids if ctx.players[p].team == team and not ctx.players[p].sub]
        spares = [p for p in ids if p not in regulars]
        regulars.sort(key=lambda p: positions.index(ctx.players[p].position) if ctx.players[p].position in positions
                      else len(positions))
        seen = set()                                    # one player to a position (a rink is lead, second, vice, skip)
        regulars = [p for p in regulars if not (ctx.players[p].position in seen or seen.add(ctx.players[p].position))]
        line = [{"player": p, "position": ctx.players[p].position or positions[min(i, len(positions) - 1)]}
                for i, p in enumerate(regulars)]
        for spare in spares[:1]:                        # a spare takes the place of one regular (not the skip)
            gone = rng.randrange(max(1, len(line) - 1))
            line[gone] = {"player": spare, "position": line[gone]["position"], "spare_for": regulars[gone]}
        rows[side] = line
    if ctx.folder == "drafts":                          # one spare written in by hand: a name, no player id yet
        side = SIDES[zlib.crc32(game.game_id.encode()) % 2]
        if all("spare_for" not in row for row in rows[side]) and len(rows[side]) > 1:
            gone = zlib.crc32(game.game_id.encode()) % (len(rows[side]) - 1)
            name = SUB_NAMES[zlib.crc32(game.game_id.encode()) % len(SUB_NAMES)]
            rows[side][gone] = {"name": name, "position": rows[side][gone]["position"],
                                "spare_for": rows[side][gone]["player"]}
    return rows


def _int(value, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default
