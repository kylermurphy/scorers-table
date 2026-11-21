"""The rules of hockey (docs/stage-5-hockey-spec.md, sections 2-5): check, read, present, derive.

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.model`, so the
stage 7 JavaScript port can match them line for line. `check` returns every problem, with paths relative to
`sheet` (the core adds `sheet.`), and never changes `sheet` or `ctx`.

The sheet is a copy of a rec game sheet (the scorekeeper's copy):

    roster:                         # who dressed, top to bottom; num is the jersey number written on the sheet
      home: [{player: len-t, num: 31}, {player: barry-s, num: 4}, ...]
      away: [...]
    goals:                          # the scoring summary, in the order written, both teams
      - {period: 1, time: "4:12", side: home, num: 12, assists: [4, 17], strength: PP, en: true, ps: true}
    penalties:
      - {period: 1, time: "12:15", side: away, num: 21, infraction: Tripping, minutes: 2}
      - {period: 2, time: "5:10", side: home, num: bench, served_by: 6, infraction: Too many players, minutes: 2}
    goalies:                        # each goalie who played; GA required, shots only when `rules.goalie_shots`
      home: [{num: 31, ga: 3, shots: 25, decision: true}]
    shootout:                       # only after a level overtime (or straight after regulation)
      first: home
      home: [{num: 12, scored: true}, ...]
      away: [...]
    score:                          # the "score by periods" boxes, as written
      home: {periods: [2, 1, 2], ot: ~, so: ~, final: 5}
      away: {periods: [1, 2, 0], ot: ~, so: ~, final: 3}

How the numbers come from it: the goals are put in time order within each period, so the running score and the
game-winning goal (GWG) follow the game, not the order of the lines. A shootout adds one goal to the winner's
final score and gives no player a goal and no goalie a goal against. Games played come from the roster.
Times are quoted text ("4:12"): an unquoted 4:12 is read by Python's YAML reader as the number 252.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from scripts.core.model import Line, Problem, Reading, Score

SIDES = ("home", "away")
SHEET_KEYS = ("roster", "goals", "penalties", "goalies", "shootout", "score")
ROSTER_KEYS = ("player", "name", "num")
GOAL_KEYS = ("period", "time", "side", "num", "assists", "strength", "en", "ps")
PENALTY_KEYS = ("period", "time", "side", "num", "served_by", "infraction", "minutes")
GOALIE_KEYS = ("num", "ga", "shots", "decision")
SCORE_SIDE_KEYS = ("periods", "ot", "so", "final")
SHOOTOUT_KEYS = ("first", "home", "away")
ATTEMPT_KEYS = ("num", "scored")
STRENGTHS = ("EV", "PP", "SH")
USUAL_MINUTES = (2, 4, 5, 10)
MAX_ROSTER = 25
MAX_ASSISTS = 2
MAX_MINUTES = 20
BENCH = "bench"

# The option defaults (sport.yml is the source; these keep a context with no options usable).
DEFAULT_PERIODS = 3
DEFAULT_PERIOD_MINUTES = 15
DEFAULT_OT_MINUTES = 5
DEFAULT_SHOOTOUT_ROUNDS = 3


# ------------------------------------------------------------------ small helpers

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _path(*parts):
    return ".".join(str(p) for p in parts)


def _other(side):
    return "away" if side == "home" else "home"


def _option(ctx, key, default):
    value = ctx.options.get(key, default)
    return default if value is None else value


def _periods(ctx):
    value = _option(ctx, "periods", DEFAULT_PERIODS)
    return value if _is_int(value) and value > 0 else DEFAULT_PERIODS


def _period_minutes(ctx):
    value = _option(ctx, "period_minutes", DEFAULT_PERIOD_MINUTES)
    return value if _is_int(value) and value > 0 else DEFAULT_PERIOD_MINUTES


def _ot_minutes(ctx):
    value = _option(ctx, "overtime_minutes", DEFAULT_OT_MINUTES)
    return value if _is_int(value) and value > 0 else DEFAULT_OT_MINUTES


def _rounds(ctx):
    value = _option(ctx, "shootout_rounds", DEFAULT_SHOOTOUT_ROUNDS)
    return value if _is_int(value) and value > 0 else DEFAULT_SHOOTOUT_ROUNDS


def _remaining_clock(ctx):
    return _option(ctx, "clock", "elapsed") == "remaining"


def _shots_recorded(ctx):
    return _option(ctx, "goalie_shots", "none") == "recorded"


def _goal_cap(ctx):
    value = _option(ctx, "goal_cap", 0)
    return value if _is_int(value) and value > 0 else 0


def _team_name(ctx, side):
    team = ctx.teams.get(ctx.sides.get(side))
    return team.name if team else side.capitalize()


def _player_label(ctx, player_id, fallback=None):
    player = ctx.players.get(player_id) if isinstance(player_id, str) else None
    if player:
        return player.label
    return fallback if fallback else str(player_id)


def _num_key(v):
    """The lookup key of a jersey number: 0 to 99 as a number, or "00" as text. None for anything else."""
    if _is_int(v) and 0 <= v <= 99:
        return str(v)
    if isinstance(v, str) and v == "00":
        return "00"
    return None


def _side_ok(v):
    return isinstance(v, str) and v in SIDES


def _period_index(v, ctx):
    """1 to periods for a regulation period, periods + 1 for OT, periods + n for OTn (n from 2); else None."""
    count = _periods(ctx)
    if _is_int(v) and 1 <= v <= count:
        return v
    if isinstance(v, str):
        if v == "OT":
            return count + 1
        match = re.fullmatch(r"OT([2-9]|[1-9][0-9])", v)
        if match:
            return count + int(match.group(1))
    return None


def _seconds(v):
    """Seconds from a time written like "4:12" (minutes, then two digits of seconds), else None."""
    if not isinstance(v, str):
        return None
    match = re.fullmatch(r"([0-9]{1,2}):([0-5][0-9])", v)
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _period_word(index, ctx):
    """"period 2", "overtime", "overtime 2" (for messages)."""
    count = _periods(ctx)
    if index <= count:
        return f"period {index}"
    n = index - count
    return "overtime" if n == 1 else f"overtime {n}"


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


# ------------------------------------------------------------------ parsing one row (shared by check and read)

def _goal_row(row, ctx):
    """A goal line as plain facts, with None for any box that is empty or not usable. None for a non-row."""
    if not isinstance(row, dict):
        return None
    assists = row.get("assists")
    return {
        "period": _period_index(row.get("period"), ctx),
        "secs": _seconds(row.get("time")),
        "side": row.get("side") if _side_ok(row.get("side")) else None,
        "num": _num_key(row.get("num")),
        "assists": [_num_key(a) for a in assists] if isinstance(assists, list) else [],
        "strength": row.get("strength") if row.get("strength") in STRENGTHS else "EV",
        "en": row.get("en") is True,
        "ps": row.get("ps") is True,
    }


def _penalty_row(row, ctx):
    if not isinstance(row, dict):
        return None
    minutes = row.get("minutes")
    bench = row.get("num") == BENCH
    return {
        "period": _period_index(row.get("period"), ctx),
        "secs": _seconds(row.get("time")),
        "side": row.get("side") if _side_ok(row.get("side")) else None,
        "num": None if bench else _num_key(row.get("num")),
        "bench": bench,
        "served_by": _num_key(row.get("served_by")),
        "minutes": minutes if _is_int(minutes) and minutes >= 0 else 0,
    }


def _time_key(secs, ctx):
    """Sorts a time within a period in the order the game was played."""
    value = secs or 0
    return -value if _remaining_clock(ctx) else value


# ------------------------------------------------------------------ check

def check(sheet, ctx):
    if not isinstance(sheet, dict):
        return [Problem("error", "", "the sheet should be a block with these lines: " + ", ".join(SHEET_KEYS) + ".")]
    out = _Out(ctx)
    for key in sheet:
        if key not in SHEET_KEYS:
            out.error(str(key), f"'{key}' isn't part of a game sheet. Use one of: {', '.join(SHEET_KEYS)}.")
    rosters = _check_roster(out, sheet)
    goals, goals_ok = _check_goals(out, sheet, rosters)
    penalties = _check_penalties(out, sheet, rosters)
    _check_strength_marks(out, sheet, goals, penalties)
    _check_goalies(out, sheet, rosters, goals, goals_ok)
    _check_score(out, sheet, rosters, goals, goals_ok)
    return out.problems


# ---- roster

def _check_roster(out, sheet):
    """The roster. Returns {side: {number key: row} or None}: None when that side's roster can't be used, so a
    number is not looked up on it."""
    ctx = out.ctx
    rosters = {side: None for side in SIDES}
    value = sheet.get("roster")
    if value is None:
        out.empty("roster", "is empty. List the players who dressed for each team, with their jersey numbers.")
        return rosters
    if not isinstance(value, dict):
        out.error("roster", "should list the players for home and away, like 'home: [...]' and 'away: [...]'")
        return rosters
    for key in value:
        if key not in SIDES:
            out.error(_path("roster", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    seen = {}
    for side in SIDES:
        team = out.team(side)
        base = _path("roster", side)
        rows = value.get(side)
        if rows is None:
            out.empty(base, f"is empty. List the players who dressed for {team}, with their jersey numbers.")
            continue
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROSTER:
            count = f"{len(rows)} rows" if isinstance(rows, list) else "no list of rows"
            out.error(base, f"{team} has {count}. A roster is a list of 1 to {MAX_ROSTER} players, one row each: "
                            "{player: len-t, num: 31}")
            continue
        numbers = {}
        for i, row in enumerate(rows):
            at = _path(base, i)
            if not isinstance(row, dict):
                out.error(at, "a row looks like {player: len-t, num: 31}")
                continue
            for key in row:
                if key not in ROSTER_KEYS:
                    out.error(_path(at, key), f"'{key}' isn't part of a roster row. Use one of: {', '.join(ROSTER_KEYS)}.")
            _check_roster_number(out, row, at, numbers, team)
            _check_roster_player(out, row, at, side, seen)
        rosters[side] = numbers
    return rosters


def _check_roster_number(out, row, at, numbers, team):
    nat = _path(at, "num")
    value = row.get("num")
    if value is None:
        out.error(nat, f"is missing. Write {team}'s jersey number for this player (0 to 99, or \"00\" in quotes).")
        return
    key = _num_key(value)
    if key is None:
        out.error(nat, f"{value!r} isn't a jersey number: write a whole number from 0 to 99, or \"00\" in quotes")
    elif key in numbers:
        out.error(nat, f"number {value} is on two rows of {team}. Each jersey number is on one row.")
    else:
        numbers[key] = row


def _check_roster_player(out, row, at, side, seen):
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
    if not player.sub and player.team != ctx.sides.get(side):
        out.warning(pat, f"{player.label} is not on {out.team(side)}. If a spare filled in, mark them sub: true in "
                         "players.yml")


def _roster_number(out, rosters, side, value, at, what):
    """Looks a jersey number up on a side's roster; the problem names the box. Returns the key or None."""
    key = _num_key(value)
    if key is None:
        out.error(at, f"{value!r} isn't a jersey number: write a whole number from 0 to 99, or \"00\" in quotes")
        return None
    roster = rosters.get(side) if _side_ok(side) else None
    if roster is not None and key not in roster:
        out.error(at, f"#{value} ({what}) isn't on {out.team(side)}'s roster. Check the number, or add the player to the roster.")
    return key


