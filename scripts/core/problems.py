"""Problems: collecting them, giving them a file and a path, sorting, printing, exit codes (spec 4.4).

Every problem prints as `<file>: <at>: <message>`. Paths are dotted into the file and list rows count from 0.
The `Checker` class is the small toolkit that league.yml, sport.yml and the loader share for "is this value
the right kind of thing", so every check words its message and names its path the same way.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence, TextIO

import yaml

from scripts.core.model import (
    BLOCK_TYPES, DECIDED_IN, PRESENT_KEYS, SIDES, STAT_RESERVED, Line, Placeholder, Problem, Reading, Score, SportContext,
)

# Ids of teams, players, seasons, sports: lower-case words joined by single hyphens (spec section 2).
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

EXIT_OK = 0          # built (warnings and placeholders listed)
EXIT_DATA = 1        # data problems: all listed, nothing written
EXIT_INTERNAL = 2    # usage or internal error, including a sport function that raised


# ------------------------------------------------------------------ paths and problem lists

def join_path(*parts: object) -> str:
    """Join path pieces with dots, skipping empty ones: join_path("sheet", "", 3, "pts") -> "sheet.3.pts"."""
    return ".".join(str(p) for p in parts if p != "" and p is not None)


def with_file(problems: Iterable[Problem], file: str) -> list[Problem]:
    """The same problems with `file` set on every one that has no file yet."""
    return [p if p.file else replace(p, file=file) for p in problems]


def with_prefix(problems: Iterable[Problem], prefix: str) -> list[Problem]:
    """The same problems with `prefix` put in front of each path ("" stays the prefix alone).
    A sport reports paths relative to `sheet`; the core adds `sheet.` with this."""
    return [replace(p, at=join_path(prefix, p.at)) for p in problems]


def has_errors(problems: Iterable[Problem]) -> bool:
    return any(p.level == "error" for p in problems)


def _natural(at: str) -> tuple:
    """Sort key for a path, so 'players.2' comes before 'players.10'."""
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in at.split("."))


# Inside one folder, the files a later file depends on come first: a broken teams.yml explains the problems in
# players.yml and schedule.csv, and those explain the game files (which sit one folder deeper, so after them).
_FILE_ORDER = {"league.yml": 0, "seasons.yml": 1, "teams.yml": 2, "players.yml": 3, "schedule.csv": 4}


def _file_key(file: str) -> tuple:
    folder, _, name = file.rpartition("/")
    return (folder, _FILE_ORDER.get(name, len(_FILE_ORDER)), name)


def sort_problems(problems: Iterable[Problem]) -> list[Problem]:
    """Errors first, then warnings; inside each, grouped by file, then by path (numbers in order). Files are in
    the order a person should fix them: by folder (league.yml, then data/seasons.yml, then each season's
    teams.yml, players.yml, schedule.csv, then its game files), so the cause of a problem is listed before
    the problems it causes."""
    return sorted(problems, key=lambda p: (p.level != "error", _file_key(p.file), _natural(p.at), p.message))


# ------------------------------------------------------------------ printing

def format_problem(problem: Problem) -> str:
    """`games/x.yml: sheet.home.running.14: message`; the file or the path is left out when empty."""
    return ": ".join(part for part in (problem.file, problem.at, problem.message) if part)


def format_human(problems: Iterable[Problem], placeholders: Sequence[Placeholder] = ()) -> str:
    """The report a person reads: errors, then warnings, then "Still to decide". Empty parts are left out."""
    ordered = sort_problems(problems)
    errors = [p for p in ordered if p.level == "error"]
    warnings = [p for p in ordered if p.level != "error"]
    blocks: list[str] = []
    if errors:
        blocks.append("\n".join(format_problem(p) for p in errors))
    if warnings:
        blocks.append("Warnings:\n" + "\n".join("  " + format_problem(p) for p in warnings))
    if placeholders:
        lines = ["Still to decide (the site shows [placeholder] until you set these in league.yml):"]
        lines += [f"  - {ph.text} ({ph.setting})" for ph in placeholders]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def problem_dict(problem: Problem) -> dict[str, str]:
    return {"level": problem.level, "file": problem.file, "at": problem.at, "message": problem.message}


def format_json(problems: Iterable[Problem]) -> str:
    """`--json`: one JSON object per line ({level, file, at, message}), in report order."""
    return "\n".join(json.dumps(problem_dict(p), ensure_ascii=False) for p in sort_problems(problems))


def _annotation_escape(text: str, *, prop: bool = False) -> str:
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def github_annotation(problem: Problem) -> str:
    """A GitHub Actions workflow command: `::error file=<file>,title=<path>::<message>`.
    The pull request then shows the message on the changed file."""
    command = "error" if problem.level == "error" else "warning"
    props = []
    if problem.file:
        props.append("file=" + _annotation_escape(problem.file, prop=True))
    props.append("title=" + _annotation_escape(problem.at or "Data problem", prop=True))
    return f"::{command} {','.join(props)}::{_annotation_escape(problem.message)}"


def exit_code(problems: Iterable[Problem]) -> int:
    """0 when nothing is an error (warnings are fine), 1 otherwise."""
    return EXIT_DATA if has_errors(problems) else EXIT_OK


def report(
    problems: Iterable[Problem],
    placeholders: Sequence[Placeholder] = (),
    *,
    json_lines: bool = False,
    annotations: bool = False,
    out: TextIO | None = None,
    data_out: TextIO | None = None,
) -> int:
    """Print every problem and return the exit code (0 or 1). The human report goes to `out` (default
    stderr); with `json_lines` the JSON lines go to `data_out` instead (default stdout, so they can be piped),
    and with `annotations` the GitHub workflow commands go to `data_out` too (stdout is the channel GitHub
    documents for them)."""
    problems = list(problems)
    out = out or sys.stderr
    data_out = data_out or sys.stdout
    if json_lines:
        if problems:
            print(format_json(problems), file=data_out)
    else:
        text = format_human(problems, placeholders)
        if text:
            print(text, file=out)
    if annotations:
        for p in sort_problems(problems):
            print(github_annotation(p), file=data_out)
    return exit_code(problems)


# ------------------------------------------------------------------ internal errors (exit 2)

class InternalError(Exception):
    """Something the data cannot fix: a bug, or a sport function that raised. Exit code 2."""


def call_sport(name: str, func: Callable[..., Any], *args: Any) -> Any:
    """Call a sport function (check, read, present, derive) and check the shape of what it returns, so a
    sport bug stops the build with exit 2 here instead of crashing the core later. If the function raises,
    or returns the wrong shape, the InternalError names the function and its file (the traceback rides on
    `__cause__`). Any other `name` is called without a shape check."""
    where = getattr(getattr(func, "__code__", None), "co_filename", "a sport file")
    try:
        result = func(*args)
    except Exception as exc:
        raise InternalError(f"the sport function {name}() in {where} raised {type(exc).__name__}: {exc}") from exc
    validator = _RESULT_CHECKS.get(name)
    wrong = validator(result, args) if validator else None
    if wrong:
        raise InternalError(f"the sport function {name}() in {where} returned the wrong shape: {wrong}")
    return result


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _ctx_of(args: tuple) -> SportContext | None:
    return args[1] if len(args) > 1 and isinstance(args[1], SportContext) else None


def _check_result_check(value: Any, args: tuple) -> str | None:
    if not isinstance(value, list):
        return f"check() must return a list of Problem, not {type(value).__name__}"
    for i, p in enumerate(value):
        if not isinstance(p, Problem):
            return f"item {i} of check()'s list is a {type(p).__name__}, not a Problem"
    return None


def _check_side_map(value: Any, what: str, item_ok: Callable[[Any], bool], item_words: str,
                    *, both: bool = True) -> str | None:
    if not isinstance(value, dict) or not set(value) <= set(SIDES) or (both and set(value) != set(SIDES)):
        need = "both 'home' and 'away'" if both else "only 'home' and/or 'away'"
        return f"{what} must be a dict with {need} as keys, not {value!r}"
    for side, v in value.items():
        if not item_ok(v):
            return f"{what}[{side!r}] must be {item_words}, not {v!r}"
    return None


def _check_score(s: Any) -> str | None:
    if not isinstance(s, Score):
        return f"Reading.score must be a Score, not {type(s).__name__}"
    int_list = lambda allow_none: lambda v: isinstance(v, list) and all(_is_int(x) or (allow_none and x is None) for x in v)
    found = (_check_side_map(s.final, "Score.final", lambda v: _is_int(v) and v >= 0, "a whole number of 0 or more")
             or _check_side_map(s.periods, "Score.periods", int_list(True), "a list of whole numbers or None")
             or _check_side_map(s.extra, "Score.extra", int_list(False), "a list of whole numbers", both=False)
             or _check_side_map(s.final_at, "Score.final_at", lambda v: isinstance(v, str) and v.startswith("sheet."),
                                "the path of the box holding that final score, from the top of the file "
                                "('sheet.final.home'; unlike check(), whose paths start inside the sheet)"))
    if found:
        return found
    if len(s.periods["home"]) != len(s.periods["away"]):
        return "Score.periods must have the same number of periods for home and away"
    if len(s.extra) == 2 and len(s.extra["home"]) != len(s.extra["away"]):
        return "Score.extra must have the same length for home and away"
    if s.decided_in not in DECIDED_IN:
        return f"Score.decided_in must be one of {', '.join(DECIDED_IN)}, not {s.decided_in!r}"
    return None


def _counts_ok(counts: Any) -> bool:
    return isinstance(counts, dict) and all(isinstance(k, str) and _is_int(v) for k, v in counts.items())


def _stat_keys(spec: Any, group: str) -> set[str] | None:
    """The stat keys sport.yml lists for `group`, or None when the spec is not at hand."""
    stats = spec.get("stats") if isinstance(spec, dict) else None
    if not isinstance(stats, dict):
        return None
    items = stats.get(group)
    return {s["key"] for s in items if isinstance(s, dict) and "key" in s} if isinstance(items, list) else set()


def _check_result_read(value: Any, args: tuple) -> str | None:
    if not isinstance(value, Reading):
        return f"read() must return a Reading, not {type(value).__name__}"
    found = _check_score(value.score)
    if found:
        return found
    ctx = _ctx_of(args)
    spec = ctx.sport if ctx else None
    groups = {g for g in (spec or {}).get("stats", {}) if g not in STAT_RESERVED} if spec else None
    if not isinstance(value.lines, list):
        return f"Reading.lines must be a list of Line, not {type(value.lines).__name__}"
    for i, line in enumerate(value.lines):
        if not isinstance(line, Line):
            return f"Reading.lines[{i}] is a {type(line).__name__}, not a Line"
        if line.side not in SIDES or not isinstance(line.player, str) or not _counts_ok(line.counts):
            return f"Reading.lines[{i}] needs side 'home' or 'away', a player id and counts of whole numbers: {line!r}"
        if groups is not None and line.group not in groups:
            return f"Reading.lines[{i}].group {line.group!r} is not a stats group in sport.yml ({', '.join(sorted(groups))})"
        known = _stat_keys(spec, line.group)
        if known is not None and not set(line.counts) <= known:
            return f"Reading.lines[{i}].counts has keys sport.yml does not list under stats.{line.group}: " \
                   f"{', '.join(sorted(set(line.counts) - known))}"
    found = _check_side_map(value.team_lines, "Reading.team_lines", _counts_ok, "a dict of whole numbers", both=False)
    if found:
        return found
    known = _stat_keys(spec, "team")
    for side, counts in value.team_lines.items():
        if known is not None and not set(counts) <= known:
            return f"Reading.team_lines[{side!r}] has keys sport.yml does not list under stats.team: " \
                   f"{', '.join(sorted(set(counts) - known))}"
    if not isinstance(value.facts, dict):
        return f"Reading.facts must be a dict, not {type(value.facts).__name__}"
    return None


def _check_result_present(value: Any, args: tuple) -> str | None:
    if not isinstance(value, dict):
        return f"present() must return a dict, not {type(value).__name__}"
    unknown = [k for k in value if k not in PRESENT_KEYS]
    if unknown:
        return f"present() returned unknown keys {unknown}; use only {', '.join(PRESENT_KEYS)}"
    blocks = value.get("blocks", [])
    if not isinstance(blocks, list):
        return "present()['blocks'] must be a list"
    for i, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
            return f"present()['blocks'][{i}] must be a dict whose 'type' is one of {', '.join(BLOCK_TYPES)}"
    card = value.get("card")
    extra = card.get("meta_extra", []) if isinstance(card, dict) else []
    if not isinstance(extra, list) or not all(isinstance(x, str) for x in extra):
        return "present()['card']['meta_extra'] must be a list of strings (each one a part of the card's foot)"
    return None


def _check_result_derive(value: Any, args: tuple) -> str | None:
    if not isinstance(value, dict):
        return f"derive() must return a dict, not {type(value).__name__}"
    for k, v in value.items():
        if not isinstance(k, str) or not (v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))):
            return f"derive() must map stat keys to numbers or None, not {k!r}: {v!r}"
    return None


_RESULT_CHECKS: dict[str, Callable[[Any, tuple], str | None]] = {
    "check": _check_result_check, "read": _check_result_read, "present": _check_result_present,
    "derive": _check_result_derive,
}


def report_internal_error(exc: BaseException, out: TextIO | None = None) -> int:
    """Print an internal error with its traceback and return exit code 2."""
    out = out or sys.stderr
    print(f"Internal error: {exc}", file=out)
    print("".join(traceback.format_exception(exc)), file=out, end="")
    return EXIT_INTERNAL


# ------------------------------------------------------------------ reading YAML

def display_path(path: Path, root: Path) -> str:
    """The path as shown in a problem: relative to `root` with forward slashes when it is inside it."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


