"""The rules of basketball (docs/stage-5-basketball-spec.md, sections 2-4): check, read, present, derive.

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.model`, so the
stage 7 JavaScript port can match them line for line. `check` returns every problem, with paths relative to
`sheet` (the core adds `sheet.`), and never changes `sheet` or `ctx`.

The sheet is a box-for-box copy of the paper running-score sheet:

    players:                        # the roster rows, top to bottom: players.home.0 is row 1
      home:
        - {player: dave-m, num: 23, here: true, ft: MMXM, fouls: 2, tech: 1}
        - {num: 31, name: Jim K., here: true}        # a sub written in by hand (a draft only)
      away: [...]
    running:                        # the running score: the team's new total -> the scorer's jersey number
      home: {2: 23, 4: 11}
      away: {3: 7}
    lines:                          # the running total each end-of-quarter line is drawn under
      home: [5, 7, 10, 12]
      away: [3, 6, 8, 10]
    boxes:                          # the score boxes under each roster, as written
      home: {q1: 5, q2: 7, q3: 10, q4: 12, ot: null, final: 12}
      away: {q1: 3, q2: 6, q3: 8, q4: 10, ot: null, final: 10}
    notes:                          # the Notes box
      - {side: away, num: 7, q: 3, kind: flagrant, text: elbow on a rebound}

How the numbers come from it: points from the running score (each jump of 1, 2 or 3 goes to the jersey number in
the box); FTM and FTA from the free-throw circles, never the running score; GP from the Here tick; PF and T from
the foul and technical boxes; flagrants from Notes; quarter scores from the differences of the quarter boxes.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from scripts.core.model import Line, Problem, Reading, Score

SIDES = ("home", "away")
SHEET_KEYS = ("players", "running", "lines", "boxes", "notes")
ROW_KEYS = ("player", "name", "num", "here", "ft", "fouls", "tech")
NOTE_KEYS = ("side", "num", "q", "kind", "text")
NOTE_KINDS = ("flagrant", "note")
MAX_ROWS = 15          # roster rows on a sheet (a sanity limit until a printed sheet supplies its own)
MAX_CIRCLES = 20       # free-throw circles for one player
MAX_TECH = 2           # technical-foul boxes for one player
MAX_TOTAL = 250        # the most a running score holds
DEFAULT_PERIODS = 4
DEFAULT_FOUL_LIMIT = 5
FT_RE = re.compile(r"[MX]*")
JERSEY_RE = re.compile(r"[0-9]{1,2}")


# ------------------------------------------------------------------ small helpers

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _count(v):
    return _is_int(v) and v >= 0


def _jersey(num):
    """A jersey number as text ("4", "00"), or None if it is not one."""
    if _is_int(num):
        num = str(num)
    if isinstance(num, str) and JERSEY_RE.fullmatch(num.strip()):
        return num.strip()
    return None


def _periods(ctx):
    """How many quarters a game has (sport.yml line_score.periods)."""
    value = ctx.sport.get("line_score", {}).get("periods", DEFAULT_PERIODS)
    if isinstance(value, str):
        value = ctx.options.get(value, DEFAULT_PERIODS)
    return value if _is_int(value) and value > 0 else DEFAULT_PERIODS


def _box_keys(ctx):
    """The quarter boxes' keys: the period word's short form, lower case, then the number (q1, q2, q3, q4)."""
    short = ctx.sport["words"]["period"]["short"].lower()
    return [f"{short}{n}" for n in range(1, _periods(ctx) + 1)]


def _foul_limit(ctx):
    v = ctx.options.get("foul_limit", DEFAULT_FOUL_LIMIT)
    return v if _is_int(v) else DEFAULT_FOUL_LIMIT


def _overtime_allowed(ctx):
    return ctx.options.get("overtime", "overtime") == "overtime"


def _team_name(ctx, side):
    team = ctx.teams.get(ctx.sides.get(side))
    return team.name if team else side.capitalize()


def _player_label(ctx, player_id):
    player = ctx.players.get(player_id) if isinstance(player_id, str) else None
    return player.label if player else str(player_id)


def _path(*parts):
    return ".".join(str(p) for p in parts)


def _total_order(total):
    """Running-score keys in order: whole numbers by size, anything else after them."""
    return (not _is_int(total), total if _is_int(total) else 0)


class _Out:
    """Collects the problems of one check() call. `gap` is the level of a box left empty: a draft may do it,
    a finished sheet may not."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.problems = []
        self.gap = "warning" if ctx.folder == "drafts" else "error"

    def error(self, at, message):
        self.problems.append(Problem("error", at, message))

    def warning(self, at, message):
        self.problems.append(Problem("warning", at, message))

    def empty(self, at, message):
        self.problems.append(Problem(self.gap, at, message))

    def team(self, side):
        return _team_name(self.ctx, side)


