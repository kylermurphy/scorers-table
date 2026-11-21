"""Rules of the two-group test sport: no checks, a sheet is read as written."""
from scripts.core.model import Line, Reading, Score


def check(sheet, ctx):
    return []


def read(sheet, ctx):
    final = sheet["final"]
    score = Score(final=dict(final), periods={"home": [final["home"]], "away": [final["away"]]},
                  decided_in=sheet.get("decided", "regulation"),
                  final_at={"home": "sheet.final.home", "away": "sheet.final.away"})
    lines = []
    for key, group in (("skaters", "skater"), ("goalies", "goalie")):
        for side, rows in (sheet.get(key) or {}).items():
            for row in rows:
                counts = {k: v for k, v in row.items() if k != "player"}
                lines.append(Line(side=side, player=row["player"], group=group, counts=counts))
    return Reading(score=score, lines=lines)


def present(reading, ctx):
    return {"blocks": []}


def derive(counts, group):
    if group != "goalie":
        return {}
    gp, ga, sa = counts["gp"], counts.get("ga", 0), counts.get("sa", 0)
    return {"gaa": ga / gp if gp else None, "sv": (sa - ga) / sa if sa else None}