class _DuplicateKey(yaml.constructor.ConstructorError):
    pass


class StrictLoader(yaml.SafeLoader):
    """PyYAML's safe loader without the YAML 1.1 surprises a volunteer would never expect:
    only true/false are booleans (`no`, `off`, `on`, `yes`, a team code `NO` stay text); a number with a
    leading zero stays text (`007`, jersey `00`); `12:34` stays text (not 754, base 60); dates stay text
    (`2026-11-05`, parsed by the code that reads them); and a key written twice in one block is an error
    instead of the last one silently winning."""

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict:
        if isinstance(node, yaml.MappingNode):
            seen: dict[str, int] = {}
            for key_node, _ in node.value:
                if isinstance(key_node, yaml.ScalarNode) and key_node.tag != "tag:yaml.org,2002:merge":
                    if key_node.value in seen:
                        raise _DuplicateKey(None, None, f"the key {key_node.value!r} is written twice in one block "
                                            f"(also on line {seen[key_node.value] + 1})", key_node.start_mark)
                    seen[key_node.value] = key_node.start_mark.line
        return super().construct_mapping(node, deep=deep)


_DROPPED_TAGS = {f"tag:yaml.org,2002:{t}" for t in ("bool", "int", "float", "timestamp", "value")}
StrictLoader.yaml_implicit_resolvers = {
    first: [(tag, regex) for tag, regex in resolvers if tag not in _DROPPED_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
                                   list("tTfF"))
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?(?:0|[1-9][0-9]*)$"),
                                   list("-+0123456789"))
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:float",
                                   re.compile(r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?$"),
                                   list("-+.0123456789"))


