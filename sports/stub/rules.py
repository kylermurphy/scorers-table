"""The rules of the stub sport (docs/stage-4-spec.md, section 3.7): check, read, present, derive.

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.model`, so the
stage 7 JavaScript port can match them line for line. `check` returns every problem, with paths relative to
`sheet` (the core adds `sheet.`), and never changes `sheet` or `ctx`.

The sheet:

    periods:  {home: [12, 9], away: [11, 10]}   # one whole number per period, per side
    overtime: {home: 3, away: 1}                # only when rules.overtime is "overtime" and regulation was tied
    final:    {home: 24, away: 22}              # the Final box as written
    players:                                    # optional: who played; pts optional per row
      home: [{player: ann-b, pts: 9}, {player: joe-k}]
      away: [{player: tom-w, pts: 4}]
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from scripts.core.model import Line, Problem, Reading, Score

SIDE_KEYS = ("home", "away")
SHEET_KEYS = ("periods", "overtime", "final", "players")
ROW_KEYS = ("player", "pts")
MAX_PERIOD = 99      # most points in one half or in overtime
MAX_PTS = 999        # most points for one player, or in the Final box


# ------------------------------------------------------------------ small helpers

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _whole(v, lo, hi):
    return _is_int(v) and lo <= v <= hi


def _path(*parts):
    return ".".join(str(p) for p in parts)


def _words(ctx):
    """('half', 'halves') from sport.yml, lower case."""
    period = ctx.sport["words"]["period"]
    return period["one"].lower(), period["many"].lower()


def _count(ctx):
    return ctx.options.get("periods", 2)


def _overtime_allowed(ctx):
    return ctx.options.get("overtime", "none") == "overtime"


class _Out:
    """Collects the problems of one check() call; `gap` is the level of a missing or empty box (a draft may
    leave boxes empty, a finished sheet may not)."""

    def __init__(self, ctx):
        self.problems = []
        self.gap = "warning" if ctx.folder == "drafts" else "error"

    def error(self, at, message):
        self.problems.append(Problem("error", at, message))

    def warning(self, at, message):
        self.problems.append(Problem("warning", at, message))

    def missing(self, at, what):
        self.problems.append(Problem(self.gap, at, f"is empty. Fill in {what}."))


def _sides_block(out, raw, at, what):
    """`raw` must be a block with only home/away keys. Returns it (or None), reporting the rest."""
    if not isinstance(raw, dict):
        out.error(at, f"must list {what} for home and away, like 'home: ...' and 'away: ...'.")
        return None
    for key in raw:
        if key not in SIDE_KEYS:
            out.error(_path(at, key), f"{str(key)!r} is not a side. Use 'home' or 'away'.")
    return raw


# ------------------------------------------------------------------ check

def check(sheet, ctx):
    if not isinstance(sheet, dict):
        return [Problem("error", "", "The sheet must be a block with these lines: " + ", ".join(SHEET_KEYS) + ".")]
    out = _Out(ctx)
    for key in sheet:
        if key not in SHEET_KEYS:
            out.error(str(key), f"{str(key)!r} is not a box on the stub sheet. Use one of: {', '.join(SHEET_KEYS)}.")
    regulation = _check_periods(out, sheet, ctx)
    overtime = _check_overtime(out, sheet, ctx, regulation)
    final = _check_final(out, sheet, ctx, regulation, overtime)
    _check_players(out, sheet, ctx, final)
    return out.problems


def _check_periods(out, sheet, ctx):
    """Returns {side: [numbers]} for each side whose periods are all good."""
    one, many = _words(ctx)
    count = _count(ctx)
    raw = sheet.get("periods")
    good = {}
    if raw is None:
        for side in SIDE_KEYS:
            out.missing(_path("periods", side), f"the points for each {one}")
        return good
    if _sides_block(out, raw, "periods", f"the points for each {one}") is None:
        return good
    for side in SIDE_KEYS:
        at = _path("periods", side)
        value = raw.get(side)
        if value is None:
            out.missing(at, f"the points for each {one}")
        elif not isinstance(value, list):
            out.error(at, f"must be a list of {count} whole numbers, one per {one}, like [12, 9].")
        elif len(value) != count:
            out.error(at, f"must have exactly {count} numbers (one per {one}), but has {len(value)}.")
        else:
            ok = True
            for i, points in enumerate(value):
                if points is None:
                    out.missing(_path(at, i), f"the points for {one} {i + 1}")
                    ok = False
                elif not _whole(points, 0, MAX_PERIOD):
                    out.error(_path(at, i), f"must be a whole number from 0 to {MAX_PERIOD}, not {points!r}.")
                    ok = False
            if ok:
                good[side] = list(value)
    return good


def _check_overtime(out, sheet, ctx, regulation):
    """Returns {side: points} for each side whose overtime points are good."""
    if "overtime" not in sheet:
        return {}
    one, many = _words(ctx)
    if not _overtime_allowed(ctx):
        out.error("overtime", "is not allowed: the league's rules have no overtime. Delete the overtime lines, "
                              "or set the overtime rule in league.yml.")
        raw = sheet["overtime"]      # its numbers still count in the Final box check, so there is one clear error
        return {side: raw[side] for side in SIDE_KEYS if isinstance(raw, dict) and _whole(raw.get(side), 0, MAX_PERIOD)}
    if len(regulation) == 2:
        home, away = sum(regulation["home"]), sum(regulation["away"])
        if home != away:
            out.error("overtime", f"is only played when the {many} end level, but they add up to {home}-{away}. "
                                  "Delete the overtime lines.")
    raw = sheet["overtime"]
    good = {}
    if raw is None:
        for side in SIDE_KEYS:
            out.missing(_path("overtime", side), "the overtime points")
        return good
    if _sides_block(out, raw, "overtime", "the overtime points") is None:
        return good
    for side in SIDE_KEYS:
        at = _path("overtime", side)
        value = raw.get(side)
        if value is None:
            out.missing(at, "the overtime points")
        elif not _whole(value, 0, MAX_PERIOD):
            out.error(at, f"must be a whole number from 0 to {MAX_PERIOD}, not {value!r}.")
        else:
            good[side] = value
    if len(good) == 2 and good["home"] == good["away"]:
        out.error("overtime.home", f"is still tied {good['home']}-{good['away']}: one side must score more in overtime.")
    return good


def _check_final(out, sheet, ctx, regulation, overtime):
    """Returns {side: number} for each side whose Final box is a whole number."""
    one, many = _words(ctx)
    raw = sheet.get("final")
    good = {}
    if raw is None:
        for side in SIDE_KEYS:
            out.missing(_path("final", side), "the Final box")
        return good
    if _sides_block(out, raw, "final", "the Final box") is None:
        return good
    for side in SIDE_KEYS:
        at = _path("final", side)
        value = raw.get(side)
        if value is None:
            out.missing(at, "the Final box")
            continue
        if not _whole(value, 0, MAX_PTS):
            out.error(at, f"must be a whole number from 0 to {MAX_PTS}, not {value!r}.")
            continue
        good[side] = value
        with_overtime = "overtime" in sheet
        if side in regulation and (not with_overtime or side in overtime):
            total = sum(regulation[side]) + (overtime[side] if with_overtime else 0)
            if value != total:
                out.error(at, f"the Final box says {value}, but the {many}"
                              f"{' and overtime' if with_overtime else ''} add up to {total}")
    return good


def _check_players(out, sheet, ctx, final):
    raw = sheet.get("players")
    if raw is None:
        return
    if _sides_block(out, raw, "players", "who played") is None:
        return
    seen = {}
    for side in SIDE_KEYS:
        rows = raw.get(side)
        at = _path("players", side)
        if rows is None:
            continue
        if not isinstance(rows, list):
            out.error(at, "must be a list, one '- player: ann-b, pts: 9' line per player.")
            continue
        sums, all_have_pts = 0, bool(rows)
        for i, row in enumerate(rows):
            row_at = _path(at, i)
            if not isinstance(row, dict):
                out.error(row_at, "must be a block like {player: ann-b, pts: 9}.")
                all_have_pts = False
                continue
            for key in row:
                if key not in ROW_KEYS:
                    out.error(_path(row_at, key), f"{str(key)!r} is not a box in a player row. Use 'player' or 'pts'.")
            _check_player_id(out, row, row_at, side, ctx, seen)
            pts = row.get("pts")
            if pts is None:
                all_have_pts = False
            elif not _whole(pts, 0, MAX_PTS):
                out.error(_path(row_at, "pts"), f"must be a whole number from 0 to {MAX_PTS}, not {pts!r}.")
                all_have_pts = False
            else:
                sums += pts
        if all_have_pts and side in final and sums != final[side]:
            out.warning(at, f"the players' points add up to {sums}, but the Final box says {final[side]}")


def _check_player_id(out, row, row_at, side, ctx, seen):
    at = _path(row_at, "player")
    pid = row.get("player")
    if pid is None:
        out.missing(at, "the player's id from players.yml")
        return
    if not isinstance(pid, str) or pid not in ctx.players:
        out.error(at, f"{pid!r} is not a player id in players.yml.")
        return
    if pid in seen:
        out.error(at, f"{pid!r} is listed twice in this game (also at {seen[pid]}).")
    else:
        seen[pid] = at
    player = ctx.players[pid]
    side_team = ctx.sides.get(side)
    if not player.sub and player.team != side_team:
        out.warning(at, f"{player.label} is not on this side's team ({side_team}). "
                        "If a spare filled in, mark them sub: true in players.yml.")


# ------------------------------------------------------------------ read

def read(sheet, ctx):
    overtime = sheet.get("overtime")
    score = Score(
        final={side: sheet["final"][side] for side in SIDE_KEYS},
        periods={side: list(sheet["periods"][side]) for side in SIDE_KEYS},
        extra={side: [overtime[side]] for side in SIDE_KEYS} if overtime else {},
        decided_in="overtime" if overtime else "regulation",
        final_at={side: f"sheet.final.{side}" for side in SIDE_KEYS})
    lines = []
    for side in SIDE_KEYS:
        for row in (sheet.get("players") or {}).get(side) or []:
            lines.append(Line(side=side, player=row["player"], group="player", counts={"pts": row.get("pts") or 0}))
    return Reading(score=score, lines=lines, team_lines={}, facts={})


# ------------------------------------------------------------------ present

def present(reading, ctx):
    score = reading.score
    short = ctx.sport["words"]["period"]["short"]
    one = ctx.sport["words"]["period"]["one"].lower()
    line = ctx.sport["line_score"]
    count = len(score.periods["home"])
    labels = [f"{short}{i + 1}" for i in range(count)]
    cells = {side: [{"v": v} for v in score.periods[side]] for side in SIDE_KEYS}
    if score.extra:
        labels.append("OT")
        for side in SIDE_KEYS:
            cells[side].append({"v": sum(score.extra[side])})
    for i in range(len(labels)):
        home, away = cells["home"][i]["v"], cells["away"][i]["v"]
        if home != away:
            cells["home" if home > away else "away"][i]["won"] = True
    line_score = {
        "shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
        "columns": [{"label": label} for label in labels],
        "rows": {side: {"cells": cells[side], "total": score.final[side], "extra": None, "hammer_first": False}
                 for side in SIDE_KEYS},
        "mark_word": None, "won_word": f"won the {one}", "legend": [], "note": None}

    top = None
    for ln in reading.lines:
        if ln.counts.get("pts", 0) > 0 and (top is None or ln.counts["pts"] > top.counts["pts"]):
            top = ln
    if top is not None:
        label = _label(ctx, top.player)
        card = {"note": f"Top: {label} {top.counts['pts']} pts", "strong": label, "link_label": "Box score"}
    else:
        card = {"note": None, "strong": None, "link_label": "Box score"}

    blocks = []
    for side in SIDE_KEYS:
        rows = [ln for ln in reading.lines if ln.side == side]
        if not rows:
            continue
        blocks.append({
            "type": "stat_table", "title": None, "side": side, "caption": f"{_team_name(ctx, side)} box score",
            "number_col": True,
            "columns": [{"key": "pts", "label": "PTS", "title": "Points", "key_col": True}],
            "rows": [{"player": ln.player, "cells": {"pts": str(ln.counts.get("pts", 0))}} for ln in rows],
            "totals": {"label": f"Team · {len(rows)} played", "cells": {"pts": str(score.final[side])}},
            "note": None})
    blocks.append({"type": "note", "text": "Points come from the Final box and each player's row."})
    return {"line_score": line_score, "card": card, "tiles": [], "blocks": blocks}


def _label(ctx, player_id):
    player = ctx.players.get(player_id)
    return player.label if player else player_id


def _team_name(ctx, side):
    team = ctx.teams.get(ctx.sides.get(side))
    return team.name if team else side.capitalize()


# ------------------------------------------------------------------ derive

def derive(counts, group):
    """Rates from summed counts (one game or a season): points per game, one decimal, half up."""
    games = counts.get("gp", 0)
    if not games:
        return {"ppg": None}
    value = Decimal(counts.get("pts", 0)) / Decimal(games)
    return {"ppg": float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))}
