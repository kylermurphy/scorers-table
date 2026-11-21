"""The rules of slo-pitch (docs/stage-5-slopitch-spec.md, sections 2-5): check, read, present, derive.

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.model`, so the
stage 7 JavaScript port can match them line for line. `check` returns every problem, with paths relative to
`sheet` (the core adds `sheet.`), and never changes `sheet` or `ctx`.

The sheet is a copy of a rec scorebook page (the per-inning plate-appearance boxes are not copied):

    runs:                           # one box per inning played, a whole number or X (a bottom half not needed)
      away: [2, 0, 5, 1, 0, 3, 0]
      home: [1, 5, 0, 3, 5, 0, X]
    totals:                         # the R H E boxes as written; h only when the league keeps team hits, e only
      away: {r: 11, h: 15}          # when it keeps errors
      home: {r: 14, h: 18}
    called: mercy                   # only for a game shorter than regulation: mercy time weather darkness other
    bats_first: home                # only after a coin toss: the team in the file as `home` bats first
    batting:                        # the batting order, top to bottom; a line only when the league keeps lines
      away: [{player: norm-w, ab: 4, r: 2, h: 3, rbi: 0, hr: 0, bb: 0}, ...]
      home: [...]

`home` is the team that bats last (the scorebook's "Home" line), `away` the visitors. A box path counts from 0:
`runs.home.6` is the 7th inning's box.

How the numbers come from it: the score is the sum of each side's runs (the R box must agree); the line score
is the runs by inning; a half-inning ended by the run limit is marked; X means the half was not played; a
player's games played is a row in the batting order, and with a batting line the line is his counts.
"""
from __future__ import annotations

from scripts.core.model import Line, Problem, Reading, Score

SIDES = ("home", "away")
SHEET_KEYS = ("runs", "totals", "called", "bats_first", "batting")
TOTALS_KEYS = ("r", "h", "e")
ROW_KEYS = ("player", "name", "ab", "r", "h", "rbi", "hr", "bb")
LINE_KEYS = ("ab", "r", "h", "rbi", "hr", "bb")
CALLED_WORDS = ("mercy", "time", "weather", "darkness", "other")
X = "X"
MAX_EXTRA_BOXES = 10          # a list may be `innings` + 10 boxes long
MAX_RUNS = 99
MAX_LINE = 20
MAX_BATTERS = 30
MAX_BOX = 99
EXTRA_PLAY = 3                # runs beyond the winning run that one play can bring in (a grand slam)

# The option defaults (sport.yml is the source; these keep a context with no options usable).
DEFAULTS = {"innings": 7, "run_limit": 5, "open_innings": "last", "limit_play": "stop", "mercy_runs": 15,
            "mercy_after": 5, "official_innings": 4, "time_limit": 60, "extra_innings": 0, "hr_limit": 0,
            "batting": "optional", "team_hits": "kept", "team_errors": "none"}
GAME_LINK = "Box score"
CALLED_TEXT = {"mercy": "mercy rule", "time": "time limit", "weather": "weather", "darkness": "darkness",
               "other": "called"}


# ------------------------------------------------------------------ small helpers

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _path(*parts):
    return ".".join(str(p) for p in parts)


def _other(side):
    return "away" if side == "home" else "home"


def _opt(ctx, key):
    value = ctx.options.get(key, DEFAULTS[key])
    return DEFAULTS[key] if value is None else value


def _int_opt(ctx, key):
    value = _opt(ctx, key)
    return value if _is_int(value) and value >= 0 else DEFAULTS[key]


def _innings(ctx):
    value = _opt(ctx, "innings")
    return value if _is_int(value) and value > 0 else DEFAULTS["innings"]


def _team_name(ctx, side):
    team = ctx.teams.get(ctx.sides.get(side))
    return team.name if team else side.capitalize()


def _player_label(ctx, player_id):
    player = ctx.players.get(player_id) if isinstance(player_id, str) else None
    return player.label if player else str(player_id)


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _box_ok(v, top):
    return _is_int(v) and 0 <= v <= top


def _sides_order(sheet):
    """(side that bats first, side that bats last). The visitors bat first unless `bats_first: home`."""
    first = "home" if sheet.get("bats_first") == "home" else "away"
    return first, _other(first)


def _limited(i, ctx):
    """Is the inning with 0-based index i limited by the run limit? Open innings (the last regulation inning and
    every extra inning under open_innings 'last') and a league with no limit are not."""
    if _int_opt(ctx, "run_limit") == 0:
        return False
    if _opt(ctx, "open_innings") == "last" and i >= _innings(ctx) - 1:
        return False
    return True


def _limit_cap(ctx):
    limit = _int_opt(ctx, "run_limit")
    return limit + EXTRA_PLAY if _opt(ctx, "limit_play") == "finish" else limit


