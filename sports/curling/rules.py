"""The rules of curling (docs/stage-5-curling-spec.md, sections 2-5): check, read, present, derive.

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.model`, so the
stage 7 JavaScript port can match them line for line. `check` returns every problem, with paths relative to
`sheet` (the core adds `sheet.`), and never changes `sheet` or `ctx`.

The sheet is a box-for-box copy of a club score card:

    hammer: away                    # which rink threw the last stone of end 1 (LSFE); required
    ends:                           # one box per end per rink, as many as `rules.ends`: 0 to 8, X = end not played
      home: [0, 0, 1, 1, 0, 3, 0, 2]
      away: [0, 2, 0, 0, 1, 0, 2, 0]
    extra:                          # extra ends, only when level after the last end
      home: [0, 1]
      away: [0, 0]
    conceded: away                  # the rink that shook hands; the ends left are X
    time_called: true               # ice time ran out (instead of conceded); the ends left are X
    final: {home: 7, away: 5}       # the Total boxes, as written
    lineups:                        # in throwing order, when `rules.lineups` is `recorded`
      home:
        - {player: carol-d, position: lead}
        - {player: ron-m, position: second, spare_for: brian-s}
        - {name: Jo K., position: vice}          # a spare not yet in players.yml (a draft only)
        - {player: doug-h, position: skip}

How the numbers come from it: the score is the ends plus the extra ends; the hammer walk (who threw last in
each end) starts with `hammer` and follows the scores: the rink that scores gives the hammer up, a blank end
keeps it where it was, and a rink that scores without the hammer has stolen the end. Games played come from
the lineups.
"""
from __future__ import annotations

from scripts.core.model import Line, Problem, Reading, Score

SIDES = ("home", "away")
SHEET_KEYS = ("hammer", "ends", "extra", "conceded", "time_called", "final", "lineups")
ROW_KEYS = ("player", "name", "position", "spare_for")
POSITIONS = ("lead", "second", "vice", "skip")
POSITION_LABELS = {"lead": "Lead", "second": "Second", "vice": "Vice", "skip": "Skip"}
DEFAULT_ENDS = 8
MAX_POINTS = 8             # the most one rink can score in an end (all eight stones counting)
RARE_POINTS = 7            # 7 and 8 are legal but very rare: a warning
BIG_END = 3                # an end of 3 or more is a "big end"
MIN_RINK, MAX_RINK = 3, 4  # a rink may play three; more than four never throw


# ------------------------------------------------------------------ small helpers

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _path(*parts):
    return ".".join(str(p) for p in parts)


def _ends(ctx):
    """How many ends a game has (the `ends` option)."""
    value = ctx.options.get("ends", DEFAULT_ENDS)
    return value if _is_int(value) and value > 0 else DEFAULT_ENDS


def _extra_rule(ctx):
    return ctx.options.get("extra_end", "playoffs")


def _lineups_recorded(ctx):
    return ctx.options.get("lineups", "recorded") == "recorded"


def _positions(ctx):
    listed = ctx.sport.get("positions")
    return tuple(listed) if isinstance(listed, list) and listed else POSITIONS


def _team_name(ctx, side):
    team = ctx.teams.get(ctx.sides.get(side))
    return team.name if team else side.capitalize()


def _player_label(ctx, player_id):
    player = ctx.players.get(player_id) if isinstance(player_id, str) else None
    return player.label if player else str(player_id)


def _other(side):
    return "away" if side == "home" else "home"


