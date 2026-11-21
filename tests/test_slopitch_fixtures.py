"""The slopitch fixtures (sports/slopitch/fixtures/, docs/stage-5-slopitch-spec.md section 8): one game file per case,
the problems `check` must report (level, path, message, in order) and the numbers `read` must give.

Each case is `<name>.yml` (`fixture: {folder, game_type, options}` and `sheet:`) with `<name>.expected.json`
(`problems`, and `reading`: null when there is an error or a draft leaves out a box, else score, lines and facts).
`context.yml` holds the teams, the players and the league settings they are checked with. The stage 7 JavaScript
rules are tested against the same files (a case marked `python_only` is for Python alone). `UPDATE_FIXTURES=1 python
-m pytest tests/test_slopitch_fixtures.py` rewrites the expected files; read the diff before committing it.
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

FIXTURES = Path(__file__).resolve().parent.parent / "sports" / "slopitch" / "fixtures"
CASES = sorted(p.name[:-len(".yml")] for p in FIXTURES.glob("*.yml") if p.name != "context.yml")
UPDATE = bool(os.environ.get("UPDATE_FIXTURES"))

SPORT, LOAD_PROBLEMS = load_sport("slopitch", SPORTS_ROOT)


def load_context():
    raw = parse_yaml((FIXTURES / "context.yml").read_text(encoding="utf-8"))
    teams = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in raw["teams"]}
    players = {p["id"]: Player(p["id"], p["name"], p["team"], p.get("number"), p.get("sub", False), p.get("position"))
               for p in raw["players"]}
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


def readable(sheet, ctx):
    """`read` is for a sheet `check` accepted. A draft reads when it has no error and, written as a finished file,
    its only errors are batting rows with no player id yet (a spare written in by name)."""
    if any(p.level == "error" for p in SPORT.rules.check(sheet, ctx)):
        return False
    final = [p for p in SPORT.rules.check(sheet, replace(ctx, folder="games")) if p.level == "error"]
    return all(p.at.startswith("batting.") and p.at.endswith(".player") for p in final)


def run(name):
    """(problems as dicts, reading as a dict or None) for one case, through call_sport so the shapes are checked too."""
    case = load_case(name)
    ctx = context_for(case)
    problems = call_sport("check", SPORT.rules.check, case["sheet"], ctx)
    result = [{"level": p.level, "at": p.at, "message": p.message} for p in problems]
    reading = None
    if readable(case["sheet"], ctx):
        read = call_sport("read", SPORT.rules.read, case["sheet"], ctx)
        reading = {"score": asdict(read.score), "lines": [asdict(ln) for ln in read.lines], "team_lines": read.team_lines,
                   "facts": read.facts}
    return result, reading


def expected_text(problems, reading):
    return json.dumps({"problems": problems, "reading": reading}, indent=2, ensure_ascii=False) + "\n"


def test_the_sport_loads_and_has_its_fixtures():
    assert not [p for p in LOAD_PROBLEMS if p.level == "error"], LOAD_PROBLEMS
    assert len(CASES) >= 70
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


# ------------------------------------------------------------------ every row of the spec's table 3.1

# (what the row checks, the case, level, path): the case's expected problems must hold that level and path.
ROWS = [
    ("a key other than runs totals called bats_first batting", "unknown-keys", "error", "umpire"),
    ("the sheet is not a block", "not-a-block", "error", ""),
    ("bats_first not home or away", "bats-first-bad", "error", "bats_first"),
    ("runs missing", "runs-missing", "error", "runs"),
    ("runs missing, in a draft", "runs-missing-draft", "warning", "runs"),
    ("runs not a block", "runs-not-a-block", "error", "runs"),
    ("runs: an unknown side", "runs-unknown-side", "error", "runs.zzz"),
    ("runs.<side> missing", "runs-side-missing", "error", "runs.home"),
    ("runs.<side> not a list", "runs-not-a-list", "error", "runs.home"),
    ("runs.<side> an empty list", "runs-empty-list", "error", "runs.home"),
    ("runs.<side> more than innings + 10 boxes", "runs-too-long", "error", "runs.home"),
    ("the two lists of different lengths", "lists-differ", "error", "runs.home"),
    ("runs.<side>.<i> empty", "run-box-empty", "error", "runs.home.3"),
    ("runs.<side>.<i> empty, in a draft", "run-box-draft", "warning", "runs.home.3"),
    ("runs.<side>.<i> text", "run-box-text", "error", "runs.away.2"),
    ("runs.<side>.<i> negative", "run-box-negative", "error", "runs.home.4"),
    ("runs.<side>.<i> above 99", "run-box-too-big", "error", "runs.away.6"),
    ("runs.<side>.<i> true", "run-box-true", "error", "runs.away.2"),
    ("X in the team batting first", "x-in-away", "error", "runs.away.6"),
    ("X in the team batting first (bats_first: home)", "x-in-home-batting-first", "error", "runs.home.6"),
    ("X in any box but the final inning's", "x-not-last", "error", "runs.home.2"),
    ("X although the team batting last trailed", "x-not-leading", "error", "runs.home.6"),
    ("X although the team batting last was level", "x-when-level", "error", "runs.home.6"),
    ("a number in the final box although the team batting last led", "number-where-x", "warning", "runs.home.6"),
    ("more runs than run_limit in a limited inning", "over-limit", "error", "runs.home.1"),
    ("more runs than run_limit + 3 (limit_play: finish)", "over-limit-finish-too-many", "error", "runs.home.1"),
    ("a limit in every inning (open_innings: none)", "open-none", "error", "runs.away.6"),
    ("fewer innings than innings and no called", "short-not-called", "error", "called"),
    ("called not one of the five words", "called-bad-word", "error", "called"),
    ("called on a game of innings or more", "called-full-game", "error", "called"),
    ("called: mercy when mercy_runs is 0", "called-mercy-no-rule", "error", "called"),
    ("called: mercy and the lead is less than mercy_runs", "called-mercy-short-lead", "warning", "called"),
    ("called: mercy and fewer than mercy_after innings", "called-mercy-short-innings", "warning", "called"),
    ("a called game shorter than official_innings", "called-under-official", "warning", "called"),
    ("more innings than innings although the score was not level", "extra-not-tied", "error", "runs.away.7"),
    ("extra innings in a regular-season game beyond extra_innings (0)", "extra-innings-regular-0", "error", "runs.away.7"),
    ("extra innings in a regular-season game beyond extra_innings (2)", "extra-innings-regular-over", "error", "runs.away.9"),
    ("an extra inning after a team led at the end of a complete extra inning", "extra-after-decided", "error", "runs.away.8"),
    ("a walk-off half with more runs than needed + 3", "walk-off-too-many", "warning", "runs.home.6"),
    ("totals missing", "totals-missing", "error", "totals"),
    ("totals not a block", "totals-not-a-block", "error", "totals"),
    ("totals: an unknown side", "totals-unknown-side", "error", "totals.zzz"),
    ("totals.<side> missing", "totals-side-missing", "error", "totals.away"),
    ("totals.<side> not a row", "totals-side-not-a-row", "error", "totals.away"),
    ("totals.<side>: a key other than r h e", "totals-unknown-key", "error", "totals.away.hr"),
    ("totals.<side>.r missing", "r-missing", "error", "totals.away.r"),
    ("totals.<side>.r not a number", "r-not-a-number", "error", "totals.away.r"),
    ("totals.<side>.r not the sum of the runs", "r-wrong", "error", "totals.home.r"),
    ("h missing when team_hits is kept and no lines", "h-missing", "error", "totals.away.h"),
    ("h missing, in a draft", "h-missing-draft", "warning", "totals.away.h"),
    ("h set when team_hits is none and no lines", "h-when-none", "error", "totals.away.h"),
    ("h not the sum of the batting lines' H", "h-not-lines", "error", "totals.away.h"),
    ("h not a whole number from 0 to 99", "h-not-a-number", "error", "totals.home.h"),
    ("e missing when team_errors is kept", "e-kept-missing", "error", "totals.away.e"),
    ("e set when team_errors is none", "e-when-none", "error", "totals.away.e"),
    ("e not a whole number from 0 to 99", "e-bad", "error", "totals.away.e"),
    ("batting missing", "batting-missing", "error", "batting"),
    ("batting missing, in a draft", "batting-missing-draft", "warning", "batting"),
    ("batting.<side> missing", "batting-side-missing", "error", "batting.home"),
    ("batting set when batting is none", "batting-none-but-rows", "error", "batting"),
    ("batting not a block", "batting-not-a-block", "error", "batting"),
    ("batting: an unknown side", "batting-unknown-side", "error", "batting.zzz"),
    ("batting.<side> not a list", "batting-side-not-a-list", "error", "batting.home"),
    ("batting.<side> an empty list", "batting-empty-list", "error", "batting.home"),
    ("batting.<side> more than 30 rows", "batting-too-many", "error", "batting.home"),
    ("batting.<side>.<i> not a row", "batting-row-not-a-block", "error", "batting.home.2"),
    ("batting.<side>.<i> an unknown key", "batting-unknown-key", "error", "batting.home.2.sac"),
    ("player missing (a name only), final file", "name-in-final", "error", "batting.away.9.player"),
    ("player missing (a name only), draft", "draft-with-name", "warning", "batting.away.9.player"),
    ("player not in players.yml", "player-unknown", "error", "batting.home.3.player"),
    ("player listed twice", "player-twice", "error", "batting.home.3.player"),
    ("player on another team and not a spare", "spare-other-team", "warning", "batting.away.9.player"),
    ("a line key when batting is order", "order-with-line", "error", "batting.home.0.ab"),
    ("a row with no line when batting is every_game", "every-game-missing-line", "error", "batting.home.4"),
    ("optional: some rows with a line and some without", "optional-mixed-rows", "error", "batting.home.4"),
    ("optional: one side with lines and the other without", "optional-one-side", "warning", "batting.home"),
    ("a line value not a whole number from 0 to 20", "line-value-bad", "error", "batting.away.0.ab"),
    ("a line value written as text", "line-value-text", "error", "batting.away.0.h"),
    ("a line key left out", "line-key-missing", "error", "batting.away.0.bb"),
    ("a line key left out, in a draft", "line-key-missing-draft", "warning", "batting.away.0.bb"),
    ("h more than ab", "h-over-ab", "error", "batting.away.0.h"),
    ("hr more than h", "hr-over-h", "error", "batting.away.0.hr"),
    ("PA more than the innings batted + 2", "pa-too-many", "warning", "batting.away.0.ab"),
    ("the side's R column not equal to its runs", "r-column-wrong", "error", "batting.away"),
    ("the side's RBI more than its runs", "rbi-over-runs", "warning", "batting.away"),
    ("a side's HR more than hr_limit", "hr-limit", "warning", "batting.home"),
    ("an empty box in a draft (a line value)", "draft-empty-boxes", "warning", "batting.away.0.ab"),
]


@pytest.mark.parametrize("what, name, level, at", ROWS, ids=[f"{i}-{r[0]}" for i, r in enumerate(ROWS)])
def test_every_row_of_the_checks_table_has_a_fixture(what, name, level, at):
    assert name in CASES, f"no fixture {name}.yml for: {what}"
    problems, _ = run(name)
    assert (level, at) in [(p["level"], p["at"]) for p in problems], (what, problems)


# ------------------------------------------------------------------ the cases that should be quiet, and the numbers they give

QUIET = ("clean", "tie", "walk-off", "limit-inning", "over-limit-finish-ok", "open-seventh", "run-limit-0",
         "called-mercy", "called-mercy-home-leads", "called-time", "called-time-top", "extra-innings-playoff",
         "extra-innings-regular-2", "bats-first-home", "h-none-quiet", "h-from-lines", "e-kept", "batting-none",
         "batting-order", "every-game-ok", "spare-sub")
WARNING_ONLY = ("number-where-x", "walk-off-too-many", "called-mercy-short-lead", "called-mercy-short-innings",
                "called-under-official", "optional-one-side", "pa-too-many", "rbi-over-runs", "hr-limit",
                "spare-other-team", "draft-with-name")


@pytest.mark.parametrize("name", QUIET)
def test_these_cases_have_no_problem_at_all(name):
    problems, reading = run(name)
    assert problems == []
    assert reading is not None


@pytest.mark.parametrize("name", WARNING_ONLY)
def test_these_cases_have_warnings_and_still_read(name):
    problems, reading = run(name)
    assert problems and all(p["level"] == "warning" for p in problems)
    assert reading is not None


def test_a_draft_with_empty_boxes_has_only_warnings_and_is_not_read():
    problems, reading = run("draft-empty-boxes")
    assert problems and all(p["level"] == "warning" for p in problems)
    assert reading is None


def lines_of(reading):
    return {ln["player"]: ln["counts"] for ln in reading["lines"]}


def test_the_clean_game_is_the_mockup_game():
    _, reading = run("clean")
    score, facts = reading["score"], reading["facts"]
    assert score["final"] == {"home": 14, "away": 11}
    assert score["periods"] == {"home": [1, 5, 0, 3, 5, 0, None], "away": [2, 0, 5, 1, 0, 3, 0]}
    assert score["extra"] == {} and score["decided_in"] == "regulation"
    assert score["final_at"] == {"home": "sheet.totals.home.r", "away": "sheet.totals.away.r"}
    assert facts["played"] == 7 and facts["bats_first"] == "away" and facts["bats_last"] == "home"
    assert facts["x_innings"] == {"home": [7], "away": []}
    assert facts["limit_innings"] == {"home": [2, 5], "away": [3]}
    assert facts["limited"] == [True] * 6 + [False]
    assert facts["called"] is None and facts["walk_off"] is False
    assert facts["totals"] == {"home": {"r": 14, "h": 18, "e": None}, "away": {"r": 11, "h": 15, "e": None}}
    assert [p["player"] for p in facts["hr_players"]["home"]] == ["ron-b", "dave-k"]
    assert [p["player"] for p in facts["hr_players"]["away"]] == ["phil-g"]
    assert [p["player"] for p in facts["h3_players"]["home"]] == ["gary-t", "ron-b"]
    assert [p["player"] for p in facts["h3_players"]["away"]] == ["norm-w"]
    assert reading["team_lines"] == {}


def test_every_batter_in_the_order_gets_a_game_and_a_line():
    _, reading = run("clean")
    lines = lines_of(reading)
    assert len(reading["lines"]) == 20
    assert lines["dave-k"] == {"ab": 3, "r": 2, "h": 2, "rbi": 4, "hr": 1, "bb": 0}
    assert {ln["group"] for ln in reading["lines"]} == {"player"}


def test_a_tie_is_level_and_nobody_walks_off():
    _, reading = run("tie")
    assert reading["score"]["final"] == {"home": 10, "away": 10} and reading["facts"]["walk_off"] is False


def test_a_walk_off_is_the_team_batting_last_taking_the_lead_in_its_last_half_inning():
    _, reading = run("walk-off")
    assert reading["facts"]["walk_off"] is True and reading["score"]["final"] == {"home": 10, "away": 9}
    assert reading["facts"]["x_innings"] == {"home": [], "away": []}
    _, reading = run("clean")
    assert reading["facts"]["walk_off"] is False       # Alpha led after the top of the 7th: X, not a walk-off


def test_extra_innings_are_in_extra_and_the_game_is_decided_in_overtime():
    _, reading = run("extra-innings-playoff")
    score = reading["score"]
    assert score["extra"] == {"home": [0, 3], "away": [0, 2]} and score["decided_in"] == "overtime"
    assert score["final"] == {"home": 12, "away": 11} and len(score["periods"]["home"]) == 7
    assert reading["facts"]["walk_off"] is True and reading["facts"]["played"] == 9
    assert reading["facts"]["limited"] == [True] * 6 + [False] * 3


def test_a_called_game_leaves_the_innings_it_never_reached_empty():
    _, reading = run("called-mercy")
    assert reading["score"]["periods"]["away"] == [3, 5, 5, 4, 5, None, None]
    assert reading["score"]["periods"]["home"] == [0, 1, 0, 2, 1, None, None]
    assert reading["facts"]["called"] == "mercy" and reading["facts"]["played"] == 5
    assert reading["score"]["final"] == {"home": 4, "away": 22}


def test_an_x_is_not_a_run_and_is_marked_in_the_facts():
    _, reading = run("called-time-top")
    assert reading["score"]["periods"]["home"][:6] == [3, 1, 2, 1, 1, None]
    assert reading["facts"]["x_innings"] == {"home": [6], "away": []}
    assert reading["score"]["final"] == {"home": 8, "away": 4}


def test_the_team_batting_first_after_a_coin_toss_is_the_home_team():
    _, reading = run("bats-first-home")
    facts = reading["facts"]
    assert facts["bats_first"] == "home" and facts["bats_last"] == "away"
    assert facts["x_innings"] == {"home": [], "away": [7]}
    assert reading["score"]["final"] == {"home": 7, "away": 9}


def test_the_open_innings_follow_the_option():
    _, reading = run("open-seventh")
    assert reading["facts"]["limited"] == [True] * 6 + [False]
    _, reading = run("run-limit-0")
    assert reading["facts"]["limited"] == [False] * 7 and reading["facts"]["limit_innings"] == {"home": [], "away": []}
    problems, reading = run("over-limit-finish-ok")
    assert reading["facts"]["limit_innings"]["home"] == [2, 5] and reading["facts"]["runs"]["home"][1] == 7


def test_the_h_of_a_side_without_an_h_box_is_the_sum_of_its_lines():
    _, reading = run("h-from-lines")
    assert reading["facts"]["totals"]["away"]["h"] == 15


def test_a_game_without_batting_lines_counts_games_played_only():
    _, reading = run("tie")
    assert len(reading["lines"]) == 20 and all(ln["counts"] == {} for ln in reading["lines"])
    assert reading["facts"]["has_lines"] == {"home": False, "away": False}
    _, reading = run("batting-order")
    assert all(ln["counts"] == {} for ln in reading["lines"]) and len(reading["lines"]) == 20


def test_batting_none_has_no_lines_at_all():
    _, reading = run("batting-none")
    assert reading["lines"] == [] and reading["facts"]["batting"] == {"home": [], "away": []}


def test_one_side_with_lines_and_one_without_each_read_as_they_are():
    _, reading = run("optional-one-side")
    assert reading["facts"]["has_lines"] == {"home": False, "away": True}
    assert lines_of(reading)["norm-w"]["h"] == 3 and lines_of(reading)["gary-t"] == {}


def test_a_spare_written_in_by_name_gets_no_game():
    _, reading = run("draft-with-name")
    assert len(reading["lines"]) == 19 and "jo-k" not in lines_of(reading)
    assert reading["facts"]["batting"]["away"][9] == {"player": None, "name": "Jo K.", "line": {
        "ab": 3, "r": 0, "h": 1, "rbi": 0, "hr": 0, "bb": 0}}


def test_a_spare_who_is_a_sub_is_a_batter_like_any_other():
    _, reading = run("spare-sub")
    assert lines_of(reading)["jo-k"]["h"] == 1


def test_errors_are_read_when_kept():
    _, reading = run("e-kept")
    assert reading["facts"]["totals"] == {"home": {"r": 14, "h": 18, "e": 1}, "away": {"r": 11, "h": 15, "e": 2}}


# ------------------------------------------------------------------ properties of check over every fixture

def get(node, parts):
    for part in parts:
        if isinstance(node, dict):
            node = next(v for k, v in node.items() if str(k) == part)
        else:
            node = node[int(part)]
    return node


def resolves(sheet, at):
    """The path leads to a node, or to a missing key whose parent exists (a block or a list)."""
    if at == "":
        return True
    parts = at.split(".")
    for cut in (len(parts), len(parts) - 1):
        try:
            node = get(sheet, parts[:cut])
        except (StopIteration, KeyError, IndexError, ValueError, TypeError):
            continue
        return cut == len(parts) or isinstance(node, (dict, list))
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
