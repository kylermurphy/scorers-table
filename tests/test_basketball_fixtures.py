"""The basketball fixtures (sports/basketball/fixtures/, docs/stage-5-basketball-spec.md section 8): one game file
per case, the problems `check` must report (level, path, message, in order) and the numbers `read` must give.

Each case is `<name>.yml` (`fixture: {folder, game_type, options}` and `sheet:`) with `<name>.expected.json`
(`problems`, and `reading`: null when there is an error or a draft leaves out a block, else score, lines and facts). `context.yml` holds the
two teams, the players and the league settings they are checked with. The stage 7 JavaScript rules are tested
against the same files. `UPDATE_FIXTURES=1 python -m pytest tests/test_basketball_fixtures.py` rewrites the
expected files; read the diff before committing it.
"""
import copy
import json
import os
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from scripts.core.model import Player, SportContext, Team
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, load_sport

FIXTURES = Path(__file__).resolve().parent.parent / "sports" / "basketball" / "fixtures"
CASES = sorted(p.name[:-len(".yml")] for p in FIXTURES.glob("*.yml") if p.name != "context.yml")
UPDATE = bool(os.environ.get("UPDATE_FIXTURES"))

SPORT, LOAD_PROBLEMS = load_sport("basketball", SPORTS_ROOT)


def load_context():
    raw = parse_yaml((FIXTURES / "context.yml").read_text(encoding="utf-8"))
    teams = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in raw["teams"]}
    players = {p["id"]: Player(p["id"], p["name"], p["team"], p.get("number"), p.get("sub", False)) for p in raw["players"]}
    return raw, teams, players


def load_case(name):
    return parse_yaml((FIXTURES / f"{name}.yml").read_text(encoding="utf-8"))


def context_for(case):
    raw, teams, players = load_context()
    fixture = case["fixture"]
    defaults = {key: opt["default"] for key, opt in SPORT.spec["options"].items()}
    options = {**defaults, **raw["options"], **fixture["options"]}
    return SportContext(sport=SPORT.spec, options=options, teams=teams, players=players, sides=raw["sides"],
                        game_type=fixture["game_type"], folder=fixture["folder"])


def readable(problems):
    """`read` is for a sheet `check` accepted: no error, and (a draft) no block or side left out. A draft with
    warnings only for a sub's missing id or a missing line still reads."""
    left_out = [p for p in problems if p.level == "warning" and p.at.split(".")[0] in ("players", "running", "boxes")
                and p.at.count(".") <= 1]
    return not any(p.level == "error" for p in problems) and not left_out


def run(name):
    """(problems as dicts, reading as a dict or None) for one case, through call_sport so the shapes are checked too."""
    case = load_case(name)
    ctx = context_for(case)
    problems = call_sport("check", SPORT.rules.check, case["sheet"], ctx)
    result = [{"level": p.level, "at": p.at, "message": p.message} for p in problems]
    reading = None
    if readable(problems):
        read = call_sport("read", SPORT.rules.read, case["sheet"], ctx)
        assert read.team_lines == {}
        reading = {"score": asdict(read.score), "lines": [asdict(ln) for ln in read.lines], "facts": read.facts}
    return result, reading


def expected_text(problems, reading):
    return json.dumps({"problems": problems, "reading": reading}, indent=2, ensure_ascii=False) + "\n"


def test_the_sport_loads_and_has_its_fixtures():
    assert not [p for p in LOAD_PROBLEMS if p.level == "error"], LOAD_PROBLEMS
    assert len(CASES) >= 60
    assert (FIXTURES / "context.yml").is_file()


def test_every_case_has_an_expected_file_and_no_expected_file_is_left_over():
    expected = {p.name[:-len(".expected.json")] for p in FIXTURES.glob("*.expected.json")}
    if UPDATE:
        return
    assert expected == set(CASES)


@pytest.mark.parametrize("name", CASES)
def test_fixture(name):
    problems, reading = run(name)
    path = FIXTURES / f"{name}.expected.json"
    if UPDATE:
        path.write_text(expected_text(problems, reading), encoding="utf-8")
        return
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert problems == expected["problems"]
    assert reading == expected["reading"]


# ------------------------------------------------------------------ the ten Masters cases

MASTERS_CASES = ("clean", "and-one", "bad-final", "draft-with-sub", "ft-mismatch", "overtime", "page-two", "tie",
                 "tie-without-overtime", "unknown-jersey")


def test_the_ten_masters_cases_are_all_there():
    assert set(MASTERS_CASES) <= set(CASES)


