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
from scripts.core.model import Line, Placeholder, Problem, Reading, Score, SportContext


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


def test_files_are_listed_in_the_order_to_fix_them():
    """league.yml, then seasons.yml, then a season's teams, players and schedule, then its game files: the cause
    of a cascade (a broken teams.yml) comes before what it causes."""
    files = ["data/s1/games/2026-11-05-1.yml", "data/s1/schedule.csv", "data/s1/players.yml", "data/s1/teams.yml",
             "data/seasons.yml", "league.yml", "data/s2/teams.yml"]
    got = [p.file for p in sort_problems([err("x", file=f) for f in files])]
    assert got == ["league.yml", "data/seasons.yml", "data/s1/teams.yml", "data/s1/players.yml",
                   "data/s1/schedule.csv", "data/s1/games/2026-11-05-1.yml", "data/s2/teams.yml"]


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


def test_report_json_and_annotations_go_to_the_data_stream():
    out, data = io.StringIO(), io.StringIO()
    code = report([err("a", "bad", "f.yml")], json_lines=True, annotations=True, out=out, data_out=data)
    lines = data.getvalue().splitlines()
    assert code == 1 and out.getvalue() == ""
    assert json.loads(lines[0])["at"] == "a"
    assert lines[1] == "::error file=f.yml,title=a::bad"


def test_report_defaults_human_text_to_stderr_and_data_to_stdout(capsys):
    report([err("a", "bad", "f.yml")], annotations=True)
    captured = capsys.readouterr()
    assert captured.err.strip() == "f.yml: a: bad"
    assert captured.out.strip() == "::error file=f.yml,title=a::bad"


def test_report_with_only_warnings_returns_zero():
    assert report([warn("a", "careful", "f.yml")], out=io.StringIO()) == 0


def sport_function_that_raises(sheet, ctx):
    raise KeyError("home")


def test_call_sport_turns_a_raise_into_an_internal_error_naming_the_file():
    with pytest.raises(InternalError) as info:
        call_sport("check", sport_function_that_raises, {}, None)
    assert "check()" in str(info.value) and "test_problems.py" in str(info.value)
    assert isinstance(info.value.__cause__, KeyError)
    assert call_sport("other", lambda a, b: [a, b], 1, 2) == [1, 2]       # no shape check for other names


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