# ---- when and who (shared by goals and penalties)

def _check_when(out, row, at, word):
    """period, time and side of a goal or penalty line. Returns (period index, seconds, side) with None for
    a box that is empty or wrong."""
    ctx = out.ctx
    count = _periods(ctx)
    pidx = None
    period = row.get("period")
    if period is None:
        out.empty(_path(at, "period"), f"is empty. Write the period of the {word}: 1 to {count}, or OT.")
    else:
        pidx = _period_index(period, ctx)
        if pidx is None:
            out.error(_path(at, "period"), f"period {period!r} should be 1 to {count}, OT, or OT2, OT3... "
                                            "(playoff sudden death)")
        elif pidx > count + 1 and not _sudden_death_playoff(ctx):
            out.error(_path(at, "period"), f"{period} isn't possible here: only a playoff game played to a first goal "
                                            "(sudden death) has OT2, OT3...; write OT")
    secs = None
    time = row.get("time")
    tat = _path(at, "time")
    if time is None:
        out.empty(tat, f"is empty. Write the time of the {word}, like \"4:12\" (in quotes).")
    elif _is_int(time) and time >= 60:
        clock = f"{time // 60}:{time % 60:02d}"
        out.error(tat, f"the time {time} looks like {clock} written without quotes (some YAML readers turn an unquoted "
                       f"{clock} into {time}): write it in quotes, like \"{clock}\"")
    elif not isinstance(time, str):
        out.error(tat, f"the time {time!r} should be text in quotes, like \"4:12\"")
    else:
        secs = _seconds(time)
        if secs is None:
            out.error(tat, f"{time!r} isn't a time: write minutes and seconds in quotes, like \"4:12\"")
        elif pidx is not None:
            limit = _period_minutes(ctx) if pidx <= count else _ot_minutes(ctx)
            if secs > limit * 60:
                out.error(tat, f"{time} is past the end of {_period_word(pidx, ctx)}, which is {limit} minutes long")
                secs = None
    side = None
    value = row.get("side")
    if value is None:
        out.empty(_path(at, "side"), f"is empty. Which team had the {word}: home or away?")
    elif not _side_ok(value):
        out.error(_path(at, "side"), f"side {value!r} should be home or away")
    else:
        side = value
    return pidx, secs, side


def _check_order(out, rows, base, ctx, word):
    """Warn when a line's time is out of order with the line before it in the same period."""
    previous = None
    for i, row in enumerate(rows):
        current = row and (row["period"], row["secs"])
        if previous and current and current[0] is not None and previous[0] == current[0] \
                and current[1] is not None and previous[1] is not None:
            late = current[1] > previous[1] if _remaining_clock(ctx) else current[1] < previous[1]
            if late:
                direction = "later" if _remaining_clock(ctx) else "earlier"
                out.warning(_path(base, i, "time"), f"this {word} is {direction} on the clock than the line before it in the "
                                                    "same period: check the order, or the time")
        previous = current


# ---- goals

def _check_goals(out, sheet, rosters):
    """Returns (goal rows as _goal_row facts or None for a bad row, whether every goal has a period and a side)."""
    ctx = out.ctx
    value = sheet.get("goals")
    if value is None:
        return [], True
    if not isinstance(value, list):
        out.error("goals", "should be a list of goal lines, one for each goal, like [{period: 1, time: \"4:12\", side: home, num: 12}]")
        return [], False
    rows, ok = [], True
    cap, counts = _goal_cap(ctx), {}
    for i, row in enumerate(value):
        at = _path("goals", i)
        if not isinstance(row, dict):
            out.error(at, "a goal line looks like {period: 1, time: \"4:12\", side: home, num: 12, assists: [4, 17]}")
            rows.append(None)
            ok = False
            continue
        for key in row:
            if key not in GOAL_KEYS:
                out.error(_path(at, key), f"'{key}' isn't part of a goal line. Use one of: {', '.join(GOAL_KEYS)}.")
        pidx, secs, side = _check_when(out, row, at, "goal")
        num = _check_scorer(out, row, at, side, rosters)
        _check_assists(out, row, at, side, num, rosters)
        _check_marks(out, row, at)
        if pidx is None or side is None:
            ok = False
        if cap and side is not None and num is not None:
            counts[(side, num)] = counts.get((side, num), 0) + 1
            if counts[(side, num)] == cap + 1:
                out.warning(_path(at, "num"), f"#{row['num']} of {out.team(side)} has more than {_plural(cap, 'goal')} in this game, "
                                              "the most this league allows. Check the sheet.")
        rows.append(_goal_row(row, ctx))
    _check_order(out, rows, "goals", ctx, "goal")
    return rows, ok


