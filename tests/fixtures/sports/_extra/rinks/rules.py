"""The rules of the throwaway Rinks sport: a few ends, a Final box, and who played. No counting stats at all.

    periods: {home: [1, 0, 2, 0], away: [0, 1, 0, 1]}
    final:   {home: 3, away: 2}
    players: {home: [ann-b, joe-k], away: [tom-w]}
"""
from scripts.core.model import Line, Problem, Reading, Score

SIDES = ("home", "away")


def check(sheet, ctx):
    out = []
    if not isinstance(sheet, dict):
        return [Problem("error", "", "must be a sheet with periods, final and players.")]
    ends = ctx.options.get("ends", 4)
    periods, final = sheet.get("periods"), sheet.get("final")
    for side in SIDES:
        row = periods.get(side) if isinstance(periods, dict) else None
        if not (isinstance(row, list) and len(row) == ends and all(isinstance(v, int) and v >= 0 for v in row)):
            out.append(Problem("error", f"periods.{side}", f"must list {ends} whole numbers, one for each end."))
        elif not isinstance(final, dict) or final.get(side) != sum(row):
            out.append(Problem("error", f"final.{side}", f"must be {sum(row)}, the total of the ends."))
        who = (sheet.get("players") or {}).get(side)
        for i, pid in enumerate(who or []):
            if pid not in ctx.players:
                out.append(Problem("error", f"players.{side}.{i}", f"{pid!r} is not a player id in players.yml."))
    return out


def read(sheet, ctx):
    score = Score(final={s: sheet["final"][s] for s in SIDES}, periods={s: list(sheet["periods"][s]) for s in SIDES},
                  final_at={s: f"sheet.final.{s}" for s in SIDES})
    lines = [Line(side=s, player=pid, group="player", counts={}) for s in SIDES
             for pid in (sheet.get("players") or {}).get(s) or []]
    return Reading(score=score, lines=lines)


def present(reading, ctx):
    score = reading.score
    cells = {s: [{"v": v} for v in score.periods[s]] for s in SIDES}
    line = ctx.sport["line_score"]
    line_score = {
        "shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
        "columns": [{"label": f"E{i + 1}"} for i in range(len(cells["home"]))],
        "rows": {s: {"cells": cells[s], "total": score.final[s], "extra": None, "hammer_first": False} for s in SIDES},
        "mark_word": None, "won_word": "won the end", "legend": [], "note": None}
    return {"line_score": line_score, "card": {"note": None, "strong": None, "link_label": "Game"}, "tiles": [],
            "blocks": [{"type": "note", "text": "Nobody counts anything here: only who played."}]}


def derive(counts, group):
    return {}
