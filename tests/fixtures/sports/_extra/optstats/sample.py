"""Sample data for the option-stats test sport (never built: it is a test sport)."""
LEAGUE_NAME = "Example Optstats League"
TEAMS = [("alpha", "Alpha", "ALP"), ("bravo", "Bravo", "BRA")]


def sheet(rng, game, ctx):
    return {"final": {"home": 1, "away": 0}}