def _sudden_death_playoff(ctx):
    return ctx.game_type == "playoff" and _option(ctx, "playoff_overtime", "sudden_death") == "sudden_death"


def _check_scorer(out, row, at, side, rosters):
    nat = _path(at, "num")
    value = row.get("num")
    if value is None:
        out.empty(nat, "is empty. Write the scorer's jersey number.")
        return None
    return _roster_number(out, rosters, side, value, nat, "the scorer")


def _check_assists(out, row, at, side, scorer, rosters):
    aat = _path(at, "assists")
    value = row.get("assists")
    if value is None:
        return
    if not isinstance(value, list):
        out.error(aat, "should be a list of jersey numbers, like [4, 17], or left out for an unassisted goal")
        return
    if len(value) > MAX_ASSISTS:
        out.error(aat, f"has {len(value)} assists. A goal has at most {MAX_ASSISTS}.")
    seen = []
    for j, a in enumerate(value):
        jat = _path(aat, j)
        key = _roster_number(out, rosters, side, a, jat, "an assist")
        if key is None:
            continue
        if scorer is not None and key == scorer:
            out.error(jat, f"#{a} scored the goal and can't assist it too")
        elif key in seen:
            out.error(jat, f"#{a} is listed twice on this goal")
        seen.append(key)
    if row.get("ps") is True and value:
        out.error(aat, "a penalty shot is never assisted: take the assists out, or the ps mark")


def _check_marks(out, row, at):
    strength = row.get("strength")
    if strength is not None and strength not in STRENGTHS:
        out.error(_path(at, "strength"), f"strength {strength!r} should be EV, PP or SH (or left out for even strength)")
    for key in ("en", "ps"):
        if row.get(key) is not None and row.get(key) is not True:
            out.error(_path(at, key), f"{key} should be true (an empty-net goal / a penalty-shot goal), or left out")


# ---- penalties

def _check_penalties(out, sheet, rosters):
    """Returns the penalty rows as _penalty_row facts (None for a bad row)."""
    ctx = out.ctx
    value = sheet.get("penalties")
    if value is None:
        return []
    if not isinstance(value, list):
        out.error("penalties", "should be a list of penalty lines, like [{period: 1, time: \"12:15\", side: away, num: 21, "
                               "infraction: Tripping, minutes: 2}]")
        return []
    rows = []
    for i, row in enumerate(value):
        at = _path("penalties", i)
        if not isinstance(row, dict):
            out.error(at, "a penalty line looks like {period: 1, time: \"12:15\", side: away, num: 21, infraction: Tripping, minutes: 2}")
            rows.append(None)
            continue
        for key in row:
            if key not in PENALTY_KEYS:
                out.error(_path(at, key), f"'{key}' isn't part of a penalty line. Use one of: {', '.join(PENALTY_KEYS)}.")
        _, _, side = _check_when(out, row, at, "penalty")
        _check_penalty_who(out, row, at, side, rosters)
        _check_infraction(out, row, at)
        _check_minutes(out, row, at)
        rows.append(_penalty_row(row, ctx))
    _check_order(out, rows, "penalties", ctx, "penalty")
    return rows


def _check_penalty_who(out, row, at, side, rosters):
    nat = _path(at, "num")
    value = row.get("num")
    if value is None:
        out.empty(nat, f"is empty. Write the jersey number of the player who took the penalty, or {BENCH} for a bench penalty.")
    elif value != BENCH:
        _roster_number(out, rosters, side, value, nat, "the penalty")
    served = row.get("served_by")
    if served is not None:
        sat = _path(at, "served_by")
        if value != BENCH:
            out.error(sat, f"served_by is only for a bench penalty (num: {BENCH}). Take it out, or write num: {BENCH}.")
        else:
            _roster_number(out, rosters, side, served, sat, "who served it")


def _check_infraction(out, row, at):
    value = row.get("infraction")
    iat = _path(at, "infraction")
    if value is None:
        out.empty(iat, "is empty. Write the infraction, like Tripping.")
    elif not isinstance(value, str) or not value.strip():
        out.error(iat, f"{value!r} should be text, like Tripping")


def _check_minutes(out, row, at):
    value = row.get("minutes")
    mat = _path(at, "minutes")
    if value is None:
        out.empty(mat, "is empty. Write the penalty minutes (2 for a minor).")
    elif not _is_int(value) or not 1 <= value <= MAX_MINUTES:
        out.error(mat, f"{value!r} should be a whole number of minutes from 1 to {MAX_MINUTES}")
    elif value not in USUAL_MINUTES:
        out.warning(mat, f"{value} minutes is unusual (2, 4, 5 and 10 are the usual penalties): check the sheet")


def _check_strength_marks(out, sheet, goals, penalties):
    """PP needs an opposing penalty in this period or the one before; SH needs one against the scorer's own team."""
    raw = sheet.get("goals")
    if not isinstance(raw, list):
        return
    taken = {(p["side"], p["period"]) for p in penalties if p and p["side"] and p["period"]}
    for i, (row, g) in enumerate(zip(raw, goals)):
        if not g or not isinstance(row, dict) or not g["side"] or not g["period"]:
            continue
        for mark, side in (("PP", _other(g["side"])), ("SH", g["side"])):
            if row.get("strength") == mark and (side, g["period"]) not in taken and (side, g["period"] - 1) not in taken:
                who = out.team(side)
                out.warning(_path("goals", i, "strength"),
                            f"{mark} goal, but {who} has no penalty in this period or the one before: check the strength mark "
                            "and the penalty list")


# ---- goalies

