"""Rules of the option-stats test sport: no checks. A sheet lists `batters` per side; with `batting: none` the
sheet keeps no batting line (nobody has a line), with `order` only the batting order (a line with no numbers)."""
from scripts.core.model import Line, Reading, Score


def check(sheet, ctx):
    return []


def read(sheet, ctx):
    final = sheet["final"]
    score = Score(final=dict(final), periods={"home": [final["home"]], "away": [final["away"]]},
                  final_at={"home": "sheet.final.home", "away": "sheet.final.away"})
    kept = ctx.options["batting"]
    lines = []
    if kept != "none":
        for side, rows in (sheet.get("batters") or {}).items():
            for row in rows:
                counts = {k: v for k, v in row.items() if k != "player"} if kept != "order" else {}
                lines.append(Line(side=side, player=row["player"], group="player", counts=counts))
    return Reading(score=score, lines=lines)


def present(reading, ctx):
    return {"blocks": []}


def derive(counts, group):
    ab, h = counts.get("ab", 0), counts.get("h", 0)
    return {"avg": h / ab if ab else None}
