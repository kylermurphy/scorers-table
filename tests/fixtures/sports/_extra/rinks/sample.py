"""Sample data for the throwaway Rinks sport: every optional constant of docs/sports.md is set."""
LEAGUE_NAME = "Example Rinks League"
TEAMS = [("ice-owls", "Ice Owls", "OWL"), ("sweepers", "Sweepers", "SWP"), ("hog-line", "Hog Line", "HOG"),
         ("pebble", "Pebble", "PEB")]
PLAYERS_PER_TEAM = 3
NUMBERS = False
POSITIONS = ["lead", "second", "skip"]
SURFACES = ["A", "B"]
TIMES = ["18:30", "20:45"]
NOTES = ["Ice was slow on sheet B."]


def sheet(rng, game, ctx):
    ends = ctx.options.get("ends", 4)
    for _ in range(500):
        periods = {s: [rng.choice([0, 0, 1, 2]) for _ in range(ends)] for s in ("home", "away")}
        total = {s: sum(v) for s, v in periods.items()}
        if (game.outcome == "tie" and ctx.game_type == "regular" and total["home"] == total["away"]) \
                or (game.outcome in ("win_home", "ot") and total["home"] > total["away"]) \
                or (game.outcome == "win_away" and total["away"] > total["home"]) \
                or (game.outcome == "tie" and ctx.game_type != "regular" and total["home"] > total["away"]):
            return {"periods": periods, "final": total,
                    "players": {s: list(game.players.get(s, [])) for s in ("home", "away") if game.players.get(s)}}
    raise RuntimeError(f"could not draw a sheet for the outcome {game.outcome!r}")