def test_read_yaml_keeps_yaml_1_1_surprises_as_text(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("a: no\nb: ON\nc: 007\nd: 00\ne: 12:34\nf: 2026-11-05\ng: 010\nh: yes\ni: off\n"
                 "j: 7\nk: true\nl: False\nm: 1.5\nn: null\no: -3\np: 0\nq: =\n", encoding="utf-8")
    data, problems = read_yaml(f, "x.yml")
    assert problems == []
    assert data == {"a": "no", "b": "ON", "c": "007", "d": "00", "e": "12:34", "f": "2026-11-05", "g": "010",
                    "h": "yes", "i": "off", "j": 7, "k": True, "l": False, "m": 1.5, "n": None, "o": -3, "p": 0,
                    "q": "="}


def test_read_yaml_rejects_a_key_written_twice(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("home: otters\naway: ravens\nhome: moose\n", encoding="utf-8")
    data, problems = read_yaml(f, "x.yml")
    assert data is None and len(problems) == 1
    assert problems[0].message == "Line 3: the key 'home' is written twice in one block (also on line 1). Keep one of them."


def test_read_yaml_allows_anchors_and_merge_keys(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("base: &b {win: 2, loss: 0}\nover:\n  <<: *b\n  win: 3\n", encoding="utf-8")
    data, problems = read_yaml(f, "x.yml")
    assert problems == [] and data["over"] == {"win": 3, "loss": 0}


def test_read_yaml_handles_a_bom_and_reports_non_utf8(tmp_path):
    f = tmp_path / "x.yml"
    f.write_bytes("\ufeffname: Caf\u00e9\n".encode("utf-8"))
    assert read_yaml(f, "x.yml") == ({"name": "Caf\u00e9"}, [])
    f.write_bytes("name: Caf\u00e9\n".encode("latin-1"))
    data, problems = read_yaml(f, "x.yml")
    assert data is None and "not saved as UTF-8" in problems[0].message


def test_read_yaml_of_an_empty_file_or_a_list(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("", encoding="utf-8")
    assert read_yaml(f, "x.yml") == (None, [])
    f.write_text("- a\n- b\n", encoding="utf-8")
    assert read_yaml(f, "x.yml") == (["a", "b"], [])


def test_checker_ident_accepts_ids_and_whole_numbers():
    c = Checker("f.yml")
    assert c.ident("ann-b", "a") == "ann-b" and c.ident(12, "b") == "12" and c.ident("2026-27", "c") == "2026-27"
    assert c.ident("Ann B", "d") is None and c.ident(True, "e") is None and c.ident("a--b", "f") is None
    assert [p.at for p in c.problems] == ["d", "e", "f"]


def test_checker_text_says_to_quote_a_number():
    c = Checker("f.yml")
    c.text(1985, "name")
    assert "Put it in quotes" in c.problems[0].message


# ------------------------------------------------------------------ call_sport checks what a sport returns

SPEC = {"stats": {"player": [{"key": "pts"}], "goalie": [{"key": "ga"}], "derived": [{"key": "ppg"}],
                  "team": [{"key": "ends"}]}}
CTX = SportContext(sport=SPEC, options={}, teams={}, players={}, sides={"home": "a", "away": "b"},
                   game_type="regular", folder="games")


def score(**changes):
    base = dict(final={"home": 2, "away": 1}, periods={"home": [1, 1], "away": [1, None]},
                final_at={"home": "sheet.final.home", "away": "sheet.final.away"})
    return Score(**{**base, **changes})


def shape_error(name, value):
    with pytest.raises(InternalError) as info:
        call_sport(name, lambda *a: value, {}, CTX)
    assert "returned the wrong shape" in str(info.value)
    return str(info.value)


def test_call_sport_accepts_good_shapes():
    reading = Reading(score(), [Line("home", "ann-b", "player", {"pts": 2}), Line("away", "joe-k", "goalie", {"ga": 2})],
                      {"home": {"ends": 3}}, {"hammer": "home"})
    assert call_sport("read", lambda *a: reading, {}, CTX) is reading
    assert call_sport("check", lambda *a: [err("x")], {}, CTX) == [err("x")]
    assert call_sport("present", lambda *a: {"blocks": [{"type": "note", "text": "x"}]}, None, CTX)
    assert call_sport("derive", lambda *a: {"ppg": 2.5, "x": None, "n": 1}, {}, "player")


@pytest.mark.parametrize("name, value, words", [
    ("check", None, "list of Problem"),
    ("check", ["oops"], "not a Problem"),
    ("read", {}, "must return a Reading"),
    ("read", Reading(score(final={"home": 2})), "Score.final"),
    ("read", Reading(score(final={"home": 2, "away": True})), "Score.final['away']"),
    ("read", Reading(score(periods={"home": [1], "away": [1, 2]})), "same number of periods"),
    ("read", Reading(score(extra={"home": [1], "away": []})), "Score.extra"),
    ("read", Reading(score(decided_in="ot")), "decided_in"),
    ("read", Reading(score(final_at={})), "Score.final_at"),
    ("read", Reading(score(final_at={"home": "final.home", "away": "final.away"})), "sheet.final.home"),
    ("read", Reading(score(), [Line("left", "ann-b")]), "side 'home' or 'away'"),
    ("read", Reading(score(), [Line("home", "ann-b", "skater", {})]), "not a stats group"),
    ("read", Reading(score(), [Line("home", "ann-b", "player", {"goals": 1})]), "goals"),
    ("read", Reading(score(), [Line("home", "ann-b", "player", {"pts": 1.5})]), "whole numbers"),
    ("read", Reading(score(), [], {"otters": {}}), "team_lines"),
    ("read", Reading(score(), [], {"home": {"stolen": 1}}), "stolen"),
    ("present", [], "must return a dict"),
    ("present", {"blocks": [{"type": "chart"}]}, "stat_table, note"),
    ("present", {"extra": 1}, "unknown keys"),
    ("derive", {"ppg": "2.5"}, "numbers or None"),
    ("derive", {"ppg": True}, "numbers or None"),
])
def test_call_sport_refuses_a_wrong_shape(name, value, words):
    assert words in shape_error(name, value)


@pytest.mark.parametrize("text,hint", [
    ("- {id: otters name: Otters}\n", "A comma is probably missing"),
    ("- [a b: c\n", "A comma is probably missing between two items"),
    ("a: b\n  c: d\n", "indented too far"),
    ("a:\n\t- b\n", "indent with spaces only"),
    ("a: 'unclosed\n", "Check the indentation"),
])
def test_invalid_yaml_says_what_probably_went_wrong(tmp_path, text, hint):
    path = tmp_path / "teams.yml"
    path.write_text(text, encoding="utf-8")
    data, problems = read_yaml(path, "teams.yml")
    assert data is None and len(problems) == 1 and problems[0].at == ""
    assert problems[0].message.startswith("This file is not valid YAML (line") and hint in problems[0].message


def test_an_id_with_capitals_or_spaces_gets_a_suggestion():
    c = Checker("teams.yml")
    assert c.ident("Otters", "0.id") is None and c.ident("Big Bears", "1.id") is None and c.ident("#1", "2.id") is None
    messages = [p.message for p in c.problems]
    assert messages[0].endswith("Did you mean 'otters'?") and messages[1].endswith("Did you mean 'big-bears'?")
    assert "Did you mean" not in messages[2]
