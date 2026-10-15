"""Tests for scripts/core/problems.py (and the Problem type): path prefixing, sorting, printing, --json,
GitHub annotations, exit codes, internal errors and the shared Checker. Run with `python -m pytest`."""
import io
import json

import pytest

from scripts.core.problems import (
    EXIT_DATA, EXIT_INTERNAL, EXIT_OK, Checker, InternalError, call_sport, exit_code, format_human, format_json,
    format_problem, github_annotation, has_errors, join_path, read_yaml, report, report_internal_error,
    sort_problems, suggest, with_file, with_prefix,
)
from scripts.core.types import Placeholder, Problem


def err(at, message="m", file=""):
    return Problem("error", at, message, file)


def warn(at, message="m", file=""):
    return Problem("warning", at, message, file)


# ------------------------------------------------------------------ the type

def test_problem_is_frozen_and_checks_its_level():
    p = err("a")
    with pytest.raises(Exception):
        p.at = "b"
    with pytest.raises(ValueError):
        Problem("fatal", "a", "m")


# ------------------------------------------------------------------ paths

def test_join_path_skips_empty_parts_and_accepts_numbers():
    assert join_path("sheet", "", 3, "pts") == "sheet.3.pts"
    assert join_path("", "") == ""


def test_with_file_sets_only_missing_files():
    out = with_file([err("a"), err("b", file="other.yml")], "games/x.yml")
    assert [p.file for p in out] == ["games/x.yml", "other.yml"]


def test_with_prefix_adds_the_sheet_prefix_a_sport_leaves_out():
    out = with_prefix([err("home.running.14"), err("")], "sheet")
    assert [p.at for p in out] == ["sheet.home.running.14", "sheet"]


# ------------------------------------------------------------------ sorting

def test_errors_come_before_warnings_then_by_file_then_path():
    problems = [warn("a", file="a.yml"), err("z", file="b.yml"), err("y", file="a.yml"), err("x", file="a.yml")]
    assert [(p.level, p.file, p.at) for p in sort_problems(problems)] == [
        ("error", "a.yml", "x"), ("error", "a.yml", "y"), ("error", "b.yml", "z"), ("warning", "a.yml", "a")]


def test_row_numbers_sort_as_numbers():
    ats = ["3.name", "10.name", "2.name", "10.home", "players"]
    got = [p.at for p in sort_problems([err(a, file="f") for a in ats])]
    assert got == ["2.name", "3.name", "10.home", "10.name", "players"]


# ------------------------------------------------------------------ printing

def test_format_problem_is_file_path_message():
    assert format_problem(err("sheet.home.running.14", "no such box", "games/2026-12-03-g1.yml")) \
        == "games/2026-12-03-g1.yml: sheet.home.running.14: no such box"


def test_format_problem_leaves_out_an_empty_path_or_file():
    assert format_problem(err("", "The file is empty.", "league.yml")) == "league.yml: The file is empty."
    assert format_problem(err("name", "is required.")) == "name: is required."


def test_format_human_lists_errors_then_warnings_then_still_to_decide():
    text = format_human(
        [warn("w", "careful", "b.yml"), err("e2", "bad two", "a.yml"), err("e1", "bad one", "a.yml")],
        [Placeholder("standings.tiebreakers", "Tiebreakers")])
    lines = text.splitlines()
    assert lines[:2] == ["a.yml: e1: bad one", "a.yml: e2: bad two"]
    assert "Warnings:" in lines and "  b.yml: w: careful" in lines
    assert "  - Tiebreakers (standings.tiebreakers)" in lines
    assert lines.index("Warnings:") < next(i for i, l in enumerate(lines) if l.startswith("Still to decide"))


def test_format_human_is_empty_when_there_is_nothing_to_say():
    assert format_human([]) == ""


def test_json_output_is_one_object_per_line():
    lines = format_json([warn("b", "w", "f.yml"), err("a", "e", "f.yml")]).splitlines()
    assert [json.loads(l) for l in lines] == [
        {"level": "error", "file": "f.yml", "at": "a", "message": "e"},
        {"level": "warning", "file": "f.yml", "at": "b", "message": "w"}]


def test_github_annotation_names_file_and_path():
    p = err("sheet.final.home", "The Final box says 24.", "data/2026-27/games/2026-11-05-1.yml")
    assert github_annotation(p) == (
        "::error file=data/2026-27/games/2026-11-05-1.yml,title=sheet.final.home::The Final box says 24.")


def test_github_annotation_escapes_special_characters_and_uses_warning():
    p = warn("a,b", "50%\nnext: line", "f:1.yml")
    assert github_annotation(p) == "::warning file=f%3A1.yml,title=a%2Cb::50%25%0Anext: line"
    assert github_annotation(err("", "x")) == "::error title=Data problem::x"


# ------------------------------------------------------------------ exit codes and report()

def test_exit_codes():
    assert (EXIT_OK, EXIT_DATA, EXIT_INTERNAL) == (0, 1, 2)
    assert exit_code([]) == 0
    assert exit_code([warn("a")]) == 0          # warnings do not stop a build
    assert exit_code([warn("a"), err("b")]) == 1
    assert has_errors([err("a")]) and not has_errors([warn("a")])