def _kind(v):
    """What a score box holds: ("empty", None), ("x", None), ("n", the number) or ("bad", the value)."""
    if v is None:
        return "empty", None
    if v == "X" and isinstance(v, str):
        return "x", None
    if _is_int(v) and 0 <= v <= MAX_POINTS:
        return "n", v
    return "bad", v


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class _Out:
    """Collects the problems of one check() call. `gap` is the level of a box left empty: a draft may do it,
    a finished file may not."""

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
            out.error(str(key), f"'{key}' isn't part of a score card. Use one of: {', '.join(SHEET_KEYS)}.")
    _check_hammer(out, sheet)
    info = _check_ends(out, sheet)
    _check_stop(out, sheet, info)
    totals = None
    if info is not None:
        totals = _check_extra(out, sheet, info)
        _check_final(out, sheet, info, totals)
    _check_lineups(out, sheet)
    return out.problems


def _check_hammer(out, sheet):
    value = sheet.get("hammer")
    if value is None:
        out.empty("hammer", "is empty. Which rink had the last stone (the hammer) in the first end? Write home or away "
                            "(the LSFE box on the card).")
    elif value not in SIDES or not isinstance(value, str):
        out.error("hammer", f"hammer {value!r} should be home or away: the rink that threw the last stone of the first end")