# ------------------------------------------------------------------ check

def check(sheet, ctx):
    if not isinstance(sheet, dict):
        return [Problem("error", "", "the sheet should be a block with these lines: " + ", ".join(SHEET_KEYS) + ".")]
    out = _Out(ctx)
    for key in sheet:
        if key not in SHEET_KEYS:
            out.error(str(key), f"'{key}' isn't part of a score sheet. Use one of: {', '.join(SHEET_KEYS)}.")
    roster = _check_players(out, sheet)
    if roster is None:
        return out.problems
    rows, by_num = roster
    running = _check_running(out, sheet, rows, by_num)
    if running is None:
        return out.problems
    pts_jumps, last, totals_seen = running
    _check_free_throws(out, rows, pts_jumps)
    ends = _check_boxes(out, sheet, last, totals_seen)
    if ends is not None:
        _check_overtime(out, ends)
    _check_notes(out, sheet, rows, by_num)
    return out.problems


def _sides_block(out, value, at, what):
    """`value` must be a block with only home and away in it. Returns it, or None (after reporting) when it is
    missing or not a block. Unknown sides are reported and skipped."""
    if value is None:
        out.empty(at, f"is empty. Fill in {what}, for home and away.")
        return None
    if not isinstance(value, dict):
        out.error(at, f"should list {what} for home and away, like 'home: ...' and 'away: ...'.")
        return None
    for key in value:
        if key not in SIDES:
            out.error(_path(at, key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    return value


def _check_players(out, sheet):
    """Returns ({side: [(row index, row, jersey, circles)]}, {side: {jersey: row index}}), or None when the
    rosters are missing and the later checks mean nothing."""
    block = _sides_block(out, sheet.get("players"), "players", "each team's roster rows")
    if block is None:
        return None
    rows, by_num, seen_players, stop = {}, {}, {}, False
    for side in SIDES:
        team = out.team(side)
        base = _path("players", side)
        rows[side], by_num[side] = [], {}
        listed = block.get(side)
        if listed is None:
            out.empty(base, f"is empty. List {team}'s players, one per roster row.")
            stop = True
            continue
        if not isinstance(listed, list) or not listed:
            out.error(base, f"list {team}'s players, one per roster row")
            continue
        if len(listed) > MAX_ROWS:
            out.error(base, f"{team} has {len(listed)} rows; the sheet has {MAX_ROWS}")
        for i, row in enumerate(listed):
            at = _path(base, i)
            if not isinstance(row, dict):
                out.error(at, "a row looks like {player: dave-m, num: 4, here: true, ft: MMX, fouls: 2}")
                continue
            for key in row:
                if key not in ROW_KEYS:
                    out.error(_path(at, key), f"'{key}' isn't part of a roster row")
            num = _jersey(row.get("num"))
            if num is None:
                out.error(_path(at, "num"), f"jersey number {row.get('num')!r} should be 0 to 99 (or \"00\")")
            elif num in by_num[side]:
                out.error(_path(at, "num"), f"#{num} is on two {team} rows (rows {by_num[side][num] + 1} and {i + 1}); "
                                            "the running score can't tell them apart")
            else:
                by_num[side][num] = i
            _check_player_id(out, row, at, side, num, seen_players)
            if not isinstance(row.get("here"), bool):
                out.error(_path(at, "here"), "here should be true (ticked) or false")
            ft = row.get("ft", "")
            if not isinstance(ft, str) or not FT_RE.fullmatch(ft):
                out.error(_path(at, "ft"), f"ft {ft!r} should be the circles in order: M for made (filled), "
                                           "X for missed (slashed), like MMXM")
                ft = ""
            elif len(ft) > MAX_CIRCLES:
                out.error(_path(at, "ft", MAX_CIRCLES), f"{len(ft)} free throws; the sheet has {MAX_CIRCLES} circles")
            for key, most in (("fouls", _foul_limit(out.ctx)), ("tech", MAX_TECH)):
                v = row.get(key, 0)
                if not _count(v) or v > most:
                    out.error(_path(at, key), f"{key} {v!r} should be a whole number from 0 to {most}")
            rows[side].append((i, row, num, ft))
        if not any(row.get("here") is True for _, row, _, _ in rows[side]):
            out.error(base, f"nobody on {team} is ticked Here")
    return None if stop else (rows, by_num)


def _check_player_id(out, row, at, side, num, seen):
    ctx = out.ctx
    pid = row.get("player")
    pat = _path(at, "player")
    if pid is None:
        who = row.get("name") or f"#{num}"
        out.empty(pat, f"{who} isn't matched to a player id yet. Pick one from players.yml, or add them there "
                       "first (a spare gets sub: true)")
        return
    if not isinstance(pid, str) or pid not in ctx.players:
        out.error(pat, f"player {pid!r} is not in players.yml")
        return
    if pid in seen:
        out.error(pat, f"{pid} is listed twice in this game (also at sheet.{seen[pid]})")
        return
    seen[pid] = pat
    player = ctx.players[pid]
    if not player.sub and player.team != ctx.sides.get(side):
        out.warning(pat, f"{player.label} is not on {out.team(side)}. If a spare filled in, mark them sub: true "
                         "in players.yml")


def _check_running(out, sheet, rows, by_num):
    """Returns ({side: {row index: scoring jumps}}, {side: last total}, {side: totals with a box}), or None."""
    block = _sides_block(out, sheet.get("running"), "running", "the running score")
    if block is None:
        return None
    stop = False
    for side in SIDES:
        value = block.get(side)
        if value is None:
            out.empty(_path("running", side), f"is empty. Fill in {out.team(side)}'s running score, like {{2: 4, 5: 10}}.")
            stop = True
        elif not isinstance(value, dict):
            out.error(_path("running", side), "the running score is total: jersey number, like {2: 4, 5: 10}")
            stop = True
    if stop:
        return None
    jumps, last, totals_seen = {}, {}, {}
    for side in SIDES:
        team = out.team(side)
        by_row = {i: row for i, row, _, _ in rows[side]}
        boxes = block[side]
        jumps[side], prev, totals = {}, 0, []
        for total in sorted(boxes, key=_total_order):
            at = _path("running", side, total)
            if not _is_int(total) or not 1 <= total <= MAX_TOTAL:
                out.error(at, f"{total!r} isn't a running-score box (1 to {MAX_TOTAL})")
                continue
            jump = total - prev
            if not 1 <= jump <= 3:
                out.error(at, f"{team} goes from {prev} to {total}, a jump of {jump}; a score is 1, 2 or 3")
            num = _jersey(boxes[total])
            if num is None:
                out.error(at, f"{boxes[total]!r} isn't a jersey number")
            elif num not in by_num[side]:
                out.error(at, f"#{num} scored for {team}, but no {team} row has #{num}")
            else:
                i = by_num[side][num]
                row = by_row[i]
                if row.get("here") is not True:
                    out.error(at, f"#{num} scored, but row {i + 1} ({row.get('player') or row.get('name') or '#' + num}) "
                                  "isn't ticked Here")
                if 1 <= jump <= 3:
                    jumps[side][i] = jumps[side].get(i, 0) + 1
            totals.append(total)
            prev = total
        last[side] = prev
        totals_seen[side] = set(totals) | {0}
    return jumps, last, totals_seen


def _check_free_throws(out, rows, jumps):
    """Made circles cannot outnumber the player's scores in the running score (a warning: worth a look)."""
    for side in SIDES:
        for i, row, num, ft in rows[side]:
            made, scores = ft.count("M"), jumps[side].get(i, 0)
            if made > scores:
                out.warning(_path("players", side, i, "ft"),
                            f"{made} free throws made, but the running score has {scores} score{'' if scores == 1 else 's'} "
                            f"for #{num}")


def _check_boxes(out, sheet, last, totals_seen):
    """The quarter lines and score boxes. Returns {side: {"q": [...], "ot": box, "final": last total}}, or None
    when a quarter box is not a count (the later checks would only repeat it)."""
    ctx = out.ctx
    keys = _box_keys(ctx)
    block = _sides_block(out, sheet.get("boxes"), "boxes", "the score boxes")
    if block is None:
        return None
    lines = sheet.get("lines")
    lines_bad = lines is not None and not isinstance(lines, dict)
    if lines is None:
        out.empty("lines", "is empty. Give the running total each end-of-quarter line was drawn under, for home and away, "
                           f"like 'home: [{', '.join(k.upper() for k in keys)}]'")
    elif lines_bad:
        out.error("lines", "should list each team's end-of-quarter lines for home and away, like 'home: [5, 12, 17, 22]'")
    else:
        for key in lines:
            if key not in SIDES:
                out.error(_path("lines", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    stop, ends = False, {}
    for side in SIDES:
        team = out.team(side)
        box = block.get(side)
        if box is None:
            out.empty(_path("boxes", side), f"is empty. Fill in {team}'s score boxes: {', '.join(keys)}, ot and final.")
            stop = True
            continue
        if not isinstance(box, dict):
            out.error(_path("boxes", side), f"{team}'s score boxes look like {{{', '.join(k + ': ..' for k in keys)}, ot: null, final: ..}}")
            stop = True
            continue
        for key in box:
            if key not in (*keys, "ot", "final"):
                out.error(_path("boxes", side, key), f"'{key}' isn't a score box. Use {', '.join(keys)}, ot or final.")
        line = []
        if lines is not None and not lines_bad:
            given = lines.get(side)
            if given is None:
                out.empty(_path("lines", side), f"where were {team}'s end-of-quarter lines drawn? "
                                                f"Give the running total at each: [{', '.join(k.upper() for k in keys)}]")
            elif not isinstance(given, list) or len(given) != len(keys) or not all(_count(x) for x in given):
                out.error(_path("lines", side), f"lines for {team} should be {len(keys)} running totals, one per quarter")
            else:
                line = given
        for q, x in enumerate(line):
            if x not in totals_seen[side]:
                out.error(_path("lines", side, q), f"the {keys[q].upper()} line is under {x}, but {team} has no box with that total")
            if q and x < line[q - 1]:
                out.error(_path("lines", side, q), f"the {keys[q].upper()} line ({x}) is above the {keys[q - 1].upper()} line ({line[q - 1]})")
        quarters = []
        for q, key in enumerate(keys):
            v = box.get(key)
            if not _count(v):
                out.error(_path("boxes", side, key), f"the {key.upper()} box should hold {team}'s running total at the end of "
                                                    f"that quarter, not {v!r}")
                quarters.append(None)
                continue
            quarters.append(v)
            if q < len(line) and v != line[q]:
                out.error(_path("boxes", side, key), f"the {key.upper()} box says {v}, but the {key.upper()} line is under {line[q]}")
            if q and quarters[q - 1] is not None and v < quarters[q - 1]:
                out.error(_path("boxes", side, key), f"the {key.upper()} box ({v}) is less than {keys[q - 1].upper()} ({quarters[q - 1]})")
        final = box.get("final")
        if not _count(final):
            out.error(_path("boxes", side, "final"), f"the Final box should hold {team}'s final score, not {final!r}")
        elif final != last[side]:
            out.error(_path("boxes", side, "final"), f"the Final box says {final}, but the running score ends at {last[side]}")
        # From here on the running score is the final: a wrong Final box is one problem, not several.
        ends[side] = {"q": quarters, "ot": box.get("ot"), "final": last[side]}
    if stop or any(v is None for side in SIDES for v in ends[side]["q"]):
        return None
    return ends


def _check_overtime(out, ends):
    """Overtime against the quarter boxes and the final, and the tie that needs overtime."""
    ctx = out.ctx
    key4 = _box_keys(ctx)[-1]
    q4 = {s: ends[s]["q"][-1] for s in SIDES}
    final = {s: ends[s]["final"] for s in SIDES}
    # Overtime: a final above a tied Q4, or (a scoreless overtime) both OT boxes filled in.
    went_ot = any(q4[s] != final[s] for s in SIDES) or (q4["home"] == q4["away"] and all(ends[s]["ot"] is not None for s in SIDES))
    allowed = _overtime_allowed(ctx)
    for side in SIDES:
        team = out.team(side)
        ot = ends[side]["ot"]
        if q4[side] > final[side]:
            out.error(_path("boxes", side, key4), f"the {key4.upper()} box ({q4[side]}) is more than the Final box ({final[side]})")
        if not allowed:
            if ot is not None:
                out.error(_path("boxes", side, "ot"), "the OT box is filled in, but this league plays no overtime")
            elif q4[side] < final[side]:
                out.error(_path("boxes", side, key4), f"the {key4.upper()} box says {q4[side]}, but the running score ends at "
                                                      f"{final[side]} and this league plays no overtime: {key4.upper()} should equal "
                                                      "the final score")
        elif went_ot:
            if ot != final[side]:
                out.error(_path("boxes", side, "ot"), f"after overtime the OT box should hold {team}'s total, {final[side]}")
        elif ot is not None:
            out.error(_path("boxes", side, "ot"), f"the OT box is filled in, but {key4.upper()} already equals the final score")
    if allowed and went_ot and q4["home"] != q4["away"]:
        out.error(_path("boxes", "home", key4), f"{key4.upper()} ({out.team('home')} {q4['home']}, {out.team('away')} {q4['away']}) "
                                                "isn't tied, so there was no overtime: "
                                                f"{key4.upper()} should equal the final score")
    # Level after Q4 needs overtime. (Still level after overtime, and a tied playoff game, are the core's to report.)
    if allowed and final["home"] == final["away"] and not went_ot:
        out.error(_path("boxes", "home", "final"), f"the final score is tied {final['home']}-{final['away']} after {key4.upper()}; "
                                                   "a tied game goes to overtime (fill in the OT boxes)")


def _check_notes(out, sheet, rows, by_num):
    """Notes: the kinds, and each flagrant foul against a roster row and its foul boxes."""
    notes = sheet.get("notes")
    if notes is None:
        return
    if not isinstance(notes, list):
        out.error("notes", "notes should be a list, like - {side: away, num: 7, q: 3, kind: flagrant, text: elbow}")
        return
    periods = _periods(out.ctx)
    flagrants = {side: {} for side in SIDES}
    for n, note in enumerate(notes):
        at = _path("notes", n)
        if not isinstance(note, dict):
            out.error(at, "a note looks like {side: away, num: 7, q: 3, kind: flagrant, text: elbow}")
            continue
        for key in note:
            if key not in NOTE_KEYS:
                out.error(_path(at, key), f"'{key}' isn't part of a note. Use {', '.join(NOTE_KEYS)}.")
        kind = note.get("kind", "note")
        if kind not in NOTE_KINDS:
            out.error(_path(at, "kind"), f"kind should be flagrant or note, not {kind!r}")
        if kind != "flagrant":
            continue
        side, num = note.get("side"), _jersey(note.get("num"))
        if side not in SIDES:
            out.error(_path(at, "side"), f"side {side!r} should be home or away")
        elif num not in by_num[side]:
            out.error(_path(at, "num"), f"no {out.team(side)} row has #{note.get('num')}")
        else:
            i = by_num[side][num]
            flagrants[side][i] = flagrants[side].get(i, 0) + 1
        q = note.get("q")
        if not (q == "OT" or (_is_int(q) and 1 <= q <= periods)):
            out.error(_path(at, "q"), f"q should be the quarter, 1 to {periods} (or OT), not {q!r}")
    for side in SIDES:
        for i, row, _, _ in rows[side]:
            f, boxes = flagrants[side].get(i, 0), row.get("fouls", 0)
            if f and _count(boxes) and f > boxes:
                out.error(_path("players", side, i, "fouls"),
                          f"{f} flagrant foul{'s' if f > 1 else ''} in Notes, but only {boxes} foul box"
                          f"{'es' if boxes != 1 else ''} slashed; a flagrant is also a personal foul")


# ------------------------------------------------------------------ read

def read(sheet, ctx):
    """The numbers of a sheet `check` accepted (warnings allowed). Arithmetic only."""
    keys = _box_keys(ctx)
    rows, by_num, pts = {}, {}, {}
    for side in SIDES:
        rows[side] = [(i, row) for i, row in enumerate(sheet["players"][side])]
        by_num[side] = {_jersey(row.get("num")): i for i, row in rows[side]}
        pts[side] = {}
        prev = 0
        boxes = sheet["running"][side]
        for total in sorted(boxes):
            i = by_num[side].get(_jersey(boxes[total]))
            if i is not None:
                pts[side][i] = pts[side].get(i, 0) + total - prev
            prev = total
    final = {side: max(sheet["running"][side], default=0) for side in SIDES}
    quarters = {side: [sheet["boxes"][side][k] for k in keys] for side in SIDES}
    periods = {side: [q - (quarters[side][n - 1] if n else 0) for n, q in enumerate(quarters[side])] for side in SIDES}
    q4 = {side: quarters[side][-1] for side in SIDES}
    went_ot = any(q4[s] != final[s] for s in SIDES) or (
        q4["home"] == q4["away"] and all(sheet["boxes"][s].get("ot") is not None for s in SIDES))
    score = Score(final=final, periods=periods,
                  extra={s: [final[s] - q4[s]] for s in SIDES} if went_ot else {},
                  decided_in="overtime" if went_ot else "regulation",
                  final_at={s: f"sheet.boxes.{s}.final" for s in SIDES})
    flagrants = {side: {} for side in SIDES}
    flagrant_facts = []
    for note in sheet.get("notes") or []:
        if note.get("kind") != "flagrant":
            continue
        side = note["side"]
        i = by_num[side][_jersey(note["num"])]
        flagrants[side][i] = flagrants[side].get(i, 0) + 1
        row = sheet["players"][side][i]
        flagrant_facts.append({"side": side, "player": row.get("player"), "num": _jersey(note["num"]), "q": note["q"]})
    lines, technicals = [], []
    for side in SIDES:
        for i, row in rows[side]:
            if row.get("here") is not True or not row.get("player"):
                continue
            ft = row.get("ft", "")
            lines.append(Line(side=side, player=row["player"], group="player", counts={
                "pts": pts[side].get(i, 0), "ftm": ft.count("M"), "fta": len(ft), "pf": row.get("fouls", 0),
                "tech": row.get("tech", 0), "flagrant": flagrants[side].get(i, 0)}))
            if row.get("tech", 0):
                technicals.append({"side": side, "player": row["player"], "num": _jersey(row.get("num")), "count": row["tech"]})
    return Reading(score=score, lines=lines, team_lines={},
                   facts={"technicals": technicals, "flagrants": flagrant_facts})


# ------------------------------------------------------------------ present

CAPTION = "Points by quarter"
BIGGEST_WORD = "biggest quarter"
BIGGEST_LEGEND = "Biggest quarter for each team"
FOOTNOTE = "PF = personal fouls. Points come from the running score on the score sheet; free throws from its circles."


def present(reading, ctx):
    score = reading.score
    return {"line_score": _line_score(score, ctx), "card": _card(reading, ctx), "tiles": None,
            "blocks": _blocks(reading, ctx)}


def _line_score(score, ctx):
    short = ctx.sport["words"]["period"]["short"]
    line = ctx.sport["line_score"]
    count = len(score.periods["home"])
    labels = [f"{short}{n + 1}" for n in range(count)]
    cells = {}
    for side in SIDES:
        biggest = max(score.periods[side])
        cells[side] = [{"v": v, **({"won": True} if v == biggest and v > 0 else {})} for v in score.periods[side]]
    if score.extra:
        labels.append("OT")
        for side in SIDES:
            cells[side].append({"v": sum(score.extra[side])})
    return {
        "shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
        "columns": [{"label": label} for label in labels],
        "rows": {side: {"cells": cells[side], "total": score.final[side], "extra": None, "hammer_first": False}
                 for side in SIDES},
        "caption": CAPTION, "won_word": BIGGEST_WORD, "mark_word": None,
        "legend": [{"kind": "won", "text": BIGGEST_LEGEND}], "note": None}


def _top_scorers(reading):
    """The lines with the most points (all of them when tied); empty when nobody scored."""
    best = max((ln.counts["pts"] for ln in reading.lines), default=0)
    return [ln for ln in reading.lines if best > 0 and ln.counts["pts"] == best]


def _card(reading, ctx):
    top = _top_scorers(reading)
    card = {"note": None, "strong": None, "link_label": "Box score"}
    if not top:
        return card
    pts = top[0].counts["pts"]
    if len(top) == 1:
        who = _player_label(ctx, top[0].player)
        fta = top[0].counts["fta"]
        card["note"] = f"Top: {who} {pts} pts"
        card["note_long"] = f"Top scorer: {who} {pts} pts" + (f", {top[0].counts['ftm']}-{fta} FT" if fta else "")
    elif len(top) == 2:
        who = " and ".join(_player_label(ctx, ln.player) for ln in top)
        card["note"] = f"Top: {who} {pts} pts"
    else:
        who = f"{len(top)} players"
        card["note"] = f"{who} with {pts} pts"
    card["strong"] = who
    return card


def _blocks(reading, ctx):
    blocks = []
    top = _top_scorers(reading)
    if len(top) <= 2:
        for ln in top:
            fta = ln.counts["fta"]
            team = _team_name(ctx, ln.side)
            blocks.append({"type": "top_performer", "label": "Top scorer", "player": ln.player, "side": ln.side,
                           "value": ln.counts["pts"], "unit": "Points",
                           "detail": f"{team} · {ln.counts['ftm']}-{fta} free throws" if fta else team})
    for side in SIDES:
        block = _box_score(reading, ctx, side)
        if block:
            blocks.append(block)
    fouls = _fouls_note(reading, ctx)
    if fouls:
        blocks.append({"type": "note", "text": fouls})
    blocks.append({"type": "note", "text": FOOTNOTE})
    return blocks


def _box_score(reading, ctx, side):
    rows = [ln for ln in reading.lines if ln.side == side]
    if not rows:
        return None
    ftm = sum(ln.counts["ftm"] for ln in rows)
    fta = sum(ln.counts["fta"] for ln in rows)
    return {
        "type": "stat_table", "title": None, "side": side, "caption": f"{_team_name(ctx, side)} box score",
        "number_col": True,
        "columns": [{"key": "pts", "label": "PTS", "title": "Points", "key_col": True},
                    {"key": "ft", "label": "FTM-FTA", "title": "Free throws made-attempted", "key_col": False},
                    {"key": "pf", "label": "PF", "title": "Personal fouls", "key_col": False}],
        "rows": [{"player": ln.player,
                  "cells": {"pts": str(ln.counts["pts"]), "ft": f"{ln.counts['ftm']}-{ln.counts['fta']}",
                            "pf": str(ln.counts["pf"])}} for ln in rows],
        "totals": {"label": f"Team · {len(rows)} played",
                   "cells": {"pts": str(reading.score.final[side]), "ft": f"{ftm}-{fta}",
                             "pf": str(sum(ln.counts["pf"] for ln in rows))}},
        "note": f"Free throws {_percent(ftm, fta)}%" if fta else None}


def _percent(made, attempted):
    """100 x made / attempted, one decimal, half up."""
    return str((Decimal(100 * made) / Decimal(attempted)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _fouls_note(reading, ctx):
    """"Technical fouls: #7 Mike R. (Pines). Flagrant fouls: #7 Mike R. (Pines), Q3." Never the Notes text."""
    parts = []
    technicals = reading.facts.get("technicals") or []
    if technicals:
        parts.append("Technical fouls: " + "; ".join(
            f"{_player_label(ctx, t['player'])} ({_team_name(ctx, t['side'])})" + (f" ×{t['count']}" if t["count"] > 1 else "")
            for t in technicals) + ".")
    flagrants = reading.facts.get("flagrants") or []
    if flagrants:
        parts.append("Flagrant fouls: " + "; ".join(
            f"{_player_label(ctx, f['player']) if f.get('player') else '#' + str(f['num'])} ({_team_name(ctx, f['side'])}), "
            f"{'OT' if f['q'] == 'OT' else 'Q' + str(f['q'])}" for f in flagrants) + ".")
    return " ".join(parts)


# ------------------------------------------------------------------ derive

def derive(counts, group):
    """Rates from summed counts (one game or a season), unrounded: the core rounds them for display (half up) and
    ranks on the exact value. points per game; free throw percentage, None with no attempts."""
    games, attempts = counts.get("gp", 0), counts.get("fta", 0)
    return {"ppg": counts.get("pts", 0) / games if games else None,
            "ft_pct": 100 * counts.get("ftm", 0) / attempts if attempts else None}
