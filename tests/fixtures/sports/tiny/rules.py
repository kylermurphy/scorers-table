"""The rules of the tiny test sport: the four functions with the right shapes and no real rules."""
from scripts.core.model import Reading, Score


def check(sheet, ctx):
    return []


def read(sheet, ctx):
    return Reading(score=Score(final={"home": 0, "away": 0}, periods={"home": [], "away": []},
                               final_at={"home": "sheet.final.home", "away": "sheet.final.away"}))


def present(reading, ctx):
    return {"blocks": []}


def derive(counts, group):
    return {}