def test_the_masters_numbers_are_the_same():
    """The figures of Masters' expected.json (tests/fixtures/sheets/ in tb-masters-basketball/website) for the
    cases with no error: the same points, free throws, fouls and quarter scores."""
    _, reading = run("clean")
    got = {ln["player"]: (ln["counts"]["pts"], ln["counts"]["ftm"], ln["counts"]["fta"], ln["counts"]["pf"], ln["counts"]["tech"])
           for ln in reading["lines"]}
    assert got == {"al-a": (9, 2, 3, 2, 0), "amy-b": (6, 0, 1, 0, 0), "ann-c": (7, 1, 1, 1, 0), "bo-c": (8, 1, 1, 3, 1),
                   "bev-d": (7, 1, 2, 0, 0), "bud-e": (4, 1, 2, 0, 0)}
    assert reading["score"]["final"] == {"home": 22, "away": 19}
    assert reading["score"]["periods"] == {"home": [5, 7, 5, 5], "away": [5, 5, 6, 3]}
    _, reading = run("and-one")
    assert {ln["player"]: ln["counts"]["pts"] for ln in reading["lines"]} == {
        "al-a": 10, "amy-b": 6, "ann-c": 6, "bo-c": 8, "bev-d": 7, "bud-e": 4}
    _, reading = run("overtime")
    assert reading["score"]["final"] == {"home": 25, "away": 24}
    assert reading["score"]["periods"] == {"home": [5, 7, 5, 5], "away": [5, 5, 6, 6]}
    assert reading["score"]["extra"] == {"home": [3], "away": [2]} and reading["score"]["decided_in"] == "overtime"
    _, reading = run("page-two")
    assert reading["score"]["final"] == {"home": 104, "away": 98}
    assert {ln["player"]: (ln["counts"]["pts"], ln["counts"]["ftm"], ln["counts"]["fta"]) for ln in reading["lines"]}["al-a"] == (40, 9, 13)
    _, reading = run("tie")
    assert reading["score"]["final"] == {"home": 24, "away": 24} and reading["score"]["decided_in"] == "overtime"


def test_the_masters_problems_are_the_same_at_the_same_boxes():
    """Masters' expected problems, with its team ids replaced by home and away (aa -> home, bb -> away)."""
    def at_of(case):
        problems, _ = run(case)
        return [(p["level"], p["at"]) for p in problems]
    assert at_of("clean") == [] and at_of("and-one") == [] and at_of("overtime") == []
    assert at_of("page-two") == [] and at_of("tie") == []
    assert at_of("bad-final") == [("error", "boxes.away.final")]
    assert at_of("ft-mismatch") == [("warning", "players.away.2.ft")]
    assert at_of("unknown-jersey") == [("error", "running.away.14")]
    assert at_of("tie-without-overtime") == [("error", "boxes.home.final")]
    assert at_of("draft-with-sub") == [("warning", "players.away.3.player")]      # its review line is the core's


# ------------------------------------------------------------------ every row of the spec's table 3.1

