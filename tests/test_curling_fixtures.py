"""The curling fixtures (sports/curling/fixtures/, docs/stage-5-curling-spec.md section 8): one game file per case,
the problems `check` must report (level, path, message, in order) and the numbers `read` must give.

Each case is `<name>.yml` (`fixture: {folder, game_type, options}` and `sheet:`) with `<name>.expected.json`
(`problems`, and `reading`: null when there is an error or a draft leaves out a box, else score, lines, team lines
and facts). `context.yml` holds the rinks, the players and the league settings they are checked with. The stage 7
JavaScript rules are tested against the same files. `UPDATE_FIXTURES=1 python -m pytest tests/test_curling_fixtures.py`
rewrites the expected files; read the diff before committing it.
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

FIXTURES = Path(__file__).resolve().parent.parent / "sports" / "curling" / "fixtures"
CASES = sorted(p.name[:-len(".yml")] for p in FIXTURES.glob("*.yml") if p.name != "context.yml")
UPDATE = bool(os.environ.get("UPDATE_FIXTURES"))

SPORT, LOAD_PROBLEMS = load_sport("curling", SPORTS_ROOT)


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
    its only errors are lineup rows with no player id yet (a spare written in by name)."""
    if any(p.level == "error" for p in SPORT.rules.check(sheet, ctx)):
        return False
    final = [p for p in SPORT.rules.check(sheet, replace(ctx, folder="games")) if p.level == "error"]
    return all(p.at.startswith("lineups.") and p.at.endswith(".player") for p in final)


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


# ------------------------------------------------------------------ every row of the spec's table 3.1