def _has_line(row):
    return isinstance(row, dict) and any(k in row for k in LINE_KEYS)


def _num(v):
    return v if _is_int(v) else 0


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


# ------------------------------------------------------------------ the game as a whole (shared by check and read)

def _game(lists, sheet, ctx):
    """The facts of a usable `runs` (both lists whole numbers or X, equal length): who bats when, the scores."""
    first, last = _sides_order(sheet)
    n = len(lists[first])
    nums = {s: [0 if v == X else v for v in lists[s]] for s in SIDES}
    total = {s: sum(nums[s]) for s in SIDES}
    return {"first": first, "last": last, "n": n, "nums": nums, "total": total, "lists": lists}


def _after_top(game, k):
    """(runs of the team batting last before inning k, runs of the team batting first through inning k), k from 0."""
    return sum(game["nums"][game["last"]][:k]), sum(game["nums"][game["first"]][:k + 1])


def _level_after(game, k):
    """Level after k whole innings."""
    return sum(game["nums"]["home"][:k]) == sum(game["nums"]["away"][:k])


def _walk_off(game, ctx):
    """The team batting last took the lead in its final half-inning of a game that reached the last regulation
    inning: the game ended there."""
    n, last = game["n"], game["last"]
    if n < _innings(ctx) or game["lists"][last][n - 1] == X:
        return False
    behind, ahead = _after_top(game, n - 1)
    return behind <= ahead and game["total"][last] > game["total"][game["first"]]


# ------------------------------------------------------------------ check

def check(sheet, ctx):
    if not isinstance(sheet, dict):
        return [Problem("error", "", "the sheet should be a block with these lines: " + ", ".join(SHEET_KEYS) + ".")]
    out = _Out(ctx)
    for key in sheet:
        if key not in SHEET_KEYS:
            out.error(str(key), f"'{key}' isn't part of a game sheet. Use one of: {', '.join(SHEET_KEYS)}.")
    _check_bats_first(out, sheet)
    runs = _check_runs(out, sheet)
    game = _game(runs, sheet, ctx) if runs else None
    if game:
        _check_innings(out, game, sheet)
    _check_called(out, sheet, game)
    info = _check_batting(out, sheet, game)
    _check_totals(out, sheet, game, info)
    return out.problems


# ---- bats_first

def _check_bats_first(out, sheet):
    value = sheet.get("bats_first")
    if value is not None and value not in SIDES:
        out.error("bats_first", f"{value!r} isn't a side. Write 'home' when the home team batted first after a coin "
                                "toss, and leave the line out when the visitors batted first.")


# ---- runs