# (what the row checks, the case, level, path): the case's expected problems must hold that level and path.
ROWS = [
    ("a key other than players running lines boxes notes", "unknown-sheet-key", "error", "form"),
    ("players missing", "no-players", "error", "players"),
    ("players missing, in a draft", "no-players-draft", "warning", "players"),
    ("players: not home + away", "players-one-side", "error", "players.away"),
    ("players: an unknown side", "unknown-side", "error", "players.zzz"),
    ("running missing", "no-running", "error", "running"),
    ("running missing, in a draft", "no-running-draft", "warning", "running"),
    ("running: only one side", "running-one-side", "error", "running.away"),
    ("running: a side that is not a block", "running-side-not-a-block", "error", "running.home"),
    ("boxes missing", "no-boxes", "error", "boxes"),
    ("boxes: not a block", "boxes-not-a-block", "error", "boxes.home"),
    ("players.<side>: not a list", "roster-not-a-list", "error", "players.home"),
    ("players.<side>: empty", "empty-roster", "error", "players.home"),
    ("players.<side>: more than 15 rows", "too-many-rows", "error", "players.home"),
    ("players.<side>: nobody ticked Here", "nobody-here", "error", "players.away"),
    ("players.<side>.<i>: not a row", "row-not-a-block", "error", "players.home.3"),
    ("players.<side>.<i>: an unknown key", "unknown-row-key", "error", "players.home.0.pts"),
    ("num not 0-99", "bad-jersey-number", "error", "players.home.3.num"),
    ("the same number on two rows", "duplicate-jersey", "error", "players.home.3.num"),
    ("player missing (a name only), final file", "name-only-row-in-a-final-file", "error", "players.away.3.player"),
    ("player missing (a name only), draft", "draft-with-sub", "warning", "players.away.3.player"),
    ("player not in players.yml", "unknown-player", "error", "players.home.3.player"),
    ("player listed twice", "duplicate-player", "error", "players.home.3.player"),
    ("player on another team and not a sub", "player-on-the-other-team", "warning", "players.home.3.player"),
    ("here not true or false", "here-not-true-or-false", "error", "players.home.3.here"),
    ("ft not made of M and X", "bad-free-throw-circles", "error", "players.home.0.ft"),
    ("ft not text", "free-throws-not-text", "error", "players.home.0.ft"),
    ("more than 20 circles", "too-many-free-throws", "error", "players.home.0.ft.20"),
    ("fouls over the limit", "fouls-over-the-limit", "error", "players.home.0.fouls"),
    ("fouls not a count", "fouls-not-a-count", "error", "players.home.0.fouls"),
    ("tech over 2", "technicals-over-two", "error", "players.away.0.tech"),
    ("more made free throws than scores", "ft-mismatch", "warning", "players.away.2.ft"),
    ("running: not a box from 1 to 250", "total-off-the-sheet", "error", "running.home.251"),
    ("running: a jump that is not 1, 2 or 3", "jump-of-four", "error", "running.home.11"),
    ("running: not a jersey number", "scorer-not-a-jersey-number", "error", "running.away.14"),
    ("running: a number on no row", "unknown-jersey", "error", "running.away.14"),
    ("running: a scorer not ticked Here", "scorer-not-ticked-here", "error", "running.home.22"),
    ("lines missing", "no-lines", "error", "lines"),
    ("lines missing, in a draft", "no-lines-draft", "warning", "lines"),
    ("lines.<side> missing", "lines-one-side", "error", "lines.home"),
    ("lines: not a block", "lines-not-a-block", "error", "lines"),
    ("lines.<side>: not four running totals", "lines-wrong-count", "error", "lines.home"),
    ("lines.<side>.<q>: under a total with no box", "line-under-no-box", "error", "lines.home.2"),
    ("lines.<side>.<q>: above the line before", "quarters-go-down", "error", "lines.home.2"),
    ("boxes q<n>: not a count", "quarter-box-empty", "error", "boxes.home.q2"),
    ("boxes q<n>: not the total at its line", "quarter-box-off-its-line", "error", "boxes.home.q2"),
    ("boxes q<n>: less than the box before", "quarters-go-down", "error", "boxes.home.q3"),
    ("boxes final: not a count", "final-not-a-count", "error", "boxes.away.final"),
    ("boxes final: not the last running total", "bad-final", "error", "boxes.away.final"),
    ("boxes q4 more than the Final box", "q4-above-final", "error", "boxes.home.q4"),
    ("boxes ot: not the total after overtime", "overtime-box-wrong", "error", "boxes.home.ot"),
    ("boxes ot: filled in with no overtime", "overtime-box-without-overtime", "error", "boxes.home.ot"),
    ("boxes ot: filled in when overtime: none", "no-overtime-rule-box-filled-in", "error", "boxes.home.ot"),
    ("boxes: an unknown box", "unknown-box-key", "error", "boxes.home.q5"),
    ("boxes.home.q4: overtime but Q4 not tied", "overtime-without-a-tied-q4", "error", "boxes.home.q4"),
    ("boxes.home.final: tied after Q4, no overtime", "tie-without-overtime", "error", "boxes.home.final"),
    ("boxes.home.final: tied after Q4, no overtime, playoff", "tie-in-a-playoff-without-overtime", "error", "boxes.home.final"),
    ("notes: not a list", "notes-not-a-list", "error", "notes"),
    ("notes.<n>: not an entry", "note-not-an-entry", "error", "notes.0"),
    ("notes.<n>: an unknown key", "unknown-note-key", "error", "notes.0.when"),
    ("notes.<n>.kind", "bad-note-kind", "error", "notes.0.kind"),
    ("a flagrant's side", "flagrant-bad-side", "error", "notes.0.side"),
    ("a flagrant's number on no row", "flagrant-number-on-no-row", "error", "notes.0.num"),
    ("a flagrant's quarter", "flagrant-bad-quarter", "error", "notes.0.q"),
    ("more flagrants than foul boxes", "flagrant-more-than-fouls", "error", "players.away.1.fouls"),
]


@pytest.mark.parametrize("what, name, level, at", ROWS, ids=[r[0] for r in ROWS])
def test_every_row_of_the_checks_table_has_a_fixture(what, name, level, at):
    assert name in CASES, f"no fixture {name}.yml for: {what}"
    problems, _ = run(name)
    assert (level, at) in [(p["level"], p["at"]) for p in problems], (what, problems)


# ------------------------------------------------------------------ the cases that should be quiet, and the numbers they give

QUIET = ("clean", "and-one", "overtime", "page-two", "tie", "scoreless-overtime", "flagrant", "flagrant-in-overtime",
         "spare-fills-in", "jersey-zero-and-double-zero", "fifteen-rows", "two-technicals", "twenty-free-throws",
         "fouls-over-the-limit-set-higher", "no-overtime-rule-level-game", "tie-after-overtime-in-a-playoff", "note-in-a-draft")