# (what the row checks, the case, level, path): the case's expected problems must hold that level and path.
ROWS = [
    ("a key other than hammer ends extra conceded time_called final lineups", "unknown-keys", "error", "draw"),
    ("the sheet is not a block", "sheet-not-a-block", "error", ""),
    ("hammer missing", "no-hammer", "error", "hammer"),
    ("hammer missing, in a draft", "no-hammer-draft", "warning", "hammer"),
    ("hammer not home or away", "hammer-text", "error", "hammer"),
    ("ends missing", "no-ends", "error", "ends"),
    ("ends missing, in a draft", "no-ends-draft", "warning", "ends"),
    ("ends not a block", "ends-not-a-block", "error", "ends"),
    ("ends: only one side", "ends-one-side", "error", "ends.away"),
    ("ends: an unknown side", "ends-unknown-side", "error", "ends.zzz"),
    ("ends.<side> not a list", "ends-not-a-list", "error", "ends.home"),
    ("ends.<side> not exactly rules.ends boxes", "wrong-number-of-ends", "error", "ends.home"),
    ("ends.<side>.<i> empty", "empty-end-box", "error", "ends.home.3"),
    ("ends.<side>.<i> empty, in a draft", "empty-end-box-draft", "warning", "ends.home.3"),
    ("ends.<side>.<i> not 0 to 8", "nine-on-an-end", "error", "ends.home.1"),
    ("ends.<side>.<i> text", "end-text", "error", "ends.home.2"),
    ("ends.<side>.<i> a lower-case x", "lowercase-x", "error", "ends.home.6"),
    ("ends.<side>.<i> is 8", "eight-ender", "warning", "ends.home.2"),
    ("ends.<side>.<i> is 7", "seven-ender", "warning", "ends.home.4"),
    ("both rinks scored in one end", "both-scored", "error", "ends.home.2"),
    ("X for one rink and a number for the other", "x-on-one-side", "error", "ends.home.6"),
    ("a number after an X", "number-after-x", "error", "ends.home.7"),
    ("ends.home.0 is X", "first-end-x", "error", "ends.home.0"),
    ("the first X with neither conceded nor time_called", "x-without-reason", "error", "ends.home.6"),
    ("conceded not home or away", "conceded-text", "error", "conceded"),
    ("conceded although every end was played", "conceded-all-played", "error", "conceded"),
    ("conceded together with time_called", "conceded-and-time", "error", "conceded"),
    ("conceded by the rink that was ahead", "conceded-while-ahead", "error", "conceded"),
    ("conceded by a rink that was level", "conceded-while-level", "error", "conceded"),
    ("time_called not true", "time-called-false", "error", "time_called"),
    ("extra not a block", "extra-not-a-block", "error", "extra"),
    ("extra: an unknown side", "extra-unknown-side", "error", "extra.zzz"),
    ("extra.<side> not a list", "extra-side-not-a-list", "error", "extra.home"),
    ("extra.<side> lists of different lengths", "extra-lengths-differ", "error", "extra.away"),
    ("extra.<side>.<i> not 0 to 8", "extra-bad-box", "error", "extra.home.0"),
    ("extra.<side>.<i> is X", "extra-end-x", "error", "extra.home.0"),
    ("extra.<side>.<i> empty, in a draft", "extra-empty-box-draft", "warning", "extra.home.0"),
    ("extra although the game was not level after the last end", "extra-end-not-level", "error", "extra"),
    ("extra although the game stopped early", "extra-after-concession", "error", "extra"),
    ("extra in a regular-season game when extra_end is playoffs", "extra-end-regular-when-playoffs", "error", "extra"),
    ("both rinks scored in an extra end", "extra-both-scored", "error", "extra.home.0"),
    ("an extra end after the one that broke the tie", "extra-after-the-end", "error", "extra.home.1"),
    ("the last extra end blank", "extra-end-blank-last", "error", "extra.home.0"),
    ("extra missing, level playoff game", "level-playoff-no-extra", "error", "extra"),
    ("extra missing, level game when extra_end is always", "level-always-no-extra", "error", "extra"),
    ("extra written as empty lists, level playoff game", "extra-empty-lists", "error", "extra"),
    ("final missing", "no-final", "error", "final"),
    ("final missing, in a draft", "no-final-draft", "warning", "final"),
    ("final not a block", "final-not-a-block", "error", "final"),
    ("final: an unknown key", "final-unknown-key", "error", "final.third"),
    ("final.<side> missing", "final-one-side", "error", "final.away"),
    ("final.<side> not a whole number", "final-not-a-number", "error", "final.home"),
    ("final.<side> not the ends", "bad-total", "error", "final.away"),
    ("final.<side> not the ends plus the extra ends", "bad-total-with-extra", "error", "final.home"),
    ("lineups filled in when rules.lineups is none", "lineups-when-none", "error", "lineups"),
    ("lineups missing", "no-lineups", "error", "lineups"),
    ("lineups missing, in a draft", "no-lineups-draft", "warning", "lineups"),
    ("lineups not a block", "lineups-not-a-block", "error", "lineups"),
    ("lineups: an unknown side", "lineups-unknown-side", "error", "lineups.zzz"),
    ("lineups.<side> missing", "lineups-one-side", "error", "lineups.away"),
    ("lineups.<side> not a list", "lineup-side-not-a-list", "error", "lineups.home"),
    ("lineups.<side> five rows", "lineup-five", "error", "lineups.home"),
    ("lineups.<side> two rows", "lineup-two", "error", "lineups.home"),
    ("lineups.<side>.<i> not a row", "lineup-row-not-a-block", "error", "lineups.home.0"),
    ("lineups.<side>.<i> an unknown key", "lineup-unknown-key", "error", "lineups.home.0.num"),
    ("position missing", "position-missing", "error", "lineups.home.0.position"),
    ("position not lead second vice skip", "unknown-position", "error", "lineups.home.0.position"),
    ("the same position twice", "two-skips", "error", "lineups.home.3.position"),
    ("a rink with no skip", "no-skip", "error", "lineups.home"),
    ("player missing (a name only), final file", "name-in-final", "error", "lineups.away.1.player"),
    ("player missing (a name only), draft", "draft-with-name", "warning", "lineups.away.1.player"),
    ("player not in players.yml", "unknown-player", "error", "lineups.home.0.player"),
    ("player listed twice", "player-twice", "error", "lineups.home.1.player"),
    ("player on another team, not a spare, no spare_for", "other-team-no-spare", "warning", "lineups.away.1.player"),
    ("spare_for not in players.yml", "spare-for-unknown", "error", "lineups.away.1.spare_for"),
    ("spare_for not a player of this rink", "spare-for-other-rink", "error", "lineups.away.1.spare_for"),
    ("spare_for also in this lineup", "spare-for-in-lineup", "error", "lineups.away.1.spare_for"),
    ("spare_for on a regular of this rink", "spare-for-regular", "warning", "lineups.away.0.spare_for"),
]


@pytest.mark.parametrize("what, name, level, at", ROWS, ids=[r[0] for r in ROWS])
def test_every_row_of_the_checks_table_has_a_fixture(what, name, level, at):
    assert name in CASES, f"no fixture {name}.yml for: {what}"
    problems, _ = run(name)
    assert (level, at) in [(p["level"], p["at"]) for p in problems], (what, problems)


# ------------------------------------------------------------------ the cases that should be quiet, and the numbers they give

QUIET = ("clean", "clean-6-ends", "clean-10-ends", "blank-first-end", "steals-and-big-end", "all-blank", "tie-regular-season",
         "three-player-rink", "lineups-none", "conceded", "time-called", "time-called-tie", "time-called-tie-playoff",
         "time-called-after-last-end", "extra-end-playoff", "extra-end-always", "two-extra-ends", "extra-blank-time-called",
         "spare-from-other-team")
WARNING_ONLY = ("eight-ender", "seven-ender", "draft-with-name", "other-team-no-spare", "spare-for-regular")


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


def test_a_spare_gets_the_game_and_the_regular_they_replaced_does_not():
    _, reading = run("clean")
    players = {ln["player"] for ln in reading["lines"]}
    assert "ron-m" in players and "brian-s" not in players
    assert all(ln["counts"] == {} and ln["group"] == "player" for ln in reading["lines"])
    assert len(reading["lines"]) == 8
    assert reading["facts"]["lineups"]["away"][1] == {"player": "ron-m", "position": "second", "spare_for": "brian-s"}