def test_report_prints_and_returns_the_exit_code():
    out = io.StringIO()
    code = report([err("a", "bad", "f.yml")], [Placeholder("rules.overtime", "Overtime")], out=out)
    assert code == 1
    assert "f.yml: a: bad" in out.getvalue() and "Still to decide" in out.getvalue()


def test_report_json_and_annotations():
    out = io.StringIO()
    code = report([err("a", "bad", "f.yml")], json_lines=True, annotations=True, out=out)
    lines = out.getvalue().splitlines()
    assert code == 1
    assert json.loads(lines[0])["at"] == "a"
    assert lines[1] == "::error file=f.yml,title=a::bad"


def test_report_with_only_warnings_returns_zero():
    assert report([warn("a", "careful", "f.yml")], out=io.StringIO()) == 0


def sport_function_that_raises(sheet, ctx):
    raise KeyError("home")


def test_call_sport_turns_a_raise_into_an_internal_error_naming_the_file():
    with pytest.raises(InternalError) as info:
        call_sport("check", sport_function_that_raises, {}, None)
    assert "check()" in str(info.value) and "test_problems.py" in str(info.value)
    assert isinstance(info.value.__cause__, KeyError)
    assert call_sport("check", lambda a, b: [a, b], 1, 2) == [1, 2]


def test_report_internal_error_prints_a_traceback_and_returns_two():
    try:
        call_sport("read", sport_function_that_raises, {}, None)
    except InternalError as exc:
        out = io.StringIO()
        assert report_internal_error(exc, out) == 2
        assert "Internal error:" in out.getvalue() and "Traceback" in out.getvalue()
        assert "KeyError" in out.getvalue()


# ------------------------------------------------------------------ reading YAML

def test_read_yaml_reports_a_syntax_error_with_its_line(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("a: 1\nb: [1, 2\n", encoding="utf-8")
    data, problems = read_yaml(f, "x.yml")
    assert data is None and len(problems) == 1
    assert problems[0].file == "x.yml" and "not valid YAML" in problems[0].message and "line" in problems[0].message


def test_read_yaml_missing_file_is_a_problem_not_a_crash(tmp_path):
    data, problems = read_yaml(tmp_path / "nope.yml", "nope.yml")
    assert data is None and problems[0].level == "error"


# ------------------------------------------------------------------ the Checker

def test_checker_mapping_flags_unknown_keys_with_a_suggestion_and_path():
    c = Checker("league.yml")
    c.mapping({"colur": "#fff", "name": "x"}, "", allowed=["colour"], required=["name"])
    [p] = c.problems
    assert (p.file, p.at, p.level) == ("league.yml", "colur", "error")
    assert "Did you mean 'colour'?" in p.message and "Allowed: name, colour" in p.message


def test_checker_mapping_names_the_missing_key():
    c = Checker("f.yml")
    c.mapping({"a": 1}, "section", allowed=["a"], required=["b"])
    assert [(p.at, p.message) for p in c.problems] == [("section.b", "is required. Add a 'b:' line.")]


def test_checker_mapping_with_no_keys_allowed_says_so():
    c = Checker("f.yml")
    c.mapping({"x": 1}, "rules")
    assert "takes no keys" in c.problems[0].message


def test_checker_rejects_a_non_mapping():
    c = Checker("f.yml")
    assert c.mapping([1], "rules") is None
    assert c.problems[0].at == "rules"


def test_checker_integer_rejects_bool_text_and_out_of_range():
    c = Checker("f.yml")
    assert c.integer(3, "a", 1, 9) == 3
    assert c.integer(True, "b") is None
    assert c.integer("3", "c") is None
    assert c.integer(12, "d", 1, 9) is None
    assert [p.at for p in c.problems] == ["b", "c", "d"]
    assert "from 1 to 9" in c.problems[2].message


def test_checker_choice_lists_the_options_and_suggests():
    c = Checker("f.yml")
    assert c.choice("12h", "t", ["12h", "24h"]) == "12h"
    assert c.choice("12 h", "t", ["12h", "24h"]) is None
    assert "Use one of: 12h, 24h." in c.problems[0].message


def test_checker_text_and_boolean_and_sequence():
    c = Checker("f.yml")
    assert c.text("ok", "a") == "ok"
    assert c.text("  ", "b") is None and c.text(5, "c") is None
    assert c.text("", "d", allow_empty=True) == ""
    assert c.boolean("yes", "e") is None and c.boolean(False, "f") is False
    assert c.sequence({"a": 1}, "g") is None
    assert [p.at for p in c.problems] == ["b", "c", "e", "g"]


def test_checker_ok_ignores_warnings():
    c = Checker("f.yml")
    c.warning("a", "careful")
    assert c.ok
    c.error("b", "bad")
    assert not c.ok


def test_suggest():
    assert suggest("head2head", ["head_to_head", "wins"]) == "head_to_head"
    assert suggest("zzzz", ["head_to_head", "wins"]) is None