def _check_ends(out, sheet):
    """The end boxes. Returns {side: [(kind, value)]} plus the facts the later checks need, or None when the
    boxes are missing or the wrong length (the later checks would mean nothing)."""
    n = _ends(out.ctx)
    block = sheet.get("ends")
    if block is None:
        out.empty("ends", f"is empty. Fill in the {n} end boxes of each rink, for home and away.")
        return None
    if not isinstance(block, dict):
        out.empty("ends", "should list the end boxes for home and away, like 'home: [0, 2, ...]' and 'away: [1, 0, ...]'.")
        return None
    for key in block:
        if key not in SIDES:
            out.error(_path("ends", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    vals, usable = {}, True
    for side in SIDES:
        team = out.team(side)
        base = _path("ends", side)
        listed = block.get(side)
        if listed is None:
            out.empty(base, f"is empty. Fill in {team}'s {n} end boxes (0 if nobody scored, X for an end not played).")
            usable = False
            continue
        if not isinstance(listed, list) or len(listed) != n:
            out.error(base, f"this league plays {n} ends: write {n} boxes for {team}, X for an end not played")
            usable = False
            continue
        vals[side] = []
        for i, v in enumerate(listed):
            at = _path(base, i)
            kind, value = _kind(v)
            vals[side].append((kind, value))
            if kind == "empty":
                out.empty(at, f"is empty. Write {team}'s score in end {i + 1} (0 if nobody scored, X if the end wasn't played).")
            elif kind == "bad":
                out.error(at, f"{v!r} isn't a score for end {i + 1}: write a whole number from 0 to {MAX_POINTS}, "
                              "or X for an end not played")
            elif kind == "n" and value >= RARE_POINTS:
                out.warning(at, f"{team} scored {value} in end {i + 1}. That is very rare: check the card.")
    if not usable:
        return None
    stopped_by = sheet.get("conceded") is not None or sheet.get("time_called") is not None
    first_x = {side: next((i for i, (k, _) in enumerate(vals[side]) if k == "x"), None) for side in SIDES}
    for i in range(n):
        (hk, hv), (ak, av) = vals["home"][i], vals["away"][i]
        if hk == "n" and ak == "n" and hv > 0 and av > 0:
            out.error(_path("ends", "home", i), f"both rinks scored in end {i + 1}. Only one rink scores in an end: "
                                                 "check the card.")
        for side in SIDES:
            mine, theirs = vals[side][i][0], vals[_other(side)][i][0]
            if mine == "x" and theirs == "n":
                out.error(_path("ends", side, i), f"end {i + 1} is X for {out.team(side)} but {out.team(_other(side))} has "
                                                   "a number. An end not played is X for both rinks.")
    for side in SIDES:
        if first_x[side] is None:
            continue
        for i in range(first_x[side] + 1, n):
            if vals[side][i][0] == "n":
                out.error(_path("ends", side, i), f"end {i + 1} has a number after an X. X marks only the ends left when a "
                                                   "game stopped early.")
    if vals["home"][0][0] == "x":
        out.error(_path("ends", "home", 0), "end 1 is X, so no end was played. A game that was not played is a forfeit "
                                            "(forfeit: <team id>), not a score.")
    where = next((s for s in SIDES if first_x[s] is not None), None)
    if where is not None and not stopped_by:
        out.error(_path("ends", where, first_x[where]),
                  f"end {first_x[where] + 1} is X, but nobody conceded and time wasn't called. Add 'conceded: home' "
                  "or 'conceded: away' (the rink that shook hands), or 'time_called: true'.")
    complete = all(k in ("n", "x") for side in SIDES for k, _ in vals[side])
    played = None
    if complete:
        xs = [first_x[s] for s in SIDES if first_x[s] is not None]
        played = min(xs) if xs else n
    sums = {side: sum(v for k, v in vals[side] if k == "n") for side in SIDES} if complete else None
    return {"vals": vals, "n": n, "complete": complete, "played": played, "sums": sums,
            "has_x": complete and played < n}


def _check_stop(out, sheet, info):
    """`conceded` and `time_called`."""
    conceded, time_called = sheet.get("conceded"), sheet.get("time_called")
    if conceded is not None:
        if not isinstance(conceded, str) or conceded not in SIDES:
            out.error("conceded", f"conceded {conceded!r} should be home or away: the rink that shook hands")
        elif info is not None and info["complete"]:
            if not info["has_x"]:
                out.error("conceded", f"{out.team(conceded)} is marked as conceding, but every end was played. Take "
                                      "'conceded' out, or write X for the ends that were not played.")
            elif info["sums"][conceded] >= info["sums"][_other(conceded)]:
                out.error("conceded", f"{out.team(conceded)} shook hands but was not behind "
                                      f"({info['sums'][conceded]}-{info['sums'][_other(conceded)]} after {info['played']} "
                                      "ends). The score stands as it is, so the rink that concedes is the one behind: "
                                      "check which rink conceded.")
        if time_called is not None:
            out.error("conceded", "'conceded' and 'time_called' are both set. A game stops one way: use only one.")
    if time_called is not None and time_called is not True:
        out.error("time_called", "time_called should be true (ice time ran out), or leave the line out")


def _check_extra(out, sheet, info):
    """The extra ends. Returns {side: the extra-end points} when every extra box is a number (0 and 0 when there
    are none), else None."""
    value = sheet.get("extra")
    if value is None:
        _check_extra_missing(out, sheet, info)
        return {"home": 0, "away": 0}
    if not isinstance(value, dict):
        out.error("extra", "should list the extra-end boxes for home and away, like 'home: [0, 1]' and 'away: [0, 0]'")
        return None
    for key in value:
        if key not in SIDES:
            out.error(_path("extra", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    boxes, listed_ok = {}, True
    for side in SIDES:
        listed = value.get(side)
        if listed is None:
            listed = []
        if not isinstance(listed, list):
            out.error(_path("extra", side), f"{out.team(side)}'s extra ends should be a list of boxes, like [0, 1]")
            listed_ok = False
            continue
        boxes[side] = listed
    if not listed_ok:
        return None
    if not boxes["home"] and not boxes["away"]:          # `extra: {home: [], away: []}` is no extra end
        _check_extra_missing(out, sheet, info)
        return {"home": 0, "away": 0}
    same_length = len(boxes["home"]) == len(boxes["away"])
    if not same_length:
        out.error(_path("extra", "away"), f"{out.team('home')} has {len(boxes['home'])} extra-end box{'' if len(boxes['home']) == 1 else 'es'} but "
                                          f"{out.team('away')} has {len(boxes['away'])}. Both rinks have a box in every "
                                          "extra end.")
    parsed = {side: [] for side in SIDES}
    for side in SIDES:
        for i, v in enumerate(boxes[side]):
            at = _path("extra", side, i)
            if v is None:
                out.empty(at, f"is empty. Write {out.team(side)}'s score in extra end {i + 1} (0 if nobody scored).")
                parsed[side].append(None)
            elif _is_int(v) and 0 <= v <= MAX_POINTS:
                parsed[side].append(v)
            else:
                what = "X is only for ends not played, and an extra end is always played" if v == "X" else f"{v!r} isn't a score"
                out.error(at, f"{what}: write a whole number from 0 to {MAX_POINTS} for extra end {i + 1}")
                parsed[side].append(None)
    # An extra end is only played by a league that plays one, after a game that was level after the last end.
    if out.ctx.game_type != "playoff" and _extra_rule(out.ctx) == "playoffs":
        out.error("extra", "extra ends are filled in, but this league plays an extra end only in the playoffs: a "
                           "regular-season game that is level after the last end is a tie. Take 'extra' out.")
    elif info["complete"]:
        if info["has_x"] or sheet.get("conceded") is not None:
            out.error("extra", "extra ends are filled in, but the game stopped early. Extra ends follow only a game "
                               "that was played to the last end.")
        elif info["sums"]["home"] != info["sums"]["away"]:
            out.error("extra", f"extra ends are filled in, but the game was not level after the last end "
                               f"({info['sums']['home']}-{info['sums']['away']}). Take 'extra' out.")
    if not same_length or any(v is None for side in SIDES for v in parsed[side]):
        return None
    broke = None                                         # the extra end that broke the tie
    for i in range(len(parsed["home"])):
        h, a = parsed["home"][i], parsed["away"][i]
        if broke is not None:
            out.error(_path("extra", "home", i), f"extra end {broke + 1} already broke the tie. Take out extra end "
                                                 f"{i + 1} and any after it: a game ends on a score.")
            break
        if h > 0 and a > 0:
            out.error(_path("extra", "home", i), f"both rinks scored in extra end {i + 1}. Only one rink scores in an "
                                                 "end: check the card.")
        if h > 0 or a > 0:
            broke = i
    if broke is None and sheet.get("time_called") is None:
        out.error(_path("extra", "home", len(parsed["home"]) - 1),
                  "the last extra end is blank, but a game ends on a score. Add the next extra end, or write "
                  "'time_called: true' if time ran out.")
    return {side: sum(parsed[side]) for side in SIDES}


def _check_extra_missing(out, sheet, info):
    ctx = out.ctx
    needs = ctx.game_type == "playoff" or _extra_rule(ctx) == "always"
    if not needs or not info["complete"] or info["has_x"]:
        return
    if sheet.get("conceded") is not None or sheet.get("time_called") is not None:
        return
    if info["sums"]["home"] == info["sums"]["away"]:
        why = "a playoff game" if ctx.game_type == "playoff" else "a game in a league that always plays an extra end"
        out.error("extra", f"the game was level {info['sums']['home']}-{info['sums']['away']} after the last end, and "
                           f"{why} goes on to an extra end. Fill in 'extra' (one box per rink for each extra end played), "
                           "or write 'time_called: true' if time ran out.")


def _check_final(out, sheet, info, extra_totals):
    """The Total boxes."""
    final = sheet.get("final")
    if final is None:
        out.empty("final", "is empty. Fill in both rinks' Total boxes, like {home: 7, away: 5}.")
        return
    if not isinstance(final, dict):
        out.error("final", "should list the Total boxes for home and away, like {home: 7, away: 5}")
        return
    for key in final:
        if key not in SIDES:
            out.error(_path("final", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    known = info["complete"] and extra_totals is not None
    for side in SIDES:
        box = final.get(side)
        team = out.team(side)
        at = _path("final", side)
        if box is None:
            out.empty(at, f"is empty. Fill in {team}'s Total box.")
        elif not _is_int(box) or box < 0:
            out.error(at, f"the Total box for {team} should be a whole number, not {box!r}")
        elif known:
            total = info["sums"][side] + extra_totals[side]
            if box != total:
                out.error(at, f"the Total box says {box}, but the ends add up to {total}")


def _check_lineups(out, sheet):
    ctx = out.ctx
    value = sheet.get("lineups")
    if not _lineups_recorded(ctx):
        if value is not None:
            out.error("lineups", "this league doesn't record lineups (rules.lineups is none): take 'lineups' out, or set "
                                 "rules.lineups to recorded")
        return
    if value is None:
        out.empty("lineups", "is empty. List each rink's players in throwing order, with their positions.")
        return
    if not isinstance(value, dict):
        out.error("lineups", "should list each rink's players for home and away, like 'home: [...]' and 'away: [...]'")
        return
    for key in value:
        if key not in SIDES:
            out.error(_path("lineups", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    seen = {}
    for side in SIDES:
        team = out.team(side)
        base = _path("lineups", side)
        rows = value.get(side)
        if rows is None:
            out.empty(base, f"is empty. List {team}'s players in throwing order, with their positions.")
            continue
        if not isinstance(rows, list):
            out.error(base, f"list {team}'s players, one row each: {{player: carol-d, position: lead}}")
            continue
        if not MIN_RINK <= len(rows) <= MAX_RINK:
            out.error(base, f"{team} has {len(rows)} rows. A rink plays three or four players (a spare is a row, not an "
                            "extra player).")
        in_lineup = {row.get("player") for row in rows if isinstance(row, dict) and isinstance(row.get("player"), str)}
        used, bad_position = {}, False
        for i, row in enumerate(rows):
            at = _path(base, i)
            if not isinstance(row, dict):
                out.error(at, "a row looks like {player: carol-d, position: lead}")
                bad_position = True
                continue
            for key in row:
                if key not in ROW_KEYS:
                    out.error(_path(at, str(key)), f"'{key}' isn't part of a lineup row. Use one of: {', '.join(ROW_KEYS)}.")
            if not _check_position(out, row, at, i, used):
                bad_position = True
            _check_lineup_player(out, row, at, side, seen)
            _check_spare_for(out, row, at, side, in_lineup)
        if not bad_position and "skip" not in used and "skip" in _positions(ctx):
            out.error(base, f"{team} has no skip. Every rink has one: write 'position: skip' on the skip's row.")


def _check_position(out, row, at, i, used):
    """Returns whether the row has a usable position (so a missing skip can be reported)."""
    positions = _positions(out.ctx)
    pat = _path(at, "position")
    position = row.get("position")
    if position is None:
        out.error(pat, f"is missing. Give the position: {', '.join(positions)}.")
        return False
    if not isinstance(position, str) or position not in positions:
        out.error(pat, f"position {position!r} should be one of: {', '.join(positions)}")
        return False
    if position in used:
        out.error(pat, f"{position} is on two rows of this rink (rows {used[position] + 1} and {i + 1}). "
                       "Each position is played once.")
        return False
    used[position] = i
    return True


def _check_lineup_player(out, row, at, side, seen):
    ctx = out.ctx
    pid = row.get("player")
    pat = _path(at, "player")
    if pid is None:
        who = row.get("name") or "this row"
        out.empty(pat, f"{who} isn't matched to a player id yet. Pick one from players.yml, or add them there first "
                       "(a spare gets sub: true)")
        return
    if not isinstance(pid, str) or pid not in ctx.players:
        out.error(pat, f"player {pid!r} is not in players.yml")
        return
    if pid in seen:
        out.error(pat, f"{pid} is listed twice in this game (also at sheet.{seen[pid]})")
        return
    seen[pid] = pat
    player = ctx.players[pid]
    if not player.sub and player.team != ctx.sides.get(side) and row.get("spare_for") is None:
        out.warning(pat, f"{player.label} is not on {out.team(side)}. If a spare filled in, mark them sub: true in "
                         "players.yml, or add spare_for with the regular they replaced")


def _check_spare_for(out, row, at, side, in_lineup):
    ctx = out.ctx
    target = row.get("spare_for")
    if target is None:
        return
    sat = _path(at, "spare_for")
    mine = ctx.sides.get(side)
    regular = ctx.players.get(target) if isinstance(target, str) else None
    if regular is None:
        out.error(sat, f"spare_for {target!r} is not in players.yml. Name the regular player the spare replaced.")
    elif regular.team != mine or regular.sub:
        out.error(sat, f"{regular.label} is not a regular player of {out.team(side)}. spare_for names the player of this "
                       "rink the spare replaced.")
    elif target in in_lineup:
        out.error(sat, f"{regular.label} is in this lineup too, so nobody was replaced. Take out spare_for, or take "
                       f"{regular.label} out of the lineup.")
    player = ctx.players.get(row.get("player")) if isinstance(row.get("player"), str) else None
    if player is not None and not player.sub and player.team == mine:
        out.warning(sat, f"{player.label} is a regular player of {out.team(side)}, not a spare. Take out spare_for, or mark "
                         "them sub: true in players.yml.")


# ------------------------------------------------------------------ read

def read(sheet, ctx):
    """The numbers of a sheet `check` accepted (warnings allowed). Arithmetic only."""
    n = _ends(ctx)
    ends = {side: list(sheet["ends"][side]) for side in SIDES}
    extra = {side: list((sheet.get("extra") or {}).get(side) or []) for side in SIDES}
    played = min((i for i in range(n) if ends["home"][i] == "X" or ends["away"][i] == "X"), default=n)
    regulation = {side: ends[side][:played] for side in SIDES}
    sequence = [{side: regulation[side][i] for side in SIDES} for i in range(played)]
    sequence += [{side: extra[side][i] for side in SIDES} for i in range(len(extra["home"]))]
    walk = _walk(sheet["hammer"], sequence)
    final = {side: sum(end[side] for end in sequence) for side in SIDES}
    score = Score(final=final,
                  periods={side: [None if v == "X" else v for v in ends[side]] for side in SIDES},
                  extra={side: extra[side] for side in SIDES} if extra["home"] else {},
                  decided_in="overtime" if extra["home"] else "regulation",
                  final_at={side: f"sheet.final.{side}" for side in SIDES})
    lineups = {side: [] for side in SIDES}
    lines = []
    if _lineups_recorded(ctx):
        for side in SIDES:
            for row in (sheet.get("lineups") or {}).get(side) or []:
                if not row.get("player"):
                    continue
                lines.append(Line(side=side, player=row["player"], group="player", counts={}))
                lineups[side].append({"player": row["player"], "position": row["position"],
                                      "spare_for": row.get("spare_for")})
    stopped = None
    if sheet.get("conceded") is not None:
        stopped = {"by": "conceded", "side": sheet["conceded"], "after": played}
    elif sheet.get("time_called") is not None:
        stopped = {"by": "time", "side": None, "after": played}
    return Reading(score=score, lines=lines, team_lines=walk["team_lines"],
                   facts={"hammer_by_end": walk["hammer_by_end"], "stopped": stopped, "ends": n, "lineups": lineups})


def _walk(first_hammer, sequence):
    """The hammer walk over the played ends, regulation then extra. Returns the hammer holder of each end and
    each rink's team counts. A rink with the hammer that scores gives it up; a blank end keeps it where it was;
    a rink that scores without the hammer has stolen the end (and the other rink keeps the hammer)."""
    keys = ("ends_won", "stolen", "blanks", "big_ends", "hammer_ends", "hammer_scored", "ends")
    counts = {side: dict.fromkeys(keys, 0) for side in SIDES}
    holder, by_end = first_hammer, []
    for end in sequence:
        by_end.append(holder)
        for side in SIDES:
            counts[side]["ends"] += 1
        counts[holder]["hammer_ends"] += 1
        scorer = next((side for side in SIDES if end[side] > 0), None)
        if scorer is None:
            counts[holder]["blanks"] += 1
            continue
        counts[scorer]["ends_won"] += 1
        if end[scorer] >= BIG_END:
            counts[scorer]["big_ends"] += 1
        if scorer == holder:
            counts[holder]["hammer_scored"] += 1
            holder = _other(holder)
        else:
            counts[scorer]["stolen"] += 1
    return {"hammer_by_end": by_end, "team_lines": counts}


# ------------------------------------------------------------------ present

CAPTION = "Points by end"
TITLE = "End by end"
HAMMER_WORD = "Hammer"
STOLEN_WORD = "stolen end"
BLANK_WORD = "blank end"
VOID_WORD = "not played"
LEGEND_HAMMER = "Hammer (last rock)"
LEGEND_STOLEN = "Stolen end"
LEGEND_BLANK = "Blank end"
LEGEND_VOID = "Not played"
NUMBERS_TITLE = "The game in numbers"
NUMBERS_CORNER = "This game"
NUMBERS_NOTE = "A blank counts to the rink that had hammer and kept it."
ROSTER_TITLE = "Lineups"
ROSTER_LINK = "Rink"
ROSTER_NOTE = "In throwing order, as on the score card."


def present(reading, ctx):
    return {"line_score": _line_score(reading, ctx, full=True), "card": _card(reading, ctx), "tiles": None,
            "blocks": _blocks(reading, ctx)}


def _columns(score):
    """(labels, how many are extra ends): 1..n for the ends, then EE (EE1, EE2... when there are several)."""
    ends = len(score.periods["home"])
    extra = len(score.extra.get("home", []))
    labels = [str(i + 1) for i in range(ends)]
    labels += ["EE"] if extra == 1 else [f"EE{i + 1}" for i in range(extra)]
    return labels, extra


def _line_score(reading, ctx, full):
    score = reading.score
    hammer = reading.facts["hammer_by_end"]
    labels, _ = _columns(score)
    regulation = len(score.periods["home"])
    series = {side: list(score.periods[side]) + list(score.extra.get(side, [])) for side in SIDES}
    columns, cells = [], {side: [] for side in SIDES}
    for k in range(len(labels)):
        v = {side: series[side][k] for side in SIDES}
        column = {"label": labels[k]}
        if full and v["home"] == 0 and v["away"] == 0:
            column["blank"] = True
        columns.append(column)
        for side in SIDES:
            if v[side] is None:
                cells[side].append({"v": None, "void": True})
                continue
            cell = {"v": v[side]}
            if v[side] > 0:
                cell["won"] = True
                if hammer[k] != side:
                    cell["mark"] = True
            if full and hammer[k] == side:
                cell["hammer"] = True
            cells[side].append(cell)
    rows = {side: {"cells": cells[side], "total": score.final[side], "extra": None,
                   "hammer_first": (not full) and hammer[0] == side} for side in SIDES}
    line = ctx.sport["line_score"]
    out = {"shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
           "columns": columns, "rows": rows, "caption": CAPTION, "won_word": None, "mark_word": STOLEN_WORD,
           "void_word": VOID_WORD, "blank_word": BLANK_WORD, "hammer_word": HAMMER_WORD,
           "title": None, "meta": None, "legend": [], "legend_stack": False, "note": None, "note_strong": None}
    if not full:
        return out
    has_void = any(c.get("void") for side in SIDES for c in cells[side])
    team = _team_name(ctx, hammer[0])
    out["title"] = TITLE
    out["meta"] = _meta(reading, regulation)
    out["note"] = f"{team} had hammer in the first end."
    out["note_strong"] = team
    out["legend"] = [{"kind": "hammer", "text": LEGEND_HAMMER}, {"kind": "mark", "text": LEGEND_STOLEN},
                     {"kind": "blank", "text": LEGEND_BLANK}]
    if has_void:
        out["legend"].append({"kind": "x", "text": LEGEND_VOID, "mark": "X"})
    return out


def _meta(reading, regulation):
    """"8 ends · no extra end", "Shook hands after 6 of 8 ends", "Time called after 7 of 8 ends"."""
    stopped = reading.facts["stopped"]
    n = reading.facts["ends"]
    extra = len(reading.score.extra.get("home", []))
    if stopped and stopped["after"] < n:
        word = "Shook hands" if stopped["by"] == "conceded" else "Time called"
        return f"{word} after {stopped['after']} of {n} ends"
    parts = [_plural(n, "end"), "no extra end" if not extra else ("extra end" if extra == 1 else f"{extra} extra ends")]
    if stopped:
        parts.append("time called")
    return " · ".join(parts)


def _card(reading, ctx):
    stopped = reading.facts["stopped"]
    card = {"note": None, "strong": None, "link_label": "Game",
            "line_score": _line_score(reading, ctx, full=False), "meta_extra": []}
    if stopped and stopped["after"] < reading.facts["ends"]:
        card["meta_extra"].append(("Shook hands" if stopped["by"] == "conceded" else "Time called") + f" after {stopped['after']}")
    return card


def _blocks(reading, ctx):
    blocks = [_numbers(reading)]
    roster = _roster(reading)
    if roster:
        blocks.append(roster)
    return blocks


def _numbers(reading):
    t = reading.team_lines

    def pair(key):
        return {side: str(t[side][key]) for side in SIDES}

    def ahead(key):
        h, a = t["home"][key], t["away"][key]
        return "home" if h > a else "away" if a > h else None

    def hammer_rate():
        """The rink that scored with the hammer in the larger share of its hammer ends (None when level or when a
        rink never had the hammer)."""
        h, a = t["home"], t["away"]
        if not h["hammer_ends"] or not a["hammer_ends"]:
            return None
        left, right = h["hammer_scored"] * a["hammer_ends"], a["hammer_scored"] * h["hammer_ends"]
        return "home" if left > right else "away" if right > left else None

    stolen = ahead("stolen")
    rows = [
        {"label": "Ends won", "cells": pair("ends_won"), "key": ahead("ends_won"), "hot": False},
        {"label": "Stolen ends", "cells": pair("stolen"), "key": stolen, "hot": stolen is not None},
        {"label": "Ends with hammer", "cells": pair("hammer_ends"), "key": None, "hot": False},
        {"label": "Scored with hammer",
         "cells": {side: f"{t[side]['hammer_scored']} of {t[side]['hammer_ends']}" for side in SIDES},
         "key": hammer_rate(), "hot": False},
        {"label": "Blank ends", "cells": pair("blanks"), "key": None, "hot": False},
        {"label": "Big ends (3+)", "cells": pair("big_ends"), "key": ahead("big_ends"), "hot": False},
    ]
    return {"type": "numbers", "title": NUMBERS_TITLE, "corner": NUMBERS_CORNER, "rows": rows, "note": NUMBERS_NOTE}


def _roster(reading):
    lineups = reading.facts.get("lineups") or {}
    teams = []
    for side in SIDES:
        rows = [{"role": POSITION_LABELS.get(r["position"], r["position"].capitalize()), "player": r["player"],
                 "key": r["position"] == "skip", "spare_for": r["spare_for"]} for r in lineups.get(side, [])]
        if rows:
            teams.append({"side": side, "rows": rows})
    if not teams:
        return None
    return {"type": "roster", "title": ROSTER_TITLE, "teams": teams, "link_label": ROSTER_LINK, "note": ROSTER_NOTE}


# ------------------------------------------------------------------ derive

def derive(counts, group):
    """Curling has no rates (spec decisions 9 and 10): player stats are games played, team stats are counts."""
    return {}