@pytest.mark.parametrize("name", QUIET)
def test_these_cases_have_no_error(name):
    problems, reading = run(name)
    assert not [p for p in problems if p["level"] == "error"], problems
    assert reading is not None


def test_a_sub_not_in_players_yml_gets_no_line_and_a_spare_does():
    _, draft = run("draft-with-sub")
    assert "bo-c" in {ln["player"] for ln in draft["lines"]} and all(ln["player"] for ln in draft["lines"])
    assert len([ln for ln in draft["lines"] if ln["side"] == "away"]) == 3
    _, spare = run("spare-fills-in")
    sam = next(ln for ln in spare["lines"] if ln["player"] == "sam-p")
    assert sam["side"] == "home" and sam["counts"]["pts"] == 0


def test_a_player_not_ticked_here_gets_no_line():
    _, reading = run("clean")
    assert "ari-d" not in {ln["player"] for ln in reading["lines"]}


def test_zero_and_double_zero_are_two_jerseys():
    _, reading = run("jersey-zero-and-double-zero")
    pts = {ln["player"]: ln["counts"]["pts"] for ln in reading["lines"]}
    assert pts["bob-g"] == 7 and pts["bas-h"] == 4 and pts["bo-c"] == 8


def test_a_scoreless_overtime_is_decided_in_overtime_with_nothing_scored():
    _, reading = run("scoreless-overtime")
    score = reading["score"]
    assert score["decided_in"] == "overtime" and score["extra"] == {"home": [0], "away": [0]}
    assert score["final"] == {"home": 22, "away": 22}


def test_with_no_overtime_a_level_game_stays_regulation():
    _, reading = run("no-overtime-rule-level-game")
    assert reading["score"]["decided_in"] == "regulation" and reading["score"]["extra"] == {}
    assert reading["score"]["final"] == {"home": 22, "away": 22}


def test_flagrants_and_technicals_are_facts_and_the_notes_text_is_not():
    _, reading = run("flagrant")
    assert reading["facts"] == {"technicals": [{"side": "away", "player": "bo-c", "num": "5", "count": 1}],
                                "flagrants": [{"side": "away", "player": "bo-c", "num": "5", "q": 3}]}
    assert "elbow" not in json.dumps(reading)
    bo = next(ln for ln in reading["lines"] if ln["player"] == "bo-c")
    assert bo["counts"] == {"pts": 8, "ftm": 1, "fta": 1, "pf": 3, "tech": 1, "flagrant": 1}
    _, reading = run("flagrant-in-overtime")
    assert reading["facts"]["flagrants"] == [{"side": "home", "player": "al-a", "num": "4", "q": "OT"}]


def test_final_at_names_each_final_box_from_the_top_of_the_file():
    _, reading = run("clean")
    assert reading["score"]["final_at"] == {"home": "sheet.boxes.home.final", "away": "sheet.boxes.away.final"}


# ------------------------------------------------------------------ properties of check over every fixture

def get(node, parts):
    for part in parts:
        if isinstance(node, dict):
            node = next(v for k, v in node.items() if str(k) == part)
        else:
            node = node[int(part)]
    return node


def resolves(sheet, at):
    """The path leads to a node, or to a missing key whose parent exists (a block or a list), or past a string
    (the 21st free-throw circle)."""
    if at == "":
        return True
    parts = at.split(".")
    for cut in (len(parts), len(parts) - 1):
        try:
            node = get(sheet, parts[:cut])
        except (StopIteration, KeyError, IndexError, ValueError):
            continue
        return cut == len(parts) or isinstance(node, (dict, list, str))
    return False


@pytest.mark.parametrize("name", CASES)
def test_every_path_points_into_the_sheet_and_check_changes_nothing(name):
    case = load_case(name)
    ctx = context_for(case)
    sheet, ctx_before = copy.deepcopy(case["sheet"]), copy.deepcopy(ctx)
    for p in SPORT.rules.check(sheet, ctx):
        assert resolves(sheet, p.at), (p.at, p.message)
        assert p.message and p.message == p.message.strip()
    assert sheet == case["sheet"] and ctx == ctx_before


@pytest.mark.parametrize("name", CASES)
def test_a_draft_is_never_stricter_than_a_final_file(name):
    case = load_case(name)
    ctx = context_for(case)
    final = SPORT.rules.check(case["sheet"], replace(ctx, folder="games"))
    draft = SPORT.rules.check(case["sheet"], replace(ctx, folder="drafts"))
    assert sum(p.level == "error" for p in draft) <= sum(p.level == "error" for p in final)
    assert [p.at for p in draft] == [p.at for p in final]