def parse_yaml(text: str) -> Any:
    """Parse YAML text with StrictLoader (raises yaml.YAMLError). Every data file goes through this."""
    return yaml.load(text, Loader=StrictLoader)


def read_yaml(path: Path, file: str) -> tuple[Any, list[Problem]]:
    """Parse a YAML file with StrictLoader. Returns (data, problems); data is None for an empty file or when
    there are problems. A file that cannot be read, is not UTF-8 or is not valid YAML is one error (with the
    line) rather than a crash."""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except OSError as exc:
        return None, [Problem("error", "", f"Cannot read this file ({exc.strerror or exc}).", file)]
    except UnicodeDecodeError:
        return None, [Problem("error", "", "This file is not saved as UTF-8 text. Save it again as UTF-8 "
                                           "(most editors offer it under 'Save as' or 'Encoding').", file)]
    try:
        return parse_yaml(text), []
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        reason = getattr(exc, "problem", None) or "invalid YAML"
        if isinstance(exc, _DuplicateKey):
            return None, [Problem("error", "", f"Line {mark.line + 1}: {reason}. Keep one of them.", file)]
        return None, [Problem("error", "", f"This file is not valid YAML{where}: {reason}. {_yaml_hint(reason)}", file)]


# What usually causes PyYAML's messages, in words a volunteer can act on.
_YAML_HINTS = (
    ("expected ',' or '}'", "A comma is probably missing between two 'key: value' pairs inside { }, or a value "
                            "with a comma or colon in it needs quotes."),
    ("expected ',' or ']'", "A comma is probably missing between two items inside [ ]."),
    ("mapping values are not allowed", "A line is probably indented too far, or a value with ': ' in it needs quotes."),
    ("found character '\\t'", "The line starts with a tab: indent with spaces only."),
)