def test_a_spare_written_in_by_name_gets_no_line():
    _, reading = run("draft-with-name")
    assert len([ln for ln in reading["lines"] if ln["side"] == "away"]) == 3
    assert [r["position"] for r in reading["facts"]["lineups"]["away"]] == ["lead", "vice", "skip"]


def test_a_three_player_rink_has_three_lines():
    _, reading = run("three-player-rink")
    assert len([ln for ln in reading["lines"] if ln["side"] == "home"]) == 3


def test_a_league_with_no_lineups_has_no_lines():
    _, reading = run("lineups-none")
    assert reading["lines"] == [] and reading["facts"]["lineups"] == {"home": [], "away": []}


def test_the_clean_game_is_the_mockup_game():
    _, reading = run("clean")
    score = reading["score"]
    assert score["final"] == {"home": 7, "away": 5}
    assert score["periods"] == {"home": [0, 0, 1, 1, 0, 3, 0, 2], "away": [0, 2, 0, 0, 1, 0, 2, 0]}
    assert score["extra"] == {} and score["decided_in"] == "regulation"
    assert reading["facts"]["hammer_by_end"] == ["away", "away", "home", "away", "away", "home", "away", "home"]
    assert reading["facts"]["stopped"] is None and reading["facts"]["ends"] == 8
    assert reading["team_lines"]["home"] == {"ends_won": 4, "stolen": 1, "blanks": 0, "big_ends": 1, "hammer_ends": 3,
                                             "hammer_scored": 3, "ends": 8}
    assert reading["team_lines"]["away"] == {"ends_won": 3, "stolen": 0, "blanks": 1, "big_ends": 0, "hammer_ends": 5,
                                             "hammer_scored": 3, "ends": 8}


def test_final_at_names_each_total_box_from_the_top_of_the_file():
    _, reading = run("clean")
    assert reading["score"]["final_at"] == {"home": "sheet.final.home", "away": "sheet.final.away"}


def test_a_concession_is_a_regulation_result_with_x_for_the_ends_left():
    _, reading = run("conceded")
    score = reading["score"]
    assert score["periods"]["home"][-2:] == [None, None] and score["periods"]["away"][-2:] == [None, None]
    assert score["final"] == {"home": 8, "away": 3} and score["decided_in"] == "regulation"
    assert reading["facts"]["stopped"] == {"by": "conceded", "side": "away", "after": 6}
    assert len(reading["facts"]["hammer_by_end"]) == 6
    assert reading["team_lines"]["home"]["ends"] == 6


def test_time_called_is_a_stop_with_no_conceding_rink():
    _, reading = run("time-called")
    assert reading["facts"]["stopped"] == {"by": "time", "side": None, "after": 7}
    _, reading = run("time-called-after-last-end")
    assert reading["facts"]["stopped"] == {"by": "time", "side": None, "after": 8}


def test_an_extra_end_is_decided_in_overtime_and_counts_in_the_totals():
    _, reading = run("extra-end-playoff")
    score = reading["score"]
    assert score["decided_in"] == "overtime" and score["extra"] == {"home": [1], "away": [0]}
    assert score["final"] == {"home": 5, "away": 4}
    assert score["periods"]["home"] == [1, 0, 2, 0, 0, 1, 0, 0]
    assert len(reading["facts"]["hammer_by_end"]) == 9
    assert reading["team_lines"]["home"]["ends"] == 9 and reading["team_lines"]["home"]["ends_won"] == 4


def test_a_blank_extra_end_keeps_the_hammer():
    _, reading = run("two-extra-ends")
    assert reading["score"]["extra"] == {"home": [0, 1], "away": [0, 0]}
    hammer = reading["facts"]["hammer_by_end"]
    assert len(hammer) == 10 and hammer[8] == hammer[9]


def test_a_scoreless_game_leaves_the_hammer_with_one_rink():
    _, reading = run("all-blank")
    assert reading["facts"]["hammer_by_end"] == ["home"] * 8
    assert reading["team_lines"]["home"]["blanks"] == 8 and reading["team_lines"]["away"]["blanks"] == 0
    assert reading["team_lines"]["home"]["hammer_ends"] == 8 and reading["team_lines"]["away"]["hammer_ends"] == 0
    assert reading["score"]["final"] == {"home": 0, "away": 0}


def test_steals_and_big_ends_are_counted():
    _, reading = run("steals-and-big-end")
    assert reading["team_lines"]["away"]["stolen"] == 2 and reading["team_lines"]["home"]["stolen"] == 0
    assert reading["team_lines"]["home"]["big_ends"] == 2       # the 4 and the 3
    assert reading["team_lines"]["away"]["big_ends"] == 0


def test_the_number_of_ends_is_the_leagues():
    _, six = run("clean-6-ends")
    _, ten = run("clean-10-ends")
    assert len(six["score"]["periods"]["home"]) == 6 and six["facts"]["ends"] == 6
    assert len(ten["score"]["periods"]["home"]) == 10 and ten["facts"]["ends"] == 10


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
