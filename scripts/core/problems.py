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

from scripts.core.types import Placeholder, Problem

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


def sort_problems(problems: Iterable[Problem]) -> list[Problem]:
    """Errors first, then warnings; inside each, grouped by file, then by path (numbers in order)."""
    return sorted(problems, key=lambda p: (p.level != "error", p.file, _natural(p.at), p.message))


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
) -> int:
    """Print every problem (human text, or JSON lines with `json_lines`), plus GitHub annotations when
    `annotations` is true, and return the exit code (0 or 1). Text goes to `out` (default stderr)."""
    problems = list(problems)
    out = out or sys.stderr
    text = format_json(problems) if json_lines else format_human(problems, placeholders)
    if text:
        print(text, file=out)
    if annotations:
        for p in sort_problems(problems):
            print(github_annotation(p), file=out)
    return exit_code(problems)


# ------------------------------------------------------------------ internal errors (exit 2)

class InternalError(Exception):
    """Something the data cannot fix: a bug, or a sport function that raised. Exit code 2."""


def call_sport(name: str, func: Callable[..., Any], *args: Any) -> Any:
    """Call a sport function (check, read, present, derive). If it raises, the error names the function,
    its file and (through `__cause__`) the traceback, and becomes an InternalError."""
    try:
        return func(*args)
    except Exception as exc:
        where = getattr(getattr(func, "__code__", None), "co_filename", "a sport file")
        raise InternalError(f"the sport function {name}() in {where} raised {type(exc).__name__}: {exc}") from exc


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


def read_yaml(path: Path, file: str) -> tuple[Any, list[Problem]]:
    """Parse a YAML file. Returns (data, problems); data is None for an empty file or when there are problems.
    A file that cannot be read or is not valid YAML is one error (with the line) rather than a crash."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [Problem("error", "", f"Cannot read this file ({exc.strerror or exc}).", file)]
    try:
        return yaml.safe_load(text), []
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        reason = getattr(exc, "problem", None) or "invalid YAML"
        return None, [Problem("error", "", f"This file is not valid YAML{where}: {reason}. Check the indentation and colons.", file)]


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
        self.error(at, "must be some text" + ("" if allow_empty else " (not empty)") + f", not {_describe(value)}.")
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
        self.error(at, f"must be {what}, not {_describe(value)}.")
        return None


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
