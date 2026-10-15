"""Sample data for the stub sport: made-up team names and one function that writes a believable sheet.

`scripts/make_sample.py` does the rest (players, schedule, outcomes) with a fixed seed. Nothing here looks
like a real league: the names are animals, the league is "Example Valley".
"""
from __future__ import annotations

from scripts.core.model import SampleGame, SportContext

LEAGUE_NAME = "Example Valley Stub League"
TEAMS = [("otters", "Otters", "OTT"), ("ravens", "Ravens", "RAV"), ("badgers", "Badgers", "BAD"),
         ("moose", "Moose", "MOO"), ("lynx", "Lynx", "LYN")]
PLAYERS_PER_TEAM = 7       # read by make_sample.py (optional; 7 is its default too)

_SIDES = ("home", "away")


def sheet(rng, game: SampleGame, ctx: SportContext) -> dict:
    """A stub sheet that passes check() and ends the way `game.outcome` asks. The outcome is bent to what the
    league's rules allow: no overtime means "ot" becomes a tie (a win in the playoffs, which never tie), and
    with overtime a tie becomes "ot"."""
    count = ctx.options.get("periods", 2)
    overtime_on = ctx.options.get("overtime", "none") == "overtime"
    outcome = game.outcome
    if outcome == "tie" and overtime_on:
        outcome = "ot"
    if outcome == "ot" and not overtime_on:
        outcome = "tie"
    if outcome == "tie" and ctx.game_type != "regular":
        outcome = "win_home"

    periods = _periods(rng, count, outcome)
    final = {side: sum(periods[side]) for side in _SIDES}
    sheet_: dict = {"periods": periods}
    if outcome == "ot":
        home = rng.randint(2, 9)
        away = rng.choice([n for n in range(2, 10) if n != home])
        sheet_["overtime"] = {"home": home, "away": away}
        final = {"home": final["home"] + home, "away": final["away"] + away}
    sheet_["final"] = final
    players = {side: _rows(rng, game.players.get(side, []), final[side]) for side in _SIDES}
    players = {side: rows for side, rows in players.items() if rows}
    if players:
        sheet_["players"] = players
    return sheet_


def _periods(rng, count: int, outcome: str) -> dict:
    for _ in range(500):
        home = [rng.randint(4, 18) for _ in range(count)]
        away = [rng.randint(4, 18) for _ in range(count)]
        if outcome in ("tie", "ot"):
            away[-1] = sum(home) - sum(away[:-1])      # level after regulation
            if not 0 <= away[-1] <= 99:
                continue
        elif outcome == "win_home" and not sum(home) > sum(away):
            continue
        elif outcome == "win_away" and not sum(away) > sum(home):
            continue
        return {"home": home, "away": away}
    raise RuntimeError(f"could not draw a sheet for the outcome {outcome!r}")


def _rows(rng, player_ids: list, total: int) -> list:
    """One row per player; their points add up to the side's Final box (shares by random weight, the
    leftover points going to the player with the largest share)."""
    if not player_ids:
        return []
    weights = [rng.random() + 0.15 for _ in player_ids]
    points = [int(total * w / sum(weights)) for w in weights]
    points[weights.index(max(weights))] += total - sum(points)
    return [{"player": pid, "pts": pts} for pid, pts in zip(player_ids, points)]