def _check_runs(out, sheet):
    """The runs by inning. Reports each box; returns {side: list} when both lists can be used for the checks that
    follow (whole numbers or X, the same length, X only where it can be), else None."""
    ctx = out.ctx
    value = sheet.get("runs")
    if value is None:
        out.empty("runs", "is empty. Write the runs each team scored in each inning, visitors and home.")
        return None
    if not isinstance(value, dict):
        out.error("runs", "should list the runs for home and away, like 'away: [2, 0, 1]' and 'home: [1, 0, X]'")
        return None
    for key in value:
        if key not in SIDES:
            out.error(_path("runs", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    first, last = _sides_order(sheet)
    top = _innings(ctx) + MAX_EXTRA_BOXES
    lists, usable = {}, True
    for side in SIDES:
        base = _path("runs", side)
        rows = value.get(side)
        team = out.team(side)
        if rows is None:
            out.empty(base, f"is empty. Write the runs {team} scored in each inning, one box each.")
            usable = False
            continue
        if not isinstance(rows, list) or not 1 <= len(rows) <= top:
            count = f"{len(rows)} boxes" if isinstance(rows, list) else "no list of boxes"
            out.error(base, f"{team} has {count}. Runs are a list of 1 to {top} boxes, one for each inning played "
                            "(write X for a bottom half that was not needed).")
            usable = False
            continue
        lists[side] = rows
        for i, v in enumerate(rows):
            at = _path(base, i)
            if v is None:
                out.empty(at, f"is empty. Write {team}'s runs in inning {i + 1}, or X if they did not bat.")
                usable = False
            elif isinstance(v, str) and v == X:
                if side == first:
                    out.error(at, f"X is for the team batting last. {team} batted first, so write their runs.")
                    usable = False
                elif i != len(rows) - 1:
                    out.error(at, f"X can only be in the last inning played: {team} batted in the rest. "
                                  "Write their runs.")
                    usable = False
            elif not _box_ok(v, MAX_RUNS):
                out.error(at, f"{v!r} isn't a number of runs: write a whole number from 0 to {MAX_RUNS}, or X.")
                usable = False
            else:
                _check_limit(out, v, i, at, team)
    if len(lists) == 2 and len(lists["home"]) != len(lists["away"]):
        short = min(SIDES, key=lambda s: len(lists[s]))
        out.error(_path("runs", short), "both teams have a box for every inning played: write X for a bottom half "
                                        "that was not needed.")
        usable = False
    return lists if usable and len(lists) == 2 else None


def _check_limit(out, v, i, at, team):
    ctx = out.ctx
    if not _limited(i, ctx) or v <= _limit_cap(ctx):
        return
    limit = _int_opt(ctx, "run_limit")
    if _opt(ctx, "limit_play") == "finish":
        out.error(at, f"{v} runs is more than the limit of {limit} a half-inning plus the play that reached it "
                      f"({limit + EXTRA_PLAY}): check the box.")
    else:
        out.error(at, f"{v} runs is more than the limit of {limit} a half-inning: check the box.")


def _check_innings(out, game, sheet):
    """The rules that need both lists: X, the walk-off, how many innings."""
    ctx = out.ctx
    first, last, n, nums, total = game["first"], game["last"], game["n"], game["nums"], game["total"]
    innings = _innings(ctx)
    lists = game["lists"]
    behind, ahead = _after_top(game, n - 1)       # the team batting last, and the team batting first, in the final inning
    last_team = out.team(last)
    if lists[last][n - 1] == X:
        if behind <= ahead:
            word = "trailed" if behind < ahead else "was level at"
            out.error(_path("runs", last, n - 1),
                      f"{last_team} {word} {behind}-{ahead} after the top of the {_ordinal(n)}, so they batted: "
                      "write their runs.")
    elif n >= innings and behind > ahead:
        out.warning(_path("runs", last, n - 1),
                    f"{last_team} led {behind}-{ahead} after the top of the {_ordinal(n)}, so the game was over: "
                    "not needed, write X.")
    elif _walk_off(game, ctx):
        needed = ahead - behind + 1
        scored = nums[last][n - 1]
        if scored > needed + EXTRA_PLAY:
            out.warning(_path("runs", last, n - 1),
                        f"{last_team} needed {_plural(needed, 'run')} to win and the game ends when the winning run "
                        f"scores (only a home run brings in more): {scored} runs is a lot, check the box.")
    if n > innings:
        _check_extra_innings(out, game)


def _check_extra_innings(out, game):
    ctx = out.ctx
    innings, n = _innings(ctx), game["n"]
    over = next((k for k in range(innings, n) if not _level_after(game, k)), None)
    if over is not None:
        at = _path("runs", "away", over)
        if over == innings:
            out.error(at, f"the score was not level after {innings} innings, so there is no inning {innings + 1}. "
                          "Take the extra innings out.")
        else:
            out.error(at, f"the game was over after inning {over}: a team led at the end of a complete extra "
                          "inning. Take the later innings out.")
        return
    allowed = _int_opt(ctx, "extra_innings")
    if ctx.game_type != "playoff" and n - innings > allowed:
        what = "no extra innings" if allowed == 0 else f"at most {_plural(allowed, 'extra inning')}"
        out.error(_path("runs", "away", innings + allowed),
                  f"this league plays {what} in the regular season: a game level after "
                  f"{innings + allowed} innings is a tie. Take the extra innings out.")


# ---- called

def _check_called(out, sheet, game):
    ctx = out.ctx
    value = sheet.get("called")
    innings = _innings(ctx)
    n = game["n"] if game else None
    if value is None:
        if n is not None and n < innings:
            out.error("called", f"a {n}-inning game is shorter than {innings}: if it was called, add 'called: mercy', "
                                "'time', 'weather', 'darkness' or 'other' (a game that is replayed stays out of the "
                                "games folder).")
        return
    if not isinstance(value, str) or value not in CALLED_WORDS:
        out.error("called", f"{value!r} isn't a reason. Use one of: {', '.join(CALLED_WORDS)}.")
        return
    if n is None:
        return
    if n >= innings:
        out.error("called", f"the game lasted {n} innings, so it was not called. Take 'called' out.")
        return
    if value == "mercy":
        _check_mercy(out, game)
    official = _int_opt(ctx, "official_innings")
    if n < official:
        out.warning("called", f"fewer than {official} innings were played: does the game count? A game that is "
                              "replayed stays out of the games folder.")


def _check_mercy(out, game):
    ctx = out.ctx
    runs, after = _int_opt(ctx, "mercy_runs"), _int_opt(ctx, "mercy_after")
    if runs == 0:
        out.error("called", "this league has no mercy rule (rules.mercy_runs is 0). Use another reason, or set "
                            "the rule.")
        return
    lead = abs(game["total"]["home"] - game["total"]["away"])
    if lead < runs:
        out.warning("called", f"the mercy rule is a lead of {runs} runs and the lead was {lead}: check the reason.")
    if game["n"] < after:
        out.warning("called", f"the mercy rule applies after {after} innings ({after - 1}½ when the team batting last "
                              f"leads) and {game['n']} were played: check the reason.")


# ---- batting

def _check_batting(out, sheet, game):
    """The batting order and lines. Returns {side: {"lines": bool, "h": sum of H or None}} for the totals check."""
    ctx = out.ctx
    mode = _opt(ctx, "batting")
    info = {s: {"lines": False, "h": None} for s in SIDES}
    value = sheet.get("batting")
    if mode == "none":
        if value is not None:
            out.error("batting", "this league keeps team results only (rules.batting is none), so there is no "
                                 "batting order. Take it out.")
        return info
    if value is None:
        out.empty("batting", "is empty. List each team's batters in batting order (and their lines when the league "
                             "keeps them).")
        return info
    if not isinstance(value, dict):
        out.error("batting", "should list the batters for home and away, like 'home: [...]' and 'away: [...]'")
        return info
    for key in value:
        if key not in SIDES:
            out.error(_path("batting", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    seen = {}
    shown = {}
    for side in SIDES:
        rows = value.get(side)
        base = _path("batting", side)
        if rows is None:
            out.empty(base, f"is empty. List {out.team(side)}'s batters in batting order.")
            continue
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BATTERS:
            count = f"{len(rows)} rows" if isinstance(rows, list) else "no list of rows"
            out.error(base, f"{out.team(side)} has {count}. A batting order is a list of 1 to {MAX_BATTERS} batters, "
                            "one row each: {player: norm-w, ab: 4, r: 1, h: 2, rbi: 0, hr: 0, bb: 0}")
            continue
        shown[side] = _check_side_rows(out, rows, base, side, seen, mode, game)
        info[side] = shown[side]
    _check_sides_agree(out, mode, shown, value)
    return info


def _check_side_rows(out, rows, base, side, seen, mode, game):
    ctx = out.ctx
    team = out.team(side)
    with_line, without_line = [], []
    sums = {k: 0 for k in LINE_KEYS}
    complete = True
    for i, row in enumerate(rows):
        at = _path(base, i)
        if not isinstance(row, dict):
            out.error(at, "a row looks like {player: norm-w, ab: 4, r: 1, h: 2, rbi: 0, hr: 0, bb: 0}")
            complete = False
            continue
        for key in row:
            if key not in ROW_KEYS:
                out.error(_path(at, key), f"'{key}' isn't part of a batting row. Use one of: {', '.join(ROW_KEYS)}.")
        _check_player(out, row, at, side, seen)
        if not _has_line(row):
            without_line.append(i)
            if mode == "every_game":
                out.empty(at, f"has no batting line. This league keeps a line for every batter in every game: "
                              f"write ab, r, h, rbi, hr and bb for {_player_name(ctx, row)}.")
            complete = False
            continue
        with_line.append(i)
        if mode == "order":
            key = next(k for k in LINE_KEYS if k in row)
            out.error(_path(at, key), "this league keeps the batting order only (rules.batting is order), so there "
                                      "are no batting lines. Take it out.")
            complete = False
            continue
        values = _check_line(out, row, at, team)
        if values is None:
            complete = False
        else:
            for k in LINE_KEYS:
                sums[k] += values[k]
    if mode == "optional" and with_line and without_line:
        out.error(_path(base, without_line[0]), f"{team}: some batters have a line and some do not. All of a team's "
                                                "batters have a line, or none.")
    lines = bool(with_line) and mode != "order"
    complete = complete and lines
    _check_side_totals(out, rows, base, side, sums, complete, game)
    return {"lines": lines, "h": sums["h"] if complete else None, "any": lines}


def _player_name(ctx, row):
    if isinstance(row.get("player"), str) and row["player"] in ctx.players:
        return _player_label(ctx, row["player"])
    return row.get("name") or "this batter"


def _check_player(out, row, at, side, seen):
    ctx = out.ctx
    pid = row.get("player")
    pat = _path(at, "player")
    if pid is None:
        who = row.get("name") or "this row"
        out.empty(pat, f"{who} isn't matched to a player id yet. Pick one from players.yml, or add them there first "
                       "(a spare gets sub: true).")
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
                         "players.yml.")


def _check_line(out, row, at, team):
    """One batter's line. Returns {key: value} when all six are usable, else None."""
    values, ok = {}, True
    who = _player_name(out.ctx, row)
    for key in LINE_KEYS:
        kat = _path(at, key)
        v = row.get(key)
        if v is None:
            out.empty(kat, f"is empty. Write {who}'s {key.upper()} (0 if none).")
            ok = False
        elif not _box_ok(v, MAX_LINE):
            out.error(kat, f"{v!r} isn't a count: write a whole number from 0 to {MAX_LINE}.")
            ok = False
        else:
            values[key] = v
    if not ok:
        return None
    if values["h"] > values["ab"]:
        out.error(_path(at, "h"), f"{who} has {values['h']} hits in {values['ab']} at-bats. Hits can't be more than "
                                  "at-bats: check the line.")
        ok = False
    if values["hr"] > values["h"]:
        out.error(_path(at, "hr"), f"{who} has {values['hr']} home runs in {values['h']} hits. Home runs are hits: "
                                   "check the line.")
        ok = False
    return values


def _check_side_totals(out, rows, base, side, sums, complete, game):
    """The checks over one side's whole column of lines: runs, RBI and home runs."""
    ctx = out.ctx
    team = out.team(side)
    if game and complete:
        scored = game["total"][side]
        if sums["r"] != scored:
            out.error(base, f"the batters' R add up to {sums['r']} but {team} scored {scored}: check the R column.")
        if sums["rbi"] > scored:
            out.warning(base, f"the batters' RBI add up to {sums['rbi']} but {team} scored {scored}: "
                              "a run can only be batted in once, check the RBI column.")
    limit = _int_opt(ctx, "hr_limit")
    if complete and limit and sums["hr"] > limit:
        out.warning(base, f"{team} hit {sums['hr']} home runs and the league's limit is {limit} a game: check the "
                          "HR column.")
    if game and complete:
        batted = sum(1 for v in game["lists"][side] if v != X)
        for i, row in enumerate(rows):
            pa = row["ab"] + row["bb"]
            if pa > batted + 2:
                out.warning(_path(base, i, "ab"), f"{_player_name(ctx, row)} has {pa} plate appearances and {team} batted "
                                                  f"{_plural(batted, 'inning')}: check the line.")


def _check_sides_agree(out, mode, shown, value):
    if mode != "optional":
        return
    with_lines = [s for s in SIDES if s in shown and shown[s]["lines"]]
    without = [s for s in SIDES if s in shown and not shown[s]["lines"]]
    if with_lines and without:
        side = without[0]
        out.warning(_path("batting", side), f"only {out.team(with_lines[0])} has batting lines: is a page missing? "
                                            "A game has lines for both teams, or for neither.")


# ---- totals

def _check_totals(out, sheet, game, info):
    ctx = out.ctx
    value = sheet.get("totals")
    if value is None:
        out.empty("totals", "is empty. Write each team's R (runs), and H (hits) and E (errors) when the league keeps "
                            "them.")
        return
    if not isinstance(value, dict):
        out.error("totals", "should list the R H E boxes for home and away, like 'home: {r: 14, h: 18}'")
        return
    for key in value:
        if key not in SIDES:
            out.error(_path("totals", key), f"'{key}' isn't a side. Use 'home' or 'away'.")
    for side in SIDES:
        base = _path("totals", side)
        row = value.get(side)
        team = out.team(side)
        if row is None:
            out.empty(base, f"is empty. Write {team}'s R box, and H and E when the league keeps them.")
            continue
        if not isinstance(row, dict):
            out.error(base, f"should be a row like {{r: 14, h: 18}}, with {team}'s boxes")
            continue
        for key in row:
            if key not in TOTALS_KEYS:
                out.error(_path(base, key), f"'{key}' isn't a box. Use one of: {', '.join(TOTALS_KEYS)}.")
        _check_r(out, row, base, side, game)
        _check_h(out, row, base, side, info[side])
        _check_e(out, row, base, side)


def _check_r(out, row, base, side, game):
    at = _path(base, "r")
    v = row.get("r")
    team = out.team(side)
    if v is None:
        out.empty(at, f"is empty. Write {team}'s R box (the runs they scored).")
    elif not _is_int(v) or v < 0:
        out.error(at, f"{v!r} isn't a number of runs: write a whole number.")
    elif game and v != game["total"][side]:
        out.error(at, f"R says {v}, the innings add up to {game['total'][side]}: check the R box and the innings.")


def _check_h(out, row, base, side, info):
    ctx = out.ctx
    at = _path(base, "h")
    v = row.get("h")
    kept = _opt(ctx, "team_hits") == "kept"
    team = out.team(side)
    if v is None:
        if kept and not info["lines"]:
            out.empty(at, f"is empty. Write {team}'s H box (hits).")
        return
    if not _box_ok(v, MAX_BOX):
        out.error(at, f"{v!r} isn't a number of hits: write a whole number from 0 to {MAX_BOX}.")
    elif not kept and not info["lines"]:
        out.error(at, "this league does not keep team hits (rules.team_hits is none). Take the H box out.")
    elif info["h"] is not None and v != info["h"]:
        out.error(at, f"H says {v}, the batters' hits add up to {info['h']}: check the H box and the H column.")


def _check_e(out, row, base, side):
    ctx = out.ctx
    at = _path(base, "e")
    v = row.get("e")
    kept = _opt(ctx, "team_errors") == "kept"
    if v is None:
        if kept:
            out.empty(at, f"is empty. Write {out.team(side)}'s E box (errors).")
        return
    if not kept:
        out.error(at, "this league does not keep errors (rules.team_errors is none). Take the E box out.")
    elif not _box_ok(v, MAX_BOX):
        out.error(at, f"{v!r} isn't a number of errors: write a whole number from 0 to {MAX_BOX}.")


# ------------------------------------------------------------------ read

def read(sheet, ctx):
    """The numbers of a sheet `check` accepted (warnings allowed). Arithmetic only."""
    innings = _innings(ctx)
    first, last = _sides_order(sheet)
    runs = sheet.get("runs") or {}
    boxes = {s: list(runs.get(s) or []) for s in SIDES}
    n = max(len(boxes["home"]), len(boxes["away"]))
    nums = {s: [_num(v) for v in boxes[s]] for s in SIDES}
    regulation = {s: [None if i >= len(boxes[s]) or boxes[s][i] == X else nums[s][i] for i in range(innings)]
                  for s in SIDES}
    extra = {s: nums[s][innings:] for s in SIDES} if n > innings else {}
    final = {s: sum(nums[s]) for s in SIDES}
    score = Score(final=final, periods=regulation, extra=extra, decided_in="overtime" if n > innings else "regulation",
                  final_at={s: f"sheet.totals.{s}.r" for s in SIDES})
    batting = _read_batting(sheet, ctx)
    lines = [Line(side=side, player=row["player"], group="player",
                  counts=dict(row["line"]) if row["line"] is not None else {})
             for side in SIDES for row in batting[side] if row["player"]]
    limit = _int_opt(ctx, "run_limit")
    limited = [_limited(i, ctx) for i in range(n)]
    x_innings = {s: [i + 1 for i in range(len(boxes[s])) if boxes[s][i] == X] for s in SIDES}
    game = {"first": first, "last": last, "n": n, "nums": nums, "total": final, "lists": boxes}
    walk_off = n > 0 and len(boxes[first]) == len(boxes[last]) == n and _walk_off(game, ctx)
    totals = {s: _read_totals(sheet, s, batting[s]) for s in SIDES}
    facts = {
        "innings": innings,
        "played": n,
        "bats_first": first,
        "bats_last": last,
        "run_limit": limit,
        "limited": limited,
        "runs": {s: [None if v == X else _num(v) for v in boxes[s]] for s in SIDES},
        "x_innings": x_innings,
        "limit_innings": {s: [i + 1 for i, v in enumerate(boxes[s])
                              if limit and limited[i] and _is_int(v) and v >= limit] for s in SIDES},
        "called": sheet.get("called") if sheet.get("called") in CALLED_WORDS else None,
        "walk_off": walk_off,
        "totals": totals,
        "has_lines": {s: any(row["line"] is not None for row in batting[s]) for s in SIDES},
        "batting": batting,
        "hr_players": {s: [{"player": r["player"], "hr": r["line"]["hr"]} for r in batting[s]
                           if r["player"] and r["line"] and r["line"]["hr"] > 0] for s in SIDES},
        "h3_players": {s: [{"player": r["player"], "h": r["line"]["h"]} for r in batting[s]
                           if r["player"] and r["line"] and r["line"]["h"] >= 3] for s in SIDES},
    }
    return Reading(score=score, lines=lines, team_lines={}, facts=facts)


def _read_batting(sheet, ctx):
    out = {s: [] for s in SIDES}
    value = sheet.get("batting")
    if _opt(ctx, "batting") == "none" or not isinstance(value, dict):
        return out
    for side in SIDES:
        for row in value.get(side) or []:
            if not isinstance(row, dict):
                continue
            line = None
            if _has_line(row) and _opt(ctx, "batting") != "order":
                line = {k: _num(row.get(k)) for k in LINE_KEYS}
            pid = row.get("player") if isinstance(row.get("player"), str) else None
            out[side].append({"player": pid, "name": row.get("name") if isinstance(row.get("name"), str) else None,
                              "line": line})
    return out


def _read_totals(sheet, side, rows):
    """R, H, E for one side: the boxes, with H the sum of the batting lines when the box is empty."""
    box = ((sheet.get("totals") or {}).get(side) or {})
    box = box if isinstance(box, dict) else {}
    lined = [r["line"] for r in rows if r["line"] is not None]
    h = box.get("h") if _is_int(box.get("h")) else (sum(ln["h"] for ln in lined) if lined else None)
    return {"r": box.get("r") if _is_int(box.get("r")) else None, "h": h,
            "e": box.get("e") if _is_int(box.get("e")) else None}


# ------------------------------------------------------------------ present

LINE_TITLE = "Line score"
CAPTION = "Runs by inning"
MARK_WORD = "run limit"
VOID_NEEDED = "not needed"
VOID_PLAYED = "not played"
ORDER_NOTE = "# = batting order from the score sheet."
BATTING_COLUMNS = [("ab", "AB", "At bats"), ("r", "R", "Runs"), ("h", "H", "Hits"), ("rbi", "RBI", "Runs batted in"),
                   ("hr", "HR", "Home runs"), ("bb", "BB", "Walks")]
EXTRA_COLUMNS = {"h": ("H", "Hits"), "e": ("E", "Errors")}


def present(reading, ctx):
    return {"line_score": _line_score(reading, ctx, True), "card": _card(reading, ctx), "tiles": None,
            "blocks": _blocks(reading, ctx)}


def _extra_keys(ctx):
    return (["h"] if _opt(ctx, "team_hits") == "kept" else []) + (["e"] if _opt(ctx, "team_errors") == "kept" else [])


def _line_score(reading, ctx, full):
    score, f = reading.score, reading.facts
    line = ctx.sport["line_score"]
    count = max(f["innings"], f["played"])
    limit = f["run_limit"]
    keys = _extra_keys(ctx)
    columns = []
    for i in range(count):
        column = {"label": str(i + 1)}
        if full and limit and not _limited(i, ctx):
            column["open"] = True
        columns.append(column)
    rows, unreached = {}, False
    for side in SIDES:
        boxes, cells = f["runs"][side], []
        for i in range(count):
            if i >= len(boxes):
                unreached = True
                cells.append({"v": None, "void": True})
            elif boxes[i] is None:
                cells.append({"v": None, "void": True})
            else:
                cell = {"v": boxes[i]}
                if limit and i < len(f["limited"]) and f["limited"][i] and boxes[i] >= limit:
                    cell["mark"] = True
                cells.append(cell)
        totals = f["totals"][side]
        rows[side] = {"cells": cells, "total": score.final[side], "extra": None,
                      "extras": [totals[k] if totals[k] is not None else "\u2013" for k in keys],
                      "hammer_first": False}
    out = {"shape": line["shape"], "corner": line["corner"], "total_label": line["total_label"], "extra_label": None,
           "extras": [{"label": EXTRA_COLUMNS[k][0], "title": EXTRA_COLUMNS[k][1]} for k in keys],
           "columns": columns, "rows": rows, "caption": CAPTION, "won_word": None, "mark_word": MARK_WORD,
           "void_word": VOID_PLAYED if unreached else VOID_NEEDED, "title": None, "meta": None, "legend": [],
           "legend_stack": False, "note": None, "note_strong": None}
    if f["bats_first"] == "home":
        out["first"] = "home"
    if full:
        out["title"] = LINE_TITLE
        out["legend"] = _legend(reading, ctx)
        out["legend_stack"] = True
    return out


def _legend(reading, ctx):
    f = reading.facts
    limit, innings = f["run_limit"], f["innings"]
    items = []
    if limit:
        text = f"Circled: the inning ended at the {limit}-run limit."
        if _opt(ctx, "open_innings") == "last" and f["played"] >= innings:
            text += (f" The {_ordinal(innings)} inning and extra innings are open (no limit)." if f["played"] > innings
                     else f" The {_ordinal(innings)} is open (no limit).")
        items.append({"kind": "limit", "mark": str(limit), "text": text})
    x_side = next((s for s in SIDES if f["x_innings"][s]), None)
    if f["called"]:
        after = _after_text(f)
        reason = CALLED_TEXT[f["called"]]
        items.append({"kind": "x", "mark": "X", "text": f"Called after {after} innings: {reason}."})
    elif x_side:
        inning = f["x_innings"][x_side][0]
        items.append({"kind": "x", "mark": "X",
                      "text": f"{_team_name(ctx, x_side)} led after the top of the {_ordinal(inning)}, so they "
                              "didn't bat."})
    return items


def _after_text(f):
    """Innings played, in words: "5", or "4\u00bd" when the team batting last led and did not bat the last one."""
    n = f["played"]
    return f"{n - 1}\u00bd" if f["x_innings"][f["bats_last"]] == [n] else str(n)


def _winner_first(reading):
    """The sides in the order facts list them: the winner, then the other; a tie keeps batting order."""
    f, final = reading.facts, reading.score.final
    order = [f["bats_first"], f["bats_last"]]
    if final["home"] != final["away"]:
        order.sort(key=lambda s: -final[s])
    return order


def _top_bat(reading, ctx):
    """The best hitter of the game: most hits (at least one), then fewest at-bats, then most RBI, then the one
    who bats first (the team batting first, then the order). None without batting lines."""
    f = reading.facts
    best, best_key = None, None
    seen = 0
    for side in (f["bats_first"], f["bats_last"]):
        for row in f["batting"][side]:
            seen += 1
            line = row["line"]
            if not row["player"] or line is None or line["h"] < 1:
                continue
            key = (-line["h"], line["ab"], -line["rbi"], seen)
            if best_key is None or key < best_key:
                best, best_key = (row, line), key
    return best


def _card(reading, ctx):
    card = {"note": None, "strong": None, "link_label": GAME_LINK, "meta_extra": [],
            "line_score": _line_score(reading, ctx, False)}
    top = _top_bat(reading, ctx)
    if top:
        row, line = top
        who = _player_label(ctx, row["player"])
        card["note"], card["strong"] = f"Top bat: {who} {line['h']} for {line['ab']}", who
    return card


def _blocks(reading, ctx):
    f = reading.facts
    blocks = []
    facts = _facts(reading, ctx)
    if facts:
        blocks.append(facts)
    tables = []
    for side in (f["bats_first"], f["bats_last"]):
        if f["has_lines"][side]:
            tables.append(_batting_table(reading, ctx, side))
    blocks.extend(tables)
    lineup = _lineup(reading, ctx, [s for s in (f["bats_first"], f["bats_last"]) if not f["has_lines"][s]])
    if lineup:
        blocks.append(lineup)
    elif tables:
        blocks.append({"type": "note", "text": ORDER_NOTE})
    return blocks


def _facts(reading, ctx):
    f = reading.facts
    sides = _winner_first(reading)
    rows = []

    def people(key, extra):
        items = []
        for side in sides:
            players = [{"player": p["player"], "extra": extra(p)} for p in f[key][side]]
            if players:
                items.append({"side": side, "players": players, "text": None})
        return items

    rows.append({"label": "Home runs", "items": people("hr_players", lambda p: str(p["hr"]) if p["hr"] > 1 else None)})
    rows.append({"label": "3+ hits", "items": people("h3_players", lambda p: None)})
    if f["run_limit"]:
        items = []
        for side in sides:
            innings = f["limit_innings"][side]
            if innings:
                words = ", ".join(_ordinal(i) for i in innings)
                items.append({"side": None, "players": [], "text": f"{_team_name(ctx, side)} {len(innings)} ({words})"})
        rows.append({"label": "Limit innings", "items": items})
    if f["called"]:
        text = f"After {_after_text(f)} innings: {CALLED_TEXT[f['called']]}"
        if f["called"] == "mercy" and _int_opt(ctx, "mercy_runs"):
            text += f", {_int_opt(ctx, 'mercy_runs')} runs"
        elif f["called"] == "time" and _int_opt(ctx, "time_limit"):
            text += f", {_int_opt(ctx, 'time_limit')} minutes"
        rows.append({"label": "Called", "items": [{"side": None, "players": [], "text": text}]})
    rows = [r for r in rows if r["items"]]
    return {"type": "facts", "title": None, "rows": rows} if rows else None


def _batting_table(reading, ctx, side):
    f = reading.facts
    columns = [{"key": k, "label": label, "title": title, "key_col": False} for k, label, title in BATTING_COLUMNS]
    rows, sums = [], {k: 0 for k, _, _ in BATTING_COLUMNS}
    for i, row in enumerate(f["batting"][side]):
        if not row["player"] or row["line"] is None:
            continue
        for k in sums:
            sums[k] += row["line"][k]
        rows.append({"player": row["player"], "num": str(i + 1), "cells": {k: str(row["line"][k]) for k in sums}})
    title = f"{_team_name(ctx, side)} batting"
    return {"type": "stat_table", "title": title, "side": side, "heading": "plain", "caption": title,
            "number_col": True, "number_label": "#", "player_label": "Batter", "columns": columns, "rows": rows,
            "totals": {"label": "Totals", "cells": {k: str(v) for k, v in sums.items()}}, "note": None}


def _lineup(reading, ctx, sides):
    """The batting order as a list for a side with no batting lines (the league keeps the order only, or this game
    has no lines). None when nothing is to show."""
    f = reading.facts
    teams = []
    for side in sides:
        rows = [{"role": str(i + 1), "player": row["player"], "key": False, "spare_for": None}
                for i, row in enumerate(f["batting"][side]) if row["player"]]
        if rows:
            teams.append({"side": side, "rows": rows})
    if not teams:
        return None
    return {"type": "roster", "title": "Batting order", "link_label": "Team", "teams": teams,
            "note": "Batting order from the score sheet."}


# ------------------------------------------------------------------ derive

def derive(counts, group):
    """PA, AVG and OBP from summed counts (one game or a season), unrounded: the core rounds them for display and
    ranks on the exact value. PA = AB + BB; AVG = H / AB and OBP = (H + BB) / (AB + BB), None with nothing at the
    plate."""
    ab, h, bb = counts.get("ab", 0), counts.get("h", 0), counts.get("bb", 0)
    return {"pa": ab + bb,
            "avg": h / ab if ab else None,
            "obp": (h + bb) / (ab + bb) if ab + bb else None}