def _yaml_hint(reason: str) -> str:
    return next((hint for key, hint in _YAML_HINTS if key in reason), "Check the indentation and colons.")


# ------------------------------------------------------------------ the shared checking toolkit



def suggest(word: str, options: Iterable[str]) -> str | None:
    """The allowed word that looks most like `word` (for 'Did you mean...'), or None."""
    close = difflib.get_close_matches(str(word), list(options), n=1, cutoff=0.6)
    return close[0] if close else None


def one_of(options: Iterable[object]) -> str:
    return ", ".join(str(o) for o in options)


class Checker:
    """Collects the problems of one file. Each `check_*` method returns the value when it is the right
    kind of thing and records an error (and returns None) when it is not; `at` is the dotted path."""

    def __init__(self, file: str = "") -> None:
        self.file = file
        self.problems: list[Problem] = []

    def add(self, level: Literal["error", "warning"], at: str, message: str) -> None:
        self.problems.append(Problem(level, at, message, self.file))

    def error(self, at: str, message: str) -> None:
        self.add("error", at, message)

    def warning(self, at: str, message: str) -> None:
        self.add("warning", at, message)

    def extend(self, problems: Iterable[Problem]) -> None:
        self.problems.extend(with_file(problems, self.file))

    @property
    def ok(self) -> bool:
        """True while no error has been recorded."""
        return not has_errors(self.problems)

    def mapping(self, value: Any, at: str, *, allowed: Iterable[str] = (), required: Iterable[str] = (),
                any_keys: bool = False) -> dict | None:
        """A mapping whose keys are all in `allowed` + `required`; unknown keys are errors (usually typos) and
        missing `required` keys are errors. With `any_keys` every key is accepted (the caller checks them).
        Returns the mapping (unknown keys and all), or None if it is not one."""
        if not isinstance(value, dict):
            self.error(at, f"must be a block of 'key: value' lines, not {_describe(value)}.")
            return None
        required = list(required)
        known = list(dict.fromkeys([*required, *allowed]))
        for key in value:
            if key not in known and not any_keys:
                hint = suggest(key, known)
                self.error(join_path(at, key), f"{str(key)!r} is not a known key here."
                           + (f" Did you mean {hint!r}?" if hint else "")
                           + (f" Allowed: {one_of(known)}." if known else " This section takes no keys."))
        for key in required:
            if key not in value:
                self.error(join_path(at, key), f"is required. Add a '{key}:' line.")
        return value

    def text(self, value: Any, at: str, *, allow_empty: bool = False) -> str | None:
        if isinstance(value, str) and (value.strip() or allow_empty):
            return value
        self.error(at, "must be some text" + ("" if allow_empty else " (not empty)") + f", not {_describe(value)}."
                   + _quote_hint(value))
        return None

    def ident(self, value: Any, at: str) -> str | None:
        """An id (lower-case letters and digits, words joined by single hyphens: 'otters', 'ann-b', '2026-27').
        A whole number written without quotes (`id: 12`) is accepted as the text '12'."""
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            value = str(value)
        if isinstance(value, str) and ID_RE.fullmatch(value):
            return value
        fixed = re.sub(r"[\s_]+", "-", value.strip().lower()) if isinstance(value, str) else ""
        self.error(at, f"must be an id: lower-case letters and digits, words joined by single hyphens (like "
                       f"'otters' or 'ann-b'), not {_describe(value)}."
                   + (f" Did you mean {fixed!r}?" if ID_RE.fullmatch(fixed) else ""))
        return None

    def integer(self, value: Any, at: str, lo: int | None = None, hi: int | None = None) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and (lo is None or value >= lo) \
                and (hi is None or value <= hi):
            return value
        self.error(at, "must be a whole number" + _range_words(lo, hi) + f", not {_describe(value)}.")
        return None

    def boolean(self, value: Any, at: str) -> bool | None:
        if isinstance(value, bool):
            return value
        self.error(at, f"must be true or false, not {_describe(value)}.")
        return None

    def choice(self, value: Any, at: str, options: Sequence[object]) -> Any:
        if isinstance(value, (str, int)) and not isinstance(value, bool) and value in options:
            return value
        hint = suggest(value, [str(o) for o in options]) if isinstance(value, str) else None
        self.error(at, f"{_describe(value)} is not allowed." + (f" Did you mean {hint!r}?" if hint else "")
                   + f" Use one of: {one_of(options)}.")
        return None

    def sequence(self, value: Any, at: str) -> list | None:
        if isinstance(value, list):
            return value
        self.error(at, f"must be a list (one '- item' per line), not {_describe(value)}.")
        return None

    def pattern(self, value: Any, at: str, regex: re.Pattern[str], what: str) -> str | None:
        """Text that fully matches `regex`; `what` finishes the sentence "must be ..." in the message."""
        if isinstance(value, str) and regex.fullmatch(value):
            return value
        self.error(at, f"must be {what}, not {_describe(value)}." + _quote_hint(value))
        return None


def _quote_hint(value: Any) -> str:
    """A number or true/false where text was wanted: YAML read it as a number, so say how to keep it text."""
    if isinstance(value, (int, float)):
        return " Put it in quotes if it is meant as text."
    return ""


def _describe(value: Any) -> str:
    if value is None:
        return "empty"
    if isinstance(value, dict):
        return "a block of keys"
    if isinstance(value, list):
        return "a list"
    return repr(value)


def _range_words(lo: int | None, hi: int | None) -> str:
    if lo is not None and hi is not None:
        return f" from {lo} to {hi}"
    if lo is not None:
        return f" of {lo} or more"
    if hi is not None:
        return f" of {hi} or less"
    return ""
