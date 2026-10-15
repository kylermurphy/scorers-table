"""Sports: finding the folders in `sports/`, checking `sport.yml` against the fixed schema (spec 3.2), and
loading `rules.py` / `sample.py` from a folder (spec section 3).

A sport is a folder `sports/<id>/` with `sport.yml`, `rules.py`, `sample.py` and `README.md`. The core finds
sports by listing `sports/*/sport.yml`; there is no plugin framework. Every function takes the sports root as
a parameter (tests point it at `tests/fixtures/sports/`).
"""
from __future__ import annotations

import copy
import importlib.util
import inspect
import re
import string
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from scripts.core.model import LAYOUTS, Problem, SportDef
from scripts.core.problems import (
    ID_RE, Checker, InternalError, display_path, join_path, one_of, read_yaml, suggest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SPORTS_ROOT = REPO_ROOT / "sports"

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# The four functions of rules.py and how many positional arguments each takes (spec 3.3).
RULES_FUNCTIONS = {"check": 2, "read": 2, "present": 2, "derive": 2}
SAMPLE_FUNCTION = ("sheet", 3)

OPTION_TYPES = ("int", "bool", "choice", "text")
RESERVED_STATS = ("gp",)       # stats the core counts itself; a sport never lists them
SHAPES = ("quarters", "ends", "periods", "innings")
CARD = ("rows", "lines")
CARD_FOOT = ("note", "meta", "status_note")
SURFACE = ("label", "sub")

# Standings (shared by sport.yml and league.yml).
RANK_BY = ("points", "win_pct")
POINT_KEYS = ("win", "tie", "loss", "ot_win", "ot_loss")
TIEBREAKERS = ("head_to_head", "head_to_head_points", "wins", "win_pct", "diff", "points_for", "points_against",
               "periods_won")
COLUMNS = ("gp", "w", "l", "t", "otw", "otl", "pts", "pct", "pf", "pa", "diff", "gb", "pw")
STANDINGS_KEYS = ("rank_by", "points", "period_points", "ties", "forfeit", "tiebreakers", "columns", "playoffs")


# ------------------------------------------------------------------ "decide" wrappers

def is_wrapped(value: Any) -> bool:
    """True for `{value: ..., decide: true}`, the form a sport uses to mark a standings setting as the
    league's to decide."""
    return isinstance(value, dict) and "value" in value and set(value) <= {"value", "decide"}


def unwrap(value: Any) -> tuple[Any, bool]:
    """(the value, whether the sport marked it `decide: true`). A plain value is returned as it is."""
    if is_wrapped(value):
        return value["value"], bool(value.get("decide"))
    return value, False


# ------------------------------------------------------------------ standings schema (also used by league.yml)

def team_stat_keys(spec: dict) -> list[str]:
    """The keys of the sport's team counting stats (stats.team), which standings columns may use."""
    stats = spec.get("stats") if isinstance(spec, dict) else None
    team = stats.get("team") if isinstance(stats, dict) else None
    return [s["key"] for s in team if isinstance(s, dict) and isinstance(s.get("key"), str)] if isinstance(team, list) else []


def check_standings(c: Checker, value: Any, at: str, extra_columns: list[str], *, allow_decide: bool = False) -> None:
    """Check a standings map (sport.yml `standings:` or league.yml `standings:`) key by key.
    `extra_columns` are the sport's team stats, also allowed as columns. With `allow_decide`, any key may be
    written as `{value: ..., decide: true}`."""
    if c.mapping(value, at, allowed=STANDINGS_KEYS) is None:
        return
    for key, raw in value.items():
        if key not in STANDINGS_KEYS:
            continue
        inner, key_at = raw, join_path(at, key)
        if allow_decide and is_wrapped(raw):
            inner, key_at = raw["value"], join_path(key_at, "value")
            if "decide" in raw:
                c.boolean(raw["decide"], join_path(at, key, "decide"))
        _check_standings_key(c, key, inner, key_at, extra_columns)


def _check_standings_key(c: Checker, key: str, v: Any, at: str, extra_columns: list[str]) -> None:
    if key == "rank_by":
        c.choice(v, at, RANK_BY)
    elif key == "points":
        if c.mapping(v, at, allowed=POINT_KEYS) is not None:
            for k in POINT_KEYS:
                if k in v:
                    c.integer(v[k], join_path(at, k), 0, 99)
    elif key == "period_points":
        c.integer(v, at, 0, 99)
    elif key == "ties":
        c.boolean(v, at)
    elif key == "forfeit":
        _check_forfeit(c, v, at)
    elif key == "tiebreakers":
        _check_tiebreakers(c, v, at)
    elif key == "columns":
        _check_columns(c, v, at, extra_columns)
    elif key == "playoffs":
        c.text(v, at)


def _check_forfeit(c: Checker, v: Any, at: str) -> None:
    if c.mapping(v, at, required=("score",)) is None or "score" not in v:
        return
    score, score_at = v["score"], join_path(at, "score")
    if score == "per_period":
        return
    if isinstance(score, list):
        if len(score) != 2:
            c.error(score_at, "must be two numbers, the winner's score then the loser's, like [7, 0].")
        else:
            for i, n in enumerate(score):
                c.integer(n, join_path(score_at, i), 0, 999)
            first, second = score
            if all(isinstance(n, int) and not isinstance(n, bool) for n in score) and first <= second:
                c.error(score_at, "the winner's score (first) must be higher than the loser's (second), like [7, 0].")
    else:
        c.error(score_at, "must be [winner, loser] like [7, 0], or per_period (1-0 in every regulation period).")


def _check_tiebreakers(c: Checker, v: Any, at: str) -> None:
    items = c.sequence(v, at)
    for i, item in enumerate(items or []):
        item_at = join_path(at, i)
        if isinstance(item, dict):
            if len(item) != 1:
                c.error(item_at, "a tiebreaker with options is one name, like {diff: {cap: 7}}.")
                continue
            (name, options), = item.items()
            if c.choice(name, join_path(item_at, name), TIEBREAKERS) is None:
                continue
            if name == "diff":
                if c.mapping(options, join_path(item_at, name), allowed=("cap",)) is not None and "cap" in options:
                    c.integer(options["cap"], join_path(item_at, name, "cap"), 1, 999)
            else:
                c.error(join_path(item_at, name), f"{name!r} takes no options; write just '{name}'.")
        else:
            c.choice(item, item_at, TIEBREAKERS)


def _check_columns(c: Checker, v: Any, at: str, extra_columns: list[str]) -> None:
    items = c.sequence(v, at)
    if items is None:
        return
    allowed = [*COLUMNS, *extra_columns]
    if not items:
        c.error(at, "must list at least one column.")
    for i, item in enumerate(items):
        c.choice(item, join_path(at, i), allowed)
        if item in items[:i]:
            c.error(join_path(at, i), f"{item!r} is listed twice.")


# ------------------------------------------------------------------ options and minimums (also used by league.yml)

def check_option_value(c: Checker, value: Any, at: str, option: dict) -> Any:
    """Check one rules value against its option definition from sport.yml (type, range, allowed values)."""
    kind = option.get("type")
    if kind == "int":
        lo, hi = (b if isinstance(b, int) and not isinstance(b, bool) else None for b in (option.get("min"), option.get("max")))
        return c.integer(value, at, lo, hi)
    if kind == "bool":
        return c.boolean(value, at)
    if kind == "choice":
        return c.choice(value, at, option.get("values", []))
    return c.text(value, at, allow_empty=True)


# ------------------------------------------------------------------ the sport.yml schema

def check_sport_spec(spec: Any, file: str) -> list[Problem]:
    """Check a parsed sport.yml against the fixed schema of spec 3.2. Returns every problem (unknown keys
    included, each with its path), so a stage 5 typo fails the contract test rather than a page."""
    c = Checker(file)
    top = ("name", "default_layout", "games_per_day", "game_minutes", "words", "line_score", "options", "standings",
           "stats", "minimums", "leaderboards", "labels", "labels_by_layout", "display", "positions")
    required = ("name", "default_layout", "words", "line_score", "standings", "stats")
    if spec is None or c.mapping(spec, "", allowed=top, required=required) is None:
        if spec is None:
            c.error("", "This file is empty. It needs at least: " + ", ".join(required) + ".")
        return c.problems
    if "name" in spec:
        c.text(spec["name"], "name")
    if "default_layout" in spec:
        c.choice(spec["default_layout"], "default_layout", LAYOUTS)
    if "games_per_day" in spec:
        c.integer(spec["games_per_day"], "games_per_day", 1, 9)
    if "game_minutes" in spec:
        c.integer(spec["game_minutes"], "game_minutes", 1, 1440)
    if "words" in spec:
        _check_words(c, spec["words"])
    if "line_score" in spec:
        _check_line_score(c, spec["line_score"], spec.get("options"))
    if "options" in spec:
        _check_options(c, spec["options"])
    team_cols = team_stat_keys(spec)
    if "standings" in spec:
        check_standings(c, spec["standings"], "standings", team_cols, allow_decide=True)
    stat_keys = _check_stats(c, spec["stats"], "stats") if "stats" in spec else {}
    if "minimums" in spec:
        _check_minimums(c, spec["minimums"])
    if "leaderboards" in spec:
        _check_leaderboards(c, spec["leaderboards"], stat_keys, spec.get("minimums"))
    _check_labels(c, spec)
    if "display" in spec:
        _check_display(c, spec["display"])
    if "positions" in spec:
        for i, p in enumerate(c.sequence(spec["positions"], "positions") or []):
            c.pattern(p, join_path("positions", i), KEY_RE, "a lower-case word")
    return c.problems


def _check_words(c: Checker, words: Any) -> None:
    if c.mapping(words, "words", allowed=("surface",),
                 required=("period", "day", "points_for", "points_against")) is None:
        return
    if "period" in words and c.mapping(words["period"], "words.period", required=("one", "many", "short")) is not None:
        for k in ("one", "many", "short"):
            if k in words["period"]:
                c.text(words["period"][k], f"words.period.{k}")
    if "day" in words:
        c.text(words["day"], "words.day")
    if "surface" in words:
        c.text(words["surface"], "words.surface", allow_empty=True)
    for k in ("points_for", "points_against"):
        if k in words and c.mapping(words[k], f"words.{k}", required=("label", "title")) is not None:
            for sub in ("label", "title"):
                if sub in words[k]:
                    c.text(words[k][sub], f"words.{k}.{sub}")


def _check_line_score(c: Checker, line: Any, options: Any = None) -> None:
    if c.mapping(line, "line_score", required=("shape", "total_label", "corner"), allowed=("periods",)) is None:
        return
    if "shape" in line:
        c.choice(line["shape"], "line_score.shape", SHAPES)
    for k in ("total_label", "corner"):
        if k in line:
            c.text(line[k], f"line_score.{k}")
    if "periods" in line:
        value = line["periods"]
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            c.error("line_score.periods", "must be a number of regulation periods (like 4) or the name of an int option "
                                          "(like 'periods').")
        elif isinstance(value, int) and value < 1:
            c.error("line_score.periods", "must be at least 1.")
        elif isinstance(value, str):
            opt = (options or {}).get(value) if isinstance(options, dict) else None
            if not isinstance(opt, dict) or opt.get("type") != "int":
                c.error("line_score.periods", f"{value!r} is not an int option in this sport.yml. Name an option "
                                              "with `type: int`, or write a number.")


def regulation_periods(spec: dict, options: dict) -> int | None:
    """How many regulation periods (quarters, halves, ends, innings) a game has.

    `spec` is a checked `sport.yml` (`SportDef.spec`), `options` the league's effective rules. Reads
    `line_score.periods`: a number, or the name of an int option (its effective value, else its default).
    None when the sport does not say (the core then cannot score a `per_period` forfeit)."""
    value = spec.get("line_score", {}).get("periods")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        chosen = options.get(value)
        if isinstance(chosen, int) and not isinstance(chosen, bool):
            return chosen
        default = spec.get("options", {}).get(value, {}).get("default")
        return default if isinstance(default, int) and not isinstance(default, bool) else None
    return None


def _check_options(c: Checker, options: Any) -> None:
    if c.mapping(options, "options", any_keys=True) is None:
        return
    for key, opt in options.items():
        at = join_path("options", key)
        c.pattern(key, at, KEY_RE, "a lower-case name like 'run_limit'")
        if c.mapping(opt, at, allowed=("min", "max", "values", "decide", "label"), required=("type", "default")) is None:
            continue
        if c.choice(opt.get("type"), join_path(at, "type"), OPTION_TYPES) is None:
            continue
        kind = opt["type"]
        if "decide" in opt:
            c.boolean(opt["decide"], join_path(at, "decide"))
        if "label" in opt:
            c.text(opt["label"], join_path(at, "label"))
        for bound in ("min", "max"):
            if bound in opt:
                if kind != "int":
                    c.error(join_path(at, bound), f"only an 'int' option has a {bound}.")
                else:
                    c.integer(opt[bound], join_path(at, bound))
        if "values" in opt and kind != "choice":
            c.error(join_path(at, "values"), "only a 'choice' option has values.")
        if kind == "choice":
            values = c.sequence(opt.get("values"), join_path(at, "values"))
            if values is not None and not values:
                c.error(join_path(at, "values"), "must list at least one value.")
            if values:
                check_option_value(c, opt["default"], join_path(at, "default"), opt)
        else:
            check_option_value(c, opt["default"], join_path(at, "default"), opt)


def _check_stat_list(c: Checker, items: Any, at: str, *, derived: bool = False) -> list[str]:
    """Check a list of stat definitions; returns the keys that were fine."""
    keys: list[str] = []
    for i, stat in enumerate(c.sequence(items, at) or []):
        s_at = join_path(at, i)
        if c.mapping(stat, s_at, allowed=("places",) if derived else (), required=("key", "label", "title")) is None:
            continue
        for k in ("label", "title"):
            if k in stat:
                c.text(stat[k], join_path(s_at, k))
        if "places" in stat:
            c.integer(stat["places"], join_path(s_at, "places"), 0, 4)
        if "key" in stat and c.pattern(stat["key"], join_path(s_at, "key"), KEY_RE, "a lower-case name like 'pts'"):
            if stat["key"] in RESERVED_STATS:
                c.error(join_path(s_at, "key"), f"{stat['key']!r} is worked out by the core (games played); "
                                                "leave it out of sport.yml.")
            elif stat["key"] in keys:
                c.error(join_path(s_at, "key"), f"{stat['key']!r} is listed twice.")
            keys.append(stat["key"])
    return keys


def _check_stats(c: Checker, stats: Any, at: str) -> dict[str, list[str]]:
    """Check `stats:`; returns {group name: [stat keys]} with the special groups 'derived' and 'team' included."""
    found: dict[str, list[str]] = {}
    if c.mapping(stats, at, any_keys=True) is None:
        return found
    groups = [k for k in stats if k not in ("derived", "team")]
    if not groups:
        c.error(at, "needs at least one group of counting stats, like 'player:' with a list of {key, label, title}.")
    for key, items in stats.items():
        key_at = join_path(at, key)
        if key in groups:
            c.pattern(key, key_at, KEY_RE, "a lower-case group name like 'player'")
        found[key] = _check_stat_list(c, items, key_at, derived=(key == "derived"))
    return found


def _check_minimums(c: Checker, minimums: Any) -> None:
    if c.mapping(minimums, "minimums", any_keys=True) is None:
        return
    for key, m in minimums.items():
        at = join_path("minimums", key)
        c.pattern(key, at, KEY_RE, "a lower-case name like 'ppg_min_games'")
        if c.mapping(m, at, allowed=("decide", "note", "label"), required=("default",)) is None:
            continue
        if "default" in m:
            c.integer(m["default"], join_path(at, "default"), 0, 999)
        if "decide" in m:
            c.boolean(m["decide"], join_path(at, "decide"))
        for k in ("note", "label"):
            if k in m:
                c.text(m[k], join_path(at, k))
        if isinstance(m.get("note"), str):
            check_template(c, m["note"], join_path(at, "note"), ["value"])


def _check_leaderboards(c: Checker, boards: Any, stat_keys: dict[str, list[str]], minimums: Any) -> None:
    seen: list[str] = []
    known_minimums = list(minimums) if isinstance(minimums, dict) else []
    for i, board in enumerate(c.sequence(boards, "leaderboards") or []):
        at = join_path("leaderboards", i)
        if c.mapping(board, at, allowed=("group", "tile", "edge", "detail", "min"),
                     required=("id", "of", "stat", "label")) is None:
            continue
        if "id" in board and c.pattern(board["id"], join_path(at, "id"), KEY_RE, "a lower-case name like 'pts'"):
            if board["id"] in seen:
                c.error(join_path(at, "id"), f"{board['id']!r} is used twice.")
            seen.append(board["id"])
        of = c.choice(board.get("of"), join_path(at, "of"), ("player", "team")) if "of" in board else None
        for k in ("label", "edge", "detail"):
            if k in board:
                c.text(board[k], join_path(at, k))
        if "tile" in board:
            c.boolean(board["tile"], join_path(at, "tile"))
        if of is None:
            continue
        group = board.get("group", "player")
        if of == "team":
            available = stat_keys.get("team", [])
        elif group in stat_keys and group not in ("derived", "team"):
            available = stat_keys[group] + stat_keys.get("derived", [])
        else:
            groups = [g for g in stat_keys if g not in ("derived", "team")]
            c.error(join_path(at, "group"), f"{group!r} is not a stats group. Use one of: {one_of(groups)}.")
            continue
        if "stat" in board and of and board["stat"] not in available:
            c.error(join_path(at, "stat"), f"{board['stat']!r} is not a stat of this board. Use one of: {one_of(available)}.")
        # The row's display values a `detail` may name: the board's stats and gp (team boards: the standings too).
        fields = [*RESERVED_STATS, *available, *(COLUMNS if of == "team" else ())]
        if isinstance(board.get("detail"), str):
            check_template(c, board["detail"], join_path(at, "detail"), fields)
        if "min" in board:
            _check_board_min(c, board["min"], join_path(at, "min"), known_minimums, fields)


def check_template(c: Checker, text: str, at: str, fields: list[str]) -> None:
    """A `detail` or `note` template (Python str.format over named values): every {name} must be one the core
    supplies, so a typo fails here and not while a page is being built."""
    try:
        names = [f for _, f, _, _ in string.Formatter().parse(text) if f is not None]
    except ValueError as exc:
        c.error(at, f"{text!r} is not a valid template ({exc}). Write a value as {{name}}, a brace as {{{{ or }}}}.")
        return
    for name in names:
        base = re.split(r"[.\[]", name, maxsplit=1)[0]
        if base not in fields:
            c.error(at, f"{{{name}}} is not a value this template can use. Use one of: "
                        + ", ".join("{" + f + "}" for f in dict.fromkeys(fields)) + ".")


def _check_board_min(c: Checker, m: Any, at: str, known_minimums: list[str], fields: list[str]) -> None:
    if c.mapping(m, at, allowed=("cap_at_team_games",), required=("stat", "setting")) is None:
        return
    if "stat" in m:
        c.choice(m["stat"], join_path(at, "stat"), list(dict.fromkeys(fields)))
    if "cap_at_team_games" in m:
        c.boolean(m["cap_at_team_games"], join_path(at, "cap_at_team_games"))
    if "setting" in m and m["setting"] not in known_minimums:
        c.error(join_path(at, "setting"), f"{m['setting']!r} is not in 'minimums:'. Use one of: {', '.join(known_minimums) or '(none listed)'}.")


def _check_labels(c: Checker, spec: dict) -> None:
    if "labels" in spec and c.mapping(spec["labels"], "labels", any_keys=True) is not None:
        for k, v in spec["labels"].items():
            c.text(v, join_path("labels", k))
    by_layout = spec.get("labels_by_layout")
    if "labels_by_layout" in spec and c.mapping(by_layout, "labels_by_layout", allowed=LAYOUTS) is not None:
        for layout, labels in by_layout.items():
            if c.mapping(labels, join_path("labels_by_layout", layout), any_keys=True) is not None:
                for k, v in labels.items():
                    c.text(v, join_path("labels_by_layout", layout, k))


def _check_display(c: Checker, display: Any) -> None:
    if c.mapping(display, "display", allowed=("card", "card_foot", "surface")) is None:
        return
    for key, options in (("card", CARD), ("card_foot", CARD_FOOT), ("surface", SURFACE)):
        if key in display:
            c.choice(display[key], join_path("display", key), options)


def normalise_spec(spec: dict) -> dict:
    """A copy of a (valid) sport.yml with the optional top-level keys filled in, so readers can rely on them."""
    out = copy.deepcopy(spec)
    for key, default in (("games_per_day", 1), ("game_minutes", 60), ("options", {}), ("minimums", {}),
                         ("leaderboards", []), ("labels", {}), ("labels_by_layout", {}), ("positions", [])):
        out.setdefault(key, default)
    out["display"] = {"card": "rows", "card_foot": "note", "surface": "label", **(out.get("display") or {})}
    out["words"].setdefault("surface", "")
    out["stats"].setdefault("derived", [])
    out["stats"].setdefault("team", [])
    return out


# ------------------------------------------------------------------ discovery and loading

def discover_sports(sports_root: Path = SPORTS_ROOT) -> list[str]:
    """The ids of the sport folders: every `<sports_root>/<id>/` that has a `sport.yml`, sorted."""
    if not sports_root.is_dir():
        return []
    return sorted(p.name for p in sports_root.iterdir() if (p / "sport.yml").is_file())


def unknown_sport_message(sport_id: object, sports_root: Path = SPORTS_ROOT, root: Path = REPO_ROOT) -> str:
    """'curlng' is not a sport folder... Available: curling, stub (with a 'did you mean' when close)."""
    available = discover_sports(sports_root)
    where = display_path(sports_root, root)
    hint = suggest(str(sport_id), available)
    return (f"{str(sport_id)!r} is not a sport folder in {where}/." + (f" Did you mean {hint!r}?" if hint else "")
            + f" Available: {one_of(available) or '(none found)'}.")


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Import one .py file by path. It is registered in sys.modules under `module_name` (dataclasses inside
    it need that) and removed again if it fails to import."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _check_function(c: Checker, module: ModuleType, name: str, arity: int, args_doc: str) -> None:
    func: Callable[..., Any] | None = getattr(module, name, None)
    if not callable(func):
        c.error("", f"is missing the function {name}({args_doc}).")
        return
    try:
        inspect.signature(func).bind(*range(arity))
    except TypeError:
        c.error("", f"{name}() must take exactly {arity} arguments: {name}({args_doc}).")
    except ValueError:
        pass


def check_rules_module(module: ModuleType, file: str) -> list[Problem]:
    """rules.py must define check(sheet, ctx), read(sheet, ctx), present(reading, ctx), derive(counts, group)."""
    c = Checker(file)
    docs = {"check": "sheet, ctx", "read": "sheet, ctx", "present": "reading, ctx", "derive": "counts, group"}
    for name, arity in RULES_FUNCTIONS.items():
        _check_function(c, module, name, arity, docs[name])
    return c.problems


def check_sample_module(module: ModuleType, file: str) -> list[Problem]:
    """sample.py must define LEAGUE_NAME, TEAMS (a list of (id, name, code)) and sheet(rng, game, ctx)."""
    c = Checker(file)
    if not isinstance(getattr(module, "LEAGUE_NAME", None), str):
        c.error("", "is missing LEAGUE_NAME, the made-up league's name (a text).")
    teams = getattr(module, "TEAMS", None)
    if not (isinstance(teams, (list, tuple)) and teams
            and all(isinstance(t, (list, tuple)) and len(t) == 3 and all(isinstance(x, str) for x in t) for t in teams)):
        c.error("", "is missing TEAMS, a list of (id, name, code) such as [(\"otters\", \"Otters\", \"OTT\")].")
    _check_function(c, module, SAMPLE_FUNCTION[0], SAMPLE_FUNCTION[1], "rng, game, ctx")
    return c.problems


def load_sport(sport_id: str, sports_root: Path = SPORTS_ROOT, *, root: Path = REPO_ROOT,
               with_sample: bool = False) -> tuple[SportDef | None, list[Problem]]:
    """Load one sport folder: parse and check `sport.yml`, import `rules.py` (and `sample.py` when
    `with_sample`), check the functions exist with the right arity. Returns (SportDef, problems); the
    SportDef is None when any problem is an error. A missing README.md is only a warning.
    An exception raised while importing a sport file is a bug, not a data problem: it becomes an InternalError
    (exit 2) naming the file, with the original traceback on `__cause__`."""
    folder = sports_root / sport_id
    shown = display_path(folder, root)
    if not (folder / "sport.yml").is_file():
        return None, [Problem("error", "", unknown_sport_message(sport_id, sports_root, root), shown)]
    spec_file = f"{shown}/sport.yml"
    spec, problems = read_yaml(folder / "sport.yml", spec_file)
    if not problems:
        problems = check_sport_spec(spec, spec_file)
    modules: dict[str, ModuleType] = {}
    wanted = [("rules", check_rules_module)] + ([("sample", check_sample_module)] if with_sample else [])
    for stem, checker in wanted:
        py_file = f"{shown}/{stem}.py"
        if not (folder / f"{stem}.py").is_file():
            problems.append(Problem("error", "", f"is missing. Every sport folder needs {stem}.py.", py_file))
            continue
        try:
            module = _load_module(folder / f"{stem}.py", f"scorers_sport_{re.sub(r'[^a-z0-9]', '_', sport_id)}_{stem}")
        except Exception as exc:       # a bug in the sport's file (SyntaxError, a bad import...): exit 2
            raise InternalError(f"importing the sport file {py_file} raised {type(exc).__name__}: {exc}") from exc
        modules[stem] = module
        problems.extend(checker(module, py_file))
    if not (folder / "README.md").is_file():
        problems.append(Problem("warning", "", "is missing. Every sport folder needs a README.md (the format, box by box).",
                                f"{shown}/README.md"))
    if any(p.level == "error" for p in problems) or "rules" not in modules:
        return None, problems
    return SportDef(sport_id, folder, normalise_spec(spec), modules["rules"], modules.get("sample")), problems


def load_all_sports(sports_root: Path = SPORTS_ROOT, *, root: Path = REPO_ROOT) -> tuple[list[SportDef], list[Problem]]:
    """Load every sport folder, sample.py included (the contract test uses this)."""
    sports, problems = [], []
    for sport_id in discover_sports(sports_root):
        sport, found = load_sport(sport_id, sports_root, root=root, with_sample=True)
        problems.extend(found)
        if sport:
            sports.append(sport)
    return sports, problems