def _check_goalies(out, sheet, rosters, goals, goals_ok):
    ctx = out.ctx
    value = sheet.get("goalies")
    if value is None:
        out.empty("goalies", "is empty. List the goalies who played, with their goals against.")
        return
    if not isinstance(value, dict):
        out.error("goalies", "should list the goalies for home and away, like 'home: [{num: 31, ga: 3}]'")
        return
    for key in value:
        if key not in SIDES:
            out.error(_path("goalies", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    for side in SIDES:
        team = out.team(side)
        base = _path("goalies", side)
        rows = value.get(side)
        if rows is None:
            out.empty(base, f"is empty. List {team}'s goalies with their goals against.")
            continue
        if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
            out.error(base, f"list {team}'s goalie, or two when both played: [{{num: 31, ga: 3}}]")
            continue
        seen, gas, decisions = [], [], 0
        for i, row in enumerate(rows):
            at = _path(base, i)
            if not isinstance(row, dict):
                out.error(at, "a goalie row looks like {num: 31, ga: 3}")
                gas.append(None)
                continue
            for key in row:
                if key not in GOALIE_KEYS:
                    out.error(_path(at, key), f"'{key}' isn't part of a goalie row. Use one of: {', '.join(GOALIE_KEYS)}.")
            _check_goalie_number(out, row, at, side, rosters, seen)
            gas.append(_check_goalie_numbers(out, row, at))
            if row.get("decision") is True:
                decisions += 1
            elif row.get("decision") not in (None, False):
                out.error(_path(at, "decision"), f"decision {row['decision']!r} should be true on the goalie who gets the win or loss, "
                                                 "or left out")
        if len(rows) == 2:
            if decisions == 0:
                out.empty(base, f"{team} used two goalies: mark the one who gets the win or loss with decision: true")
            elif decisions > 1:
                out.error(base, f"{team} has two goalies marked with the decision. Only one gets the win or loss.")
        elif decisions and isinstance(rows[0], dict):
            out.warning(_path(base, 0, "decision"), f"decision isn't needed when {team} used one goalie: that goalie gets it. Take it out.")
        _check_ga_total(out, side, base, gas, goals, goals_ok)


def _check_goalie_number(out, row, at, side, rosters, seen):
    nat = _path(at, "num")
    value = row.get("num")
    if value is None:
        out.empty(nat, "is empty. Write the goalie's jersey number.")
        return
    key = _roster_number(out, rosters, side, value, nat, "the goalie")
    if key is not None:
        if key in seen:
            out.error(nat, f"goalie #{value} is listed twice for {out.team(side)}")
        seen.append(key)


def _check_goalie_numbers(out, row, at):
    """`ga` and `shots` of one goalie row. Returns the goals against when it is a usable number, else None."""
    ga = row.get("ga")
    gat = _path(at, "ga")
    usable = None
    if ga is None:
        out.empty(gat, "is empty. Write the goals against (0 for a shutout).")
    elif not _is_int(ga) or ga < 0:
        out.error(gat, f"{ga!r} should be a whole number of goals against, 0 or more")
    else:
        usable = ga
    shots = row.get("shots")
    sat = _path(at, "shots")
    if not _shots_recorded(out.ctx):
        if shots is not None:
            out.error(sat, "this league doesn't record shots against (rules.goalie_shots is none): take 'shots' out, or set "
                           "rules.goalie_shots to recorded")
    elif shots is None:
        out.empty(sat, "is empty. Write the shots against this goalie (this league records them).")
    elif not _is_int(shots) or shots < 0:
        out.error(sat, f"{shots!r} should be a whole number of shots, 0 or more")
    elif usable is not None and shots < usable:
        out.error(sat, f"{shots} shots against but {usable} goals against: a goalie faces at least as many shots as goals")
    return usable


def _check_ga_total(out, side, base, gas, goals, goals_ok):
    """The goalies' GA add up to the other team's goals in the periods and OT, empty-net goals left out."""
    if not goals_ok or not gas or any(g is None for g in gas):
        return
    against = [g for g in goals if g and g["side"] == _other(side)]
    empty_net = sum(1 for g in against if g["en"])
    expected = len(against) - empty_net
    if sum(gas) != expected:
        scorer = out.team(_other(side))
        tail = ", none into an empty net" if not empty_net else f", {empty_net} of them into an empty net (those aren't charged to a goalie)"
        out.error(base, f"the GA boxes add up to {sum(gas)}, but {scorer} scored {len(against)}{tail}: check the GA boxes and the goal lines")


# ---- the score boxes, overtime and the shootout

def _check_score(out, sheet, rosters, goals, goals_ok):
    ctx = out.ctx
    count = _periods(ctx)
    score = sheet.get("score")
    boxes = {side: None for side in SIDES}
    if score is None:
        out.empty("score", "is empty. Copy the score by periods boxes for both teams.")
    elif not isinstance(score, dict):
        out.error("score", "should have the boxes for home and away, like 'home: {periods: [2, 1, 2], final: 5}'")
    else:
        for key in score:
            if key not in SIDES:
                out.error(_path("score", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
        for side in SIDES:
            boxes[side] = _check_score_side(out, score.get(side), side, count)
    facts = _game_shape(ctx, goals, goals_ok, boxes)
    if facts["reg"] is not None and goals_ok:
        _check_boxes_against_goals(out, boxes, goals, facts, count)
    _check_overtime(out, sheet, boxes, goals, goals_ok, facts)
    winner = _check_shootout_block(out, sheet, rosters, facts)
    _check_shootout_boxes(out, boxes, facts, winner)
    _check_final_boxes(out, boxes)


def _check_score_side(out, block, side, count):
    """The syntax of one side's boxes. Returns {periods, ot, so, final} as written (None where not usable), or
    None when the side has no boxes."""
    team = out.team(side)
    base = _path("score", side)
    if block is None:
        out.empty(base, f"is empty. Copy {team}'s score by periods boxes.")
        return None
    if not isinstance(block, dict):
        out.error(base, f"should be like {{periods: [2, 1, 2], final: 5}} for {team}")
        return None
    for key in block:
        if key not in SCORE_SIDE_KEYS:
            out.error(_path(base, key), f"'{key}' isn't a score box. Use one of: {', '.join(SCORE_SIDE_KEYS)}.")
    result = {"periods": None, "ot": block.get("ot"), "so": block.get("so"), "final": None}
    periods = block.get("periods")
    pat = _path(base, "periods")
    if periods is None:
        out.empty(pat, f"is empty. Write {team}'s goals in each of the {count} periods.")
    elif not isinstance(periods, list) or len(periods) != count:
        out.error(pat, f"this league plays {count} periods: write {count} boxes for {team}")
    else:
        values = []
        for i, v in enumerate(periods):
            at = _path(pat, i)
            if v is None:
                out.empty(at, f"is empty. Write {team}'s goals in period {i + 1} (0 if none).")
                values.append(None)
            elif not _is_int(v) or v < 0:
                out.error(at, f"{v!r} isn't a score for period {i + 1}: write a whole number, 0 or more")
                values.append(None)
            else:
                values.append(v)
        result["periods"] = values
    for key in ("ot", "so"):
        v = block.get(key)
        if v is not None and (not _is_int(v) or v < 0):
            out.error(_path(base, key), f"{v!r} should be a whole number, 0 or more, or empty when not played")
            result[key] = None
    final = block.get("final")
    fat = _path(base, "final")
    if final is None:
        out.empty(fat, f"is empty. Copy {team}'s Final box.")
    elif not _is_int(final) or final < 0:
        out.error(fat, f"the Final box for {team} should be a whole number, not {final!r}")
    else:
        result["final"] = final
    return result


def _game_shape(ctx, goals, goals_ok, boxes):
    """What kind of game this is, from the goal lines (or the period boxes when the goals can't be used):
    regulation goals per side, overtime goals per side (None when not known), and whether overtime and a
    shootout belong in this game."""
    count = _periods(ctx)
    reg = ot = None
    if goals_ok:
        reg = {s: sum(1 for g in goals if g and g["side"] == s and g["period"] <= count) for s in SIDES}
        ot = {s: sum(1 for g in goals if g and g["side"] == s and g["period"] > count) for s in SIDES}
    elif all(boxes[s] and boxes[s]["periods"] and None not in boxes[s]["periods"] for s in SIDES):
        reg = {s: sum(boxes[s]["periods"]) for s in SIDES}
    level = None if reg is None else reg["home"] == reg["away"]
    if ctx.game_type == "playoff":
        ot_rule = True
        so_rule = _option(ctx, "playoff_overtime", "sudden_death") == "shootout"
    else:
        mode = _option(ctx, "overtime", "none")
        ot_rule, so_rule = mode in ("overtime", "shootout"), mode in ("shootout", "shootout_only")
    ot_total = None if ot is None else ot["home"] + ot["away"]
    so_allowed = None
    if level is not None:
        so_allowed = level and so_rule
        if so_allowed and ot_rule:
            so_allowed = None if ot_total is None else ot_total == 0
    return {"reg": reg, "ot": ot, "level": level, "ot_rule": ot_rule, "so_rule": so_rule,
            "ot_allowed": None if level is None else (level and ot_rule), "so_allowed": so_allowed, "ot_total": ot_total}


def _check_boxes_against_goals(out, boxes, goals, facts, count):
    for side in SIDES:
        box = boxes[side]
        if not box or not box["periods"]:
            continue
        for i, v in enumerate(box["periods"]):
            if v is None:
                continue
            have = sum(1 for g in goals if g and g["side"] == side and g["period"] == i + 1)
            if v != have:
                out.error(_path("score", side, "periods", i), f"the box says {v}, but the goal lines have {have} for "
                                                              f"{out.team(side)} in period {i + 1}")


def _check_overtime(out, sheet, boxes, goals, goals_ok, facts):
    ctx = out.ctx
    count = _periods(ctx)
    allowed = facts["ot_allowed"]
    reg = facts["reg"]
    kind = "playoff" if ctx.game_type == "playoff" else "regular-season"
    # overtime goal lines in a game that has no overtime, and a second goal in a sudden-death overtime
    if goals_ok and allowed is not None:
        first = True
        for i, g in enumerate(goals):
            if not g or g["period"] <= count:
                continue
            if not allowed:
                out.error(_path("goals", i, "period"), _no_overtime_reason(out, facts, kind) + " Take this goal out, or fix the period.")
            elif not first:
                out.error(_path("goals", i, "period"), "overtime ends on the first goal, so there is only one overtime goal in a game. "
                                                       "Check the period of this goal.")
            first = False
    for side in SIDES:
        box = boxes[side]
        if not box:
            continue
        at = _path("score", side, "ot")
        value = box["ot"]
        if allowed is False and value is not None:
            out.error(at, _no_overtime_reason(out, facts, kind) + " Leave the OT box empty.")
        elif allowed is True:
            if value is None:
                out.empty(at, f"is empty. The game was level after {count} periods, so overtime was played: write "
                              f"{out.team(side)}'s overtime goals (0 for a scoreless overtime).")
            elif facts["ot"] is not None and value != facts["ot"][side]:
                out.error(at, f"the OT box says {value}, but the goal lines have {facts['ot'][side]} for {out.team(side)} in overtime")


def _no_overtime_reason(out, facts, kind):
    reg = facts["reg"]
    if not facts["level"]:
        return f"The game wasn't level after the periods ({reg['home']}-{reg['away']}), so there was no overtime."
    return (f"A {kind} game that is level after the periods doesn't go to overtime in this league "
            f"(rules.{'playoff_overtime' if kind == 'playoff' else 'overtime'}).")


def _no_shootout_reason(out, facts):
    """Why this game has no shootout, for the shootout block and the SO boxes (only called when so_allowed is False)."""
    reg = facts["reg"]
    if not facts["level"]:
        return f"The game wasn't level after the periods ({reg['home']}-{reg['away']}), so there was no shootout."
    if facts["so_rule"]:
        return "The game was decided in overtime, so there was no shootout."
    if out.ctx.game_type == "playoff":
        return ("A level playoff game in this league plays overtime periods until a goal, with no shootout "
                "(rules.playoff_overtime).")
    if facts["ot_rule"]:
        return "A regular-season game still level after overtime is a tie in this league, with no shootout (rules.overtime)."
    return "A regular-season game level after the periods is a tie in this league, with no shootout (rules.overtime)."


def _check_shootout_block(out, sheet, rosters, facts):
    """The `shootout` block. Returns the winning side when it can be told."""
    value = sheet.get("shootout")
    allowed = facts["so_allowed"]
    if value is None:
        if allowed:
            out.empty("shootout", "is empty. The game was still level after overtime, so a shootout was played: fill in who shot "
                                  "and who scored.")
        return None
    if allowed is False:
        out.error("shootout", _no_shootout_reason(out, facts) + " Take 'shootout' out.")
        return None
    return _check_shootout(out, value, rosters)


def _check_shootout(out, value, rosters):
    ctx = out.ctx
    if not isinstance(value, dict):
        out.error("shootout", "should be like {first: home, home: [{num: 12, scored: true}], away: [...]}")
        return None
    for key in value:
        if key not in SHOOTOUT_KEYS:
            out.error(_path("shootout", key), f"'{key}' isn't part of a shootout. Use one of: {', '.join(SHOOTOUT_KEYS)}.")
    first = value.get("first")
    if first is None:
        out.empty("shootout.first", "is empty. Which team shot first, home or away? (It decides when a shootout can stop early.)")
    elif not _side_ok(first):
        out.error("shootout.first", f"first {first!r} should be home or away")
        first = None
    results, usable = {}, True
    for side in SIDES:
        team = out.team(side)
        base = _path("shootout", side)
        rows = value.get(side)
        if rows is None:
            out.empty(base, f"is empty. List {team}'s shooters in order, like [{{num: 12, scored: true}}].")
            usable = False
            continue
        if not isinstance(rows, list):
            out.error(base, f"should be a list of {team}'s shooters, like [{{num: 12, scored: true}}]")
            usable = False
            continue
        results[side] = []
        for i, row in enumerate(rows):
            at = _path(base, i)
            if not isinstance(row, dict):
                out.error(at, "an attempt looks like {num: 12, scored: true}")
                usable = False
                continue
            for key in row:
                if key not in ATTEMPT_KEYS:
                    out.error(_path(at, key), f"'{key}' isn't part of an attempt. Use one of: {', '.join(ATTEMPT_KEYS)}.")
            if row.get("num") is None:
                out.empty(_path(at, "num"), "is empty. Write the shooter's jersey number.")
            else:
                _roster_number(out, rosters, side, row["num"], _path(at, "num"), "the shooter")
            scored = row.get("scored")
            if scored is None:
                out.empty(_path(at, "scored"), "is empty. Write true if the shot scored, false if it didn't.")
                usable = False
            elif not isinstance(scored, bool):
                out.error(_path(at, "scored"), f"{scored!r} should be true or false")
                usable = False
            else:
                results[side].append(scored)
    if not usable or len(results) != 2:
        return None
    tally = {s: sum(results[s]) for s in SIDES}
    if tally["home"] == tally["away"]:
        out.error("shootout", f"the shootout is level {tally['home']}-{tally['away']}, but a shootout ends with a winner: check the "
                              "shots, or add the shots that decided it")
        return None
    winner = "home" if tally["home"] > tally["away"] else "away"
    if first is not None:
        problem = _shootout_fit(first, results, _rounds(ctx))
        if problem == "after":
            out.warning("shootout", "there are shots after the shootout was already decided: check the list")
        elif problem == "missing":
            out.warning("shootout", f"the shootout isn't complete: a round is missing (each team shoots {_rounds(ctx)} times, then "
                                    "one each until someone leads after a round, unless one team can no longer catch up)")
    return winner


def _shootout_decided(n, g, rounds):
    """Whether the shootout is over after n shots each so far, with g goals: nobody can catch up, or every round
    is done and (in sudden death) a round is level no more."""
    def left(side, other):
        return max(rounds - n[side], 0) if n[side] < rounds else max(n[other] - n[side], 0)
    return g["home"] > g["away"] + left("away", "home") or g["away"] > g["home"] + left("home", "away")


def _shootout_fit(first, results, rounds):
    """None when the shots fit the rounds, "after" when shots follow the one that decided it, "missing" when it stops
    before it was decided."""
    second = _other(first)
    n, g = {"home": 0, "away": 0}, {"home": 0, "away": 0}
    while True:
        if _shootout_decided(n, g, rounds):
            return "after" if any(n[s] < len(results[s]) for s in SIDES) else None
        shooter = first if n[first] == n[second] else second
        if n[shooter] >= len(results[shooter]):
            return "missing"
        g[shooter] += 1 if results[shooter][n[shooter]] else 0
        n[shooter] += 1


def _check_shootout_boxes(out, boxes, facts, winner):
    allowed = facts["so_allowed"]
    if allowed is None:
        return
    filled = {}
    for side in SIDES:
        box = boxes[side]
        if not box:
            continue
        at = _path("score", side, "so")
        value = box["so"]
        if not allowed:
            if value is not None:
                out.error(at, _no_shootout_reason(out, facts) + " Leave the SO box empty.")
        elif value is None:
            out.empty(at, f"is empty. The game went to a shootout: write 1 for the winning team and 0 for the other.")
        elif value not in (0, 1):
            out.error(at, f"{value!r} should be 1 for the shootout winner and 0 for the other team")
        else:
            filled[side] = value
    if allowed and len(filled) == 2:
        if winner is not None:
            for side in SIDES:
                want = 1 if side == winner else 0
                if filled[side] != want:
                    out.error(_path("score", side, "so"), f"the SO box says {filled[side]}, but {out.team(winner)} won the shootout: "
                                                          "write 1 for the winner and 0 for the other team")
        elif filled["home"] + filled["away"] != 1:
            out.error(_path("score", "home", "so"), "write 1 in the SO box of the shootout winner and 0 in the other's")


def _check_final_boxes(out, boxes):
    for side in SIDES:
        box = boxes[side]
        if not box or box["final"] is None or box["periods"] is None or None in box["periods"]:
            continue
        total = sum(box["periods"]) + (box["ot"] or 0) + (box["so"] or 0)
        if box["final"] != total:
            out.error(_path("score", side, "final"), f"the Final box says {box['final']}, but the periods, overtime and shootout "
                                                     f"add up to {total}")


# ------------------------------------------------------------------ read

def read(sheet, ctx):
    """The numbers of a sheet `check` accepted (warnings allowed). Arithmetic only."""
    count = _periods(ctx)
    rosters = _read_rosters(sheet)
    goals = _read_goals(sheet, ctx, rosters)
    penalties = _read_penalties(sheet, ctx, rosters)
    goalies = _read_goalies(sheet, rosters)
    shootout = _read_shootout(sheet, rosters)
    regulation = {s: [sum(1 for g in goals if g["side"] == s and g["raw_period"] == p) for p in range(1, count + 1)] for s in SIDES}
    ot_goals = {s: sum(1 for g in goals if g["side"] == s and g["period_index"] > count) for s in SIDES}
    ot_played = any(g["period_index"] > count for g in goals) or any(
        isinstance(((sheet.get("score") or {}).get(s) or {}).get("ot"), int) for s in SIDES)
    so_played = shootout is not None
    so_goal = {s: 1 if so_played and shootout["winner"] == s else 0 for s in SIDES}
    extra = {}
    if ot_played or so_played:
        extra = {s: ([ot_goals[s]] if ot_played else []) + ([so_goal[s]] if so_played else []) for s in SIDES}
    final = {s: sum(regulation[s]) + ot_goals[s] + so_goal[s] for s in SIDES}
    decided_in = "shootout" if so_played else "overtime" if any(ot_goals.values()) else "regulation"
    score = Score(final=final, periods=regulation, extra=extra, decided_in=decided_in,
                  final_at={s: f"sheet.score.{s}.final" for s in SIDES})
    _mark_gwg(goals, so_played)
    lines = _read_lines(goals, penalties, goalies, rosters, score, ctx, shootout)
    pim = {s: sum(p["minutes"] for p in penalties if p["side"] == s) for s in SIDES}
    facts = {
        "periods": count,
        "clock": _option(ctx, "clock", "elapsed"),
        "ot_played": ot_played,
        "so_played": so_played,
        "goals": [_goal_fact(g) for g in goals],
        "penalties": [_penalty_fact(p) for p in penalties],
        "goalies": goalies,
        "shootout": shootout,
        "pim": pim,
    }
    return Reading(score=score, lines=lines, team_lines={}, facts=facts)


def _read_rosters(sheet):
    """{side: {number key: {"player": id or None, "name": text or None, "num": the number as written}}}."""
    out = {}
    for side in SIDES:
        rows = ((sheet.get("roster") or {}).get(side)) or []
        out[side] = {}
        for row in rows:
            key = _num_key(row.get("num")) if isinstance(row, dict) else None
            if key is not None and key not in out[side]:
                out[side][key] = {"player": row.get("player"), "name": row.get("name"), "num": row.get("num")}
    return out


def _who(rosters, side, key):
    row = rosters[side].get(key) if key is not None else None
    return {"num": row["num"] if row else None, "player": row["player"] if row else None, "name": row["name"] if row else None}


def _read_goals(sheet, ctx, rosters):
    """The goal lines in time order (by period, then the clock, then the order written), each with its running score."""
    rows = []
    for i, row in enumerate(sheet.get("goals") or []):
        g = _goal_row(row, ctx)
        if g is None or g["side"] is None or g["period"] is None:
            continue
        g["index"] = i
        g["period_index"] = g["period"]
        g["raw_period"] = g["period"]
        g["time"] = row.get("time")
        g["written_period"] = row.get("period")
        rows.append(g)
    rows.sort(key=lambda g: (g["period_index"], _time_key(g["secs"], ctx), g["index"]))
    score = {"home": 0, "away": 0}
    for g in rows:
        score[g["side"]] += 1
        g["number"] = score[g["side"]]
        g["score"] = dict(score)
        g["scorer"] = _who(rosters, g["side"], g["num"])
        g["helpers"] = [_who(rosters, g["side"], a) for a in g["assists"] if a is not None]
        g["gwg"] = False
    return rows


def _mark_gwg(goals, so_played):
    """The goal that gave the winner one more than the loser's final total (none after a tie or a shootout)."""
    if so_played or not goals:
        return
    total = {s: sum(1 for g in goals if g["side"] == s) for s in SIDES}
    if total["home"] == total["away"]:
        return
    winner = "home" if total["home"] > total["away"] else "away"
    needed = total[_other(winner)] + 1
    for g in goals:
        if g["side"] == winner and g["number"] == needed:
            g["gwg"] = True


def _goal_fact(g):
    return {"period": g["written_period"], "time": g["time"], "side": g["side"], "num": g["scorer"]["num"],
            "player": g["scorer"]["player"], "name": g["scorer"]["name"],
            "assists": [{"num": h["num"], "player": h["player"], "name": h["name"]} for h in g["helpers"]],
            "strength": g["strength"], "en": g["en"], "ps": g["ps"], "gwg": g["gwg"],
            "score": [g["score"]["home"], g["score"]["away"]]}


def _read_penalties(sheet, ctx, rosters):
    rows = []
    for i, row in enumerate(sheet.get("penalties") or []):
        p = _penalty_row(row, ctx)
        if p is None or p["side"] is None or p["period"] is None:
            continue
        p.update({"index": i, "time": row.get("time"), "written_period": row.get("period"),
                  "infraction": row.get("infraction"), "who": _who(rosters, p["side"], p["num"]),
                  "served": _who(rosters, p["side"], p["served_by"])})
        rows.append(p)
    rows.sort(key=lambda p: (p["period"], _time_key(p["secs"], ctx), p["index"]))
    return rows


def _penalty_fact(p):
    fact = {"period": p["written_period"], "time": p["time"], "side": p["side"], "infraction": p["infraction"],
            "minutes": p["minutes"], "bench": p["bench"]}
    if p["bench"]:
        fact.update({"num": BENCH, "player": None, "name": None,
                     "served_by": p["served"] if p["served_by"] is not None else None})
    else:
        fact.update({"num": p["who"]["num"], "player": p["who"]["player"], "name": p["who"]["name"], "served_by": None})
    return fact


def _read_goalies(sheet, rosters):
    """{side: [{num, player, name, ga, shots, decision}]} as written (decision a true/false)."""
    out = {s: [] for s in SIDES}
    for side in SIDES:
        for row in ((sheet.get("goalies") or {}).get(side)) or []:
            key = _num_key(row.get("num")) if isinstance(row, dict) else None
            if key is None:
                continue
            who = _who(rosters, side, key)
            ga, shots = row.get("ga"), row.get("shots")
            out[side].append({"num": who["num"] if who["num"] is not None else row.get("num"), "key": key,
                              "player": who["player"], "name": who["name"],
                              "ga": ga if _is_int(ga) else 0, "shots": shots if _is_int(shots) else None,
                              "decision": row.get("decision") is True})
    return out


def _read_shootout(sheet, rosters):
    value = sheet.get("shootout")
    if not isinstance(value, dict):
        return None
    shots = {}
    for side in SIDES:
        rows = value.get(side)
        shots[side] = [r for r in rows if isinstance(r, dict) and isinstance(r.get("scored"), bool)] if isinstance(rows, list) else []
    if not shots["home"] and not shots["away"]:
        return None
    first = value.get("first") if _side_ok(value.get("first")) else "home"
    second = _other(first)
    attempts = []
    for k in range(max(len(shots["home"]), len(shots["away"]))):
        for side in (first, second):
            if k < len(shots[side]):
                row = shots[side][k]
                who = _who(rosters, side, _num_key(row.get("num")))
                attempts.append({"side": side, "num": who["num"] if who["num"] is not None else row.get("num"),
                                 "player": who["player"], "name": who["name"], "scored": row["scored"]})
    tally = {s: sum(1 for r in shots[s] if r["scored"]) for s in SIDES}
    winner = "home" if tally["home"] > tally["away"] else "away" if tally["away"] > tally["home"] else None
    return {"first": first, "attempts": attempts, "tally": tally, "winner": winner}


def _read_lines(goals, penalties, goalies, rosters, score, ctx, shootout):
    lines = []
    played_goalie = {s: {g["key"] for g in goalies[s]} for s in SIDES}
    for side in SIDES:
        for key, row in rosters[side].items():
            if not row["player"] or key in played_goalie[side]:
                continue
            if _dressed_backup(row["player"], side, key, goals, penalties, shootout, ctx):
                continue                                   # owner decision: a backup goalie who did not play gets no game
            lines.append(Line(side=side, player=row["player"], group="skater", counts=_skater_counts(side, key, goals, penalties)))
    for side in SIDES:
        record = _goalie_of_record(goalies[side])
        against = [g for g in goals if g["side"] == _other(side)]
        for g in goalies[side]:
            if not g["player"]:
                continue
            lines.append(Line(side=side, player=g["player"], group="goalie",
                              counts=_goalie_counts(side, g, g is record, goalies[side], against, goals, penalties, score)))
    return lines


def _dressed_backup(player, side, key, goals, penalties, shootout, ctx):
    """A roster row marked as a goalie (position goalie in players.yml) who is not in `goalies`, so did not play in net,
    and did nothing on the sheet as a skater (no goal, assist, penalty or shootout shot)."""
    who = ctx.players.get(player) if isinstance(player, str) else None
    if who is None or who.position != "goalie":
        return False
    if any(g["side"] == side and (g["num"] == key or key in g["assists"]) for g in goals):
        return False
    if any(p["side"] == side and (p["num"] == key or p.get("served_by") == key) for p in penalties):
        return False
    if shootout and any(a["side"] == side and _num_key(a["num"]) == key for a in shootout["attempts"]):
        return False
    return True


def _skater_counts(side, key, goals, penalties):
    mine = [g for g in goals if g["side"] == side and g["num"] == key]
    helped = sum(1 for g in goals if g["side"] == side and key in g["assists"])
    scored = len(mine)
    return {"g": scored, "a": helped, "pts": scored + helped,
            "pim": sum(p["minutes"] for p in penalties if p["side"] == side and p["num"] == key and not p["bench"]),
            "ppg": sum(1 for g in mine if g["strength"] == "PP"),
            "shg": sum(1 for g in mine if g["strength"] == "SH"),
            "gwg": sum(1 for g in mine if g["gwg"])}


def _goalie_of_record(rows):
    if len(rows) == 1:
        return rows[0]
    return next((g for g in rows if g["decision"]), None)


def _goalie_counts(side, row, is_record, side_rows, against, goals, penalties, score):
    key = row["key"]
    counts = {"w": 0, "l": 0, "t": 0, "otl": 0, "ga": row["ga"], "sa": row["shots"] or 0, "sho": 0,
              "a": sum(1 for g in goals if g["side"] == side and key in g["assists"]),
              "pim": sum(p["minutes"] for p in penalties if p["side"] == side and p["num"] == key and not p["bench"])}
    if is_record:
        mine, theirs = score.final[side], score.final[_other(side)]
        if mine > theirs:
            counts["w"] = 1
        elif mine < theirs:
            counts["l"] = 1
            counts["otl"] = 1 if score.decided_in != "regulation" else 0
        else:
            counts["t"] = 1
    if len(side_rows) == 1 and not against:
        counts["sho"] = 1
    return counts


# ------------------------------------------------------------------ present

SCORING_TITLE = "Scoring"
PENALTIES_TITLE = "Penalties"
GOALIES_TITLE = "Goalies"
SKATERS_TITLE = "Skaters"
SKATERS_INTRO = "Players with a goal, assist or penalty."
NO_SCORING = "No scoring"
GAME_LINK = "Game sheet"


def present(reading, ctx):
    return {"line_score": _line_score(reading, ctx), "card": _card(reading, ctx), "tiles": None,
            "blocks": _blocks(reading, ctx)}


def _line_score(reading, ctx):
    score, facts = reading.score, reading.facts
    line = ctx.sport["line_score"]
    count = facts["periods"]
    labels = [str(i + 1) for i in range(count)]
    series = {s: list(score.periods[s]) for s in SIDES}
    extra = [dict(zip(SIDES, v)) for v in zip(*[score.extra.get(s, []) for s in SIDES])] if score.extra else []
    names = (["OT"] if facts["ot_played"] else []) + (["SO"] if facts["so_played"] else [])
    for name, values in zip(names, extra):
        labels.append(name)
        for s in SIDES:
            series[s].append(values[s])
    rows = {s: {"cells": [{"v": v} for v in series[s]], "total": score.final[s], "extra": None, "hammer_first": False}
            for s in SIDES}
    return {"shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
            "columns": [{"label": label} for label in labels], "rows": rows, "won_word": None, "mark_word": None,
            "legend": [], "note": None, "split": _split(reading, ctx)}


def _split(reading, ctx):
    """The two lines under the line score: the goalies, and the penalty minutes (home first)."""
    goalies = reading.facts["goalies"]
    lines = []
    runs = [{"t": "Goalies: "}]
    for side in SIDES:
        names = [_goalie_label(ctx, g) for g in goalies[side]]
        if not names:
            continue
        if len(runs) > 1:
            runs.append({"t": " · "})
        for k, name in enumerate(names):
            if k:
                runs.append({"t": " / "})
            runs.append({"t": name, "b": True})
    if len(runs) > 1:
        lines.append(runs)
    pim = reading.facts["pim"]
    lines.append([{"t": f"PIM {pim['home']}–{pim['away']}"}])
    return lines


def _goalie_label(ctx, g):
    if g["player"]:
        return _player_label(ctx, g["player"])
    return f"#{g['num']} {g['name']}" if g["name"] else f"#{g['num']}"


def _person(ctx, who):
    """How a player shows: the label from players.yml, else the name written on the sheet, else the number."""
    if who["player"]:
        return _player_label(ctx, who["player"])
    if who["name"]:
        return f"#{who['num']} {who['name']}" if who["num"] is not None else who["name"]
    return f"#{who['num']}" if who["num"] is not None else "?"


def _card(reading, ctx):
    score, facts = reading.score, reading.facts
    card = {"note": None, "strong": None, "link_label": GAME_LINK, "meta_extra": []}
    if score.decided_in == "shootout":
        card["note"] = "Won in a shootout"
    elif score.final["home"] == score.final["away"]:
        card["note"] = "Tie"
    else:
        winning = next((g for g in facts["goals"] if g["gwg"]), None)
        if winning:
            who = _person(ctx, {"player": winning["player"], "name": winning["name"], "num": winning["num"]})
            card["note"], card["strong"] = f"GWG {who}", who
    return card


def _blocks(reading, ctx):
    blocks = [_events(reading, ctx)]
    penalties = _penalties(reading, ctx)
    if penalties:
        blocks.append(penalties)
    goalies = _goalies_group(reading, ctx)
    if goalies:
        blocks.append(goalies)
    blocks.append(_skaters_group(reading, ctx))
    return blocks


def _events(reading, ctx):
    facts, score = reading.facts, reading.score
    count = facts["periods"]
    word = ctx.sport["words"]["period"]["one"].lower()
    groups = []
    ot_levels = 0
    for g in facts["goals"]:
        if isinstance(g["period"], str):
            ot_levels = max(ot_levels, 1 if g["period"] == "OT" else int(g["period"][2:]))
    if facts["ot_played"]:
        ot_levels = max(ot_levels, 1)
    labels = [(p, f"{_ordinal(p)} {word}") for p in range(1, count + 1)]
    for n in range(1, ot_levels + 1):
        labels.append(("OT" if n == 1 else f"OT{n}", "Overtime" if n == 1 else f"{_ordinal(n)} overtime"))
    for key, label in labels:
        goals = [g for g in facts["goals"] if g["period"] == key]
        events = [{"time": g["time"], "side": g["side"], "player": g["player"], "name": _scorer_text(ctx, g),
                   "badge": "GWG" if g["gwg"] else None, "sub": _assist_line(ctx, g),
                   "score": f"{g['score'][0]}–{g['score'][1]}"} for g in goals]
        groups.append({"label": label, "tally": [{"side": s, "n": sum(1 for g in goals if g["side"] == s)} for s in SIDES],
                       "empty": NO_SCORING, "events": events})
    shootout = facts["shootout"]
    if shootout:
        running = {s: 0 for s in SIDES}
        events = []
        for k, a in enumerate(shootout["attempts"]):
            running[a["side"]] += 1 if a["scored"] else 0
            events.append({"time": f"Shot {k // 2 + 1}", "side": a["side"], "player": a["player"],
                           "name": _person(ctx, a), "badge": None, "sub": "Scored" if a["scored"] else "Missed",
                           "score": f"{running['home']}–{running['away']}"})
        groups.append({"label": "Shootout", "tally": [{"side": s, "n": shootout["tally"][s]} for s in SIDES], "empty": NO_SCORING,
                       "events": events})
    first = _team_name(ctx, "home")
    clock = "left in the period" if facts["clock"] == "remaining" else "elapsed in the period"
    return {"type": "events", "title": SCORING_TITLE, "groups": groups,
            "note": f"Score shown {first} first. Times are time {clock}."}


def _scorer_text(ctx, g):
    """"#12 Gord P." and, after it, the marks of the goal: "#12 Gord P. (PP, EN)"."""
    marks = []
    if g["strength"] in ("PP", "SH"):
        marks.append(g["strength"])
    if g["en"]:
        marks.append("EN")
    if g["ps"]:
        marks.append("PS")
    who = _person(ctx, {"player": g["player"], "name": g["name"], "num": g["num"]})
    return f"{who} ({', '.join(marks)})" if marks else who


def _assist_line(ctx, g):
    if not g["assists"]:
        return "Unassisted"
    return "Assists: " + ", ".join(_person(ctx, a) for a in g["assists"])


def _penalties(reading, ctx):
    rows = []
    for p in reading.facts["penalties"]:
        period = p["period"] if isinstance(p["period"], str) else str(p["period"])
        row = {"period": period, "time": p["time"], "side": p["side"], "player": None, "text": None,
               "infraction": p["infraction"], "minutes": p["minutes"]}
        if p["bench"]:
            served = p["served_by"]
            row["text"] = "Bench" + (f" (served by {_person(ctx, served)})" if served else "")
        elif p["player"]:
            row["player"] = p["player"]
        else:
            row["text"] = _person(ctx, {"player": None, "name": p["name"], "num": p["num"]})
        rows.append(row)
    if not rows:
        return None
    return {"type": "penalties", "title": PENALTIES_TITLE, "rows": rows, "legend": list(SIDES)}


def _result_word(counts):
    if counts["w"]:
        return "W"
    if counts["otl"]:
        return "OTL"
    if counts["l"]:
        return "L"
    if counts["t"]:
        return "T"
    return "–"


def _save_pct(shots, ga):
    """".912": the saves over the shots, three places, half up, no leading zero."""
    text = str((Decimal(shots - ga) / Decimal(shots)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    return text[1:] if text.startswith("0") else text


def _goalies_group(reading, ctx):
    recorded = reading.facts["goalies"]
    if not any(recorded[s] for s in SIDES):
        return None
    shots = _shots_recorded(ctx)
    columns = [{"key": "result", "label": "Result", "title": "Result for the goalie", "key_col": False, "style": "strong"},
               {"key": "ga", "label": "GA", "title": "Goals against", "key_col": True, "style": "big"}]
    if shots:
        columns += [{"key": "sa", "label": "SA", "title": "Shots against", "key_col": False},
                    {"key": "sv", "label": "SV%", "title": "Save percentage", "key_col": False}]
    by_player = {ln.player: ln for ln in reading.lines if ln.group == "goalie"}
    rows = []
    for side in SIDES:
        for g in recorded[side]:
            if not g["player"] or g["player"] not in by_player:
                continue
            counts = by_player[g["player"]].counts
            cells = {"result": _result_word(counts), "ga": str(counts["ga"])}
            if shots:
                cells["sa"] = str(g["shots"]) if g["shots"] is not None else "–"
                cells["sv"] = _save_pct(g["shots"], counts["ga"]) if g["shots"] else "–"
            rows.append({"player": g["player"], "side": side, "cells": cells})
    if not rows:
        return None
    table = {"type": "stat_table", "title": None, "side": None, "caption": "Goalies", "team_col": True, "player_label": "Goalie",
             "columns": columns, "rows": rows, "totals": None, "note": None}
    return {"type": "group", "title": GOALIES_TITLE, "intro": None, "note": _goalie_note(reading, ctx), "blocks": [table]}


def _goalie_note(reading, ctx):
    recorded = reading.facts["goalies"]
    two = [s for s in SIDES if len(recorded[s]) == 2]
    if not two:
        return "Both goalies played the full game."
    parts = []
    for side in two:
        taker = next((g for g in recorded[side] if g["decision"]), None)
        text = f"{_team_name(ctx, side)} used two goalies"
        parts.append(text + (f"; {_goalie_label(ctx, taker)} took the decision." if taker else "."))
    return " ".join(parts)


def _skaters_group(reading, ctx):
    columns = [{"key": "g", "label": "G", "title": "Goals", "key_col": False},
               {"key": "a", "label": "A", "title": "Assists", "key_col": False},
               {"key": "pts", "label": "PTS", "title": "Points", "key_col": True},
               {"key": "pim", "label": "PIM", "title": "Penalty minutes", "key_col": False}]
    first_seen = {}
    for g in reading.facts["goals"]:
        for who in [{"side": g["side"], "player": g["player"]}] + [{"side": g["side"], "player": a["player"]} for a in g["assists"]]:
            first_seen.setdefault((who["side"], who["player"]), len(first_seen))
    for p in reading.facts["penalties"]:
        if p["player"]:
            first_seen.setdefault((p["side"], p["player"]), len(first_seen))
    tables = []
    for side in SIDES:
        rows = []
        total = {"g": 0, "a": 0, "pts": 0, "pim": reading.facts["pim"][side]}
        for ln in reading.lines:
            if ln.side != side:
                continue
            c = ln.counts
            g, a, pim = c.get("g", 0), c["a"], c["pim"]
            total["g"] += g
            total["a"] += a
            if g or a or pim:
                rows.append((-(g + a), -g, -pim, first_seen.get((side, ln.player), 10 ** 6), ln.player,
                             {"g": str(g), "a": str(a), "pts": str(g + a), "pim": str(pim)}))
        total["pts"] = total["g"] + total["a"]
        rows.sort(key=lambda r: r[:4])
        if not rows and not total["pim"]:
            continue
        tables.append({"type": "stat_table", "title": None, "side": side, "heading": "small",
                       "caption": f"{_team_name(ctx, side)} skaters", "columns": columns,
                       "rows": [{"player": r[4], "cells": r[5]} for r in rows],
                       "totals": {"label": "Total", "cells": {k: str(v) for k, v in total.items()}}, "note": None})
    return {"type": "group", "title": SKATERS_TITLE, "intro": SKATERS_INTRO, "note": None, "blocks": tables}


# ------------------------------------------------------------------ derive

def derive(counts, group):
    """Goalie rates from summed counts (one game or a season), unrounded: the core rounds them for display and
    ranks on the exact value. GAA is goals against per game played (a rec sheet has no minutes in net); SV% is
    None when no shots were recorded. Skaters have no rates."""
    if group != "goalie":
        return {}
    games, ga, shots = counts.get("gp", 0), counts.get("ga", 0), counts.get("sa", 0)
    return {"gaa": ga / games if games else None,
            "sv_pct": (shots - ga) / shots if shots else None}
