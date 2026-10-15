"""The stub sport (sports/stub/, docs/stage-4-spec.md section 3.7): every row of the checks table with its
exact path and message, then read, present, derive, sample.py and the settings the league decides."""
import copy
import random
from dataclasses import replace

import pytest

from scripts.core.config import sport_decide_settings
from scripts.core.model import BLOCK_TYPES, Line, Player, Problem, Reading, SampleGame, Score, SportContext, Team
from scripts.core.problems import call_sport
from scripts.core.sports import SPORTS_ROOT, load_sport

SPORT, LOAD_PROBLEMS = load_sport("stub", SPORTS_ROOT, with_sample=True)

TEAMS = {"otters": Team("otters", "Otters", "OTT"), "ravens": Team("ravens", "Ravens", "RAV")}
PLAYERS = {p.id: p for p in (
    Player("ann-b", "Ann B.", "otters", "7"), Player("joe-k", "Joe K.", "otters"),
    Player("tom-w", "Tom W.", "ravens", "3"), Player("sam-p", "Sam P.", None, sub=True),
    Player("lou-d", "Lou D.", "ravens", "12"), Player("rex-x", "Rex X.", "badgers"))}


def make_ctx(overtime="none", periods=2, folder="games", game_type="regular"):
    return SportContext(sport=SPORT.spec, options={"periods": periods, "overtime": overtime}, teams=TEAMS,
                        players=PLAYERS, sides={"home": "otters", "away": "ravens"}, game_type=game_type,
                        folder=folder)


def good_sheet():
    """The sheet of spec 3.7 without overtime: 21-20."""
    return {"periods": {"home": [12, 9], "away": [11, 9]}, "final": {"home": 21, "away": 20},
            "players": {"home": [{"player": "ann-b", "pts": 9}, {"player": "joe-k"}],
                        "away": [{"player": "tom-w", "pts": 4}, {"player": "lou-d"}]}}


def overtime_sheet():
    """The example of spec 3.7: level after two halves (21-21), then 3-1 in overtime."""
    return {"periods": {"home": [12, 9], "away": [11, 10]}, "overtime": {"home": 3, "away": 1},
            "final": {"home": 24, "away": 22},
            "players": {"home": [{"player": "ann-b", "pts": 9}, {"player": "joe-k"}],
                        "away": [{"player": "tom-w", "pts": 4}, {"player": "lou-d"}]}}


def run_check(sheet, ctx=None):
    return call_sport("check", SPORT.rules.check, sheet, ctx or make_ctx())


def found(sheet, ctx=None):
    """{(level, at): message}"""
    return {(p.level, p.at): p.message for p in run_check(sheet, ctx)}


def only(sheet, ctx=None):
    """The one problem expected: (level, at, message)."""
    problems = run_check(sheet, ctx)
    assert len(problems) == 1, problems
    return problems[0].level, problems[0].at, problems[0].message


def with_change(base, *path, value):
    """A deep copy of `base` with the node at `path` replaced (or removed when value is the string "<del>")."""
    sheet = copy.deepcopy(base)
    node = sheet
    for key in path[:-1]:
        node = node[key]
    if value == "<del>":
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return sheet


# ------------------------------------------------------------------ the folder itself

def test_the_stub_folder_loads_cleanly():
    assert LOAD_PROBLEMS == [] and SPORT is not None
    assert SPORT.sample.LEAGUE_NAME == "Example Valley Stub League"
    assert [t[0] for t in SPORT.sample.TEAMS] == ["otters", "ravens", "badgers", "moose", "lynx"]
    assert (SPORT.folder / "README.md").is_file()


def test_the_settings_the_league_decides_have_readable_names():
    words = dict(sport_decide_settings(SPORT.spec))
    assert words == {"rules.overtime": "Overtime", "standings.forfeit": "Forfeit", "standings.tiebreakers": "Tiebreakers",
                     "stats.minimums.ppg_min_games": "Minimum games for the points per game leaders"}


def test_the_standings_points_rule_is_complete():
    assert SPORT.spec["standings"]["points"] == {"win": 2, "tie": 1, "loss": 0, "ot_win": 2, "ot_loss": 1}


# ------------------------------------------------------------------ check: the 3.7 table

def test_good_sheets_have_no_problems():
    assert run_check(good_sheet()) == []
    assert run_check(overtime_sheet(), make_ctx("overtime")) == []
    assert run_check(good_sheet(), make_ctx(game_type="playoff")) == []


def test_a_sheet_that_is_not_a_block():
    assert only("hello") == ("error", "", "The sheet must be a block with these lines: periods, overtime, final, players.")


def test_an_unknown_key_is_an_error_at_that_key():
    sheet = good_sheet()
    sheet["pts"] = 3
    level, at, message = only(sheet)
    assert (level, at) == ("error", "pts") and "'pts' is not a box on the stub sheet" in message


@pytest.mark.parametrize("sheet", [{}, {"periods": None, "final": None}])
def test_missing_periods_and_final_are_errors_at_the_missing_box(sheet):
    assert set(found(sheet)) == {("error", "periods"), ("error", "final")}


def test_a_missing_side_is_an_error_at_that_side():
    sheet = with_change(with_change(good_sheet(), "periods", "away", value="<del>"), "final", "home", value="<del>")
    assert set(found(sheet)) == {("error", "periods.away"), ("error", "final.home")}


def test_periods_must_be_a_list_of_exactly_the_right_length():
    base = good_sheet()
    level, at, message = only(with_change(base, "periods", "home", value=9))
    assert (level, at) == ("error", "periods.home") and "must be a list of 2 whole numbers" in message
    level, at, message = only(with_change(base, "periods", "home", value=[12, 9, 0]))
    assert (level, at) == ("error", "periods.home") and "exactly 2 numbers" in message and "has 3" in message
    assert only(with_change(base, "periods", "away", value=[]))[:2] == ("error", "periods.away")


def test_the_number_of_periods_follows_the_rules():
    sheet = {"periods": {"home": [5, 5, 5, 5], "away": [5, 5, 5, 5]}, "final": {"home": 20, "away": 20}}
    assert run_check(sheet, make_ctx(periods=4)) == []
    assert ("error", "periods.home") in found(sheet)     # two halves are expected by default


@pytest.mark.parametrize("bad", [-1, 100, 1.5, "9", True, [3]])
def test_a_period_must_be_a_whole_number_0_to_99(bad):
    level, at, message = only(with_change(good_sheet(), "periods", "away", 1, value=bad))
    assert (level, at) == ("error", "periods.away.1") and "must be a whole number from 0 to 99" in message


def test_the_period_name_follows_sport_yml():
    spec = copy.deepcopy(SPORT.spec)
    spec["words"]["period"] = {"one": "Quarter", "many": "Quarters", "short": "Q"}
    ctx = replace(make_ctx(), sport=spec)
    problems = run_check(with_change(good_sheet(), "final", "home", value=30), ctx)
    assert problems[0].message == "the Final box says 30, but the quarters add up to 21"


def test_overtime_is_an_error_when_the_rules_have_none():
    sheet = overtime_sheet()
    level, at, message = only(sheet, make_ctx("none"))
    assert (level, at) == ("error", "overtime") and "no overtime" in message


def test_overtime_is_an_error_when_regulation_was_not_tied():
    sheet = with_change(overtime_sheet(), "periods", "home", 1, value=5)       # 17-21
    sheet["final"] = {"home": 20, "away": 22}
    level, at, message = only(sheet, make_ctx("overtime"))
    assert (level, at) == ("error", "overtime") and "17-21" in message


def test_overtime_sides_must_be_whole_numbers_and_not_level():
    ctx = make_ctx("overtime")
    level, at, message = only(with_change(overtime_sheet(), "overtime", "home", value=2.5), ctx)
    assert (level, at) == ("error", "overtime.home") and "whole number" in message
    sheet = with_change(overtime_sheet(), "overtime", "away", value=3)
    sheet["final"] = {"home": 24, "away": 24}
    level, at, message = only(sheet, ctx)
    assert (level, at) == ("error", "overtime.home") and "still tied 3-3" in message
    assert ("error", "overtime.away") in found(with_change(overtime_sheet(), "overtime", "away", value="<del>"), ctx)


def test_final_box_missing_or_not_a_number():
    base = good_sheet()
    assert only(with_change(base, "final", "home", value="<del>"))[:2] == ("error", "final.home")
    level, at, message = only(with_change(base, "final", "away", value="20"))
    assert (level, at) == ("error", "final.away") and "must be a whole number" in message


def test_final_box_must_equal_the_halves():
    sheet = with_change(good_sheet(), "final", "home", value=24)
    assert only(sheet) == ("error", "final.home", "the Final box says 24, but the halves add up to 21")


def test_final_box_counts_overtime():
    sheet = with_change(overtime_sheet(), "final", "away", value=23)
    assert only(sheet, make_ctx("overtime")) == (
        "error", "final.away", "the Final box says 23, but the halves and overtime add up to 22")


def test_a_player_must_be_in_players_yml_and_listed_once():
    base = good_sheet()
    level, at, message = only(with_change(base, "players", "home", 1, "player", value="zed-q"))
    assert (level, at) == ("error", "players.home.1.player") and "'zed-q' is not a player id in players.yml" in message
    twice = with_change(base, "players", "away", 1, "player", value="tom-w")
    level, at, message = only(twice)
    assert (level, at) == ("error", "players.away.1.player") and "listed twice" in message and "players.away.0.player" in message


def test_a_player_of_another_team_is_a_warning_unless_a_sub():
    base = with_change(good_sheet(), "players", "away", value=[{"player": "lou-d"}, {"player": "sam-p"}])
    assert run_check(base) == []                                      # lou-d is on the away team; sam-p is a sub
    level, at, message = only(with_change(base, "players", "away", 0, "player", value="rex-x"))
    assert (level, at) == ("warning", "players.away.0.player") and "Rex X." in message


def test_a_players_points_must_be_a_whole_number():
    level, at, message = only(with_change(good_sheet(), "players", "home", 0, "pts", value=-2))
    assert (level, at) == ("error", "players.home.0.pts") and "whole number" in message


def test_row_shapes_and_unknown_row_keys():
    base = good_sheet()
    assert only(with_change(base, "players", "home", 0, value="ann-b"))[:2] == ("error", "players.home.0")
    assert only(with_change(base, "players", "home", value="ann-b"))[:2] == ("error", "players.home")
    assert only(with_change(base, "players", "home", 0, "points", value=3))[:2] == ("error", "players.home.0.points")
    assert only(with_change(base, "players", "home", 1, "player", value="<del>"))[:2] == ("error", "players.home.1.player")


def test_players_points_that_do_not_add_up_are_a_warning():
    rows = [{"player": "ann-b", "pts": 9}, {"player": "joe-k", "pts": 10}]
    level, at, message = only(with_change(good_sheet(), "players", "home", value=rows))
    assert (level, at) == ("warning", "players.home")
    assert message == "the players' points add up to 19, but the Final box says 21"
    rows[1]["pts"] = 12
    assert run_check(with_change(good_sheet(), "players", "home", value=rows)) == []
    del rows[1]["pts"]                            # a row without pts: nothing to add up
    assert run_check(with_change(good_sheet(), "players", "home", value=rows)) == []


def test_players_are_optional_and_a_side_may_be_left_out():
    sheet = good_sheet()
    del sheet["players"]
    assert run_check(sheet) == []
    sheet["players"] = {"home": [{"player": "ann-b", "pts": 21}]}
    assert run_check(sheet) == []


def test_unknown_sides_in_a_block_are_errors():
    sheet = with_change(good_sheet(), "final", "both", value=3)
    assert only(sheet)[:2] == ("error", "final.both")


def test_a_draft_may_leave_boxes_empty():
    draft = make_ctx(folder="drafts")
    sheet = {"periods": {"home": [12, None], "away": [11, 9]}, "final": {"home": 21}}
    got = found(sheet, draft)
    assert set(got) == {("warning", "periods.home.1"), ("warning", "final.away")}
    assert {level for level, _ in found(sheet, make_ctx())} == {"error"}
    assert found({}, draft).keys() == {("warning", "periods"), ("warning", "final")}


def test_a_wrong_number_is_still_an_error_in_a_draft():
    draft = make_ctx(folder="drafts")
    assert found(with_change(good_sheet(), "final", "home", value=99), draft) == {
        ("error", "final.home"): "the Final box says 99, but the halves add up to 21"}


def test_check_changes_neither_the_sheet_nor_the_context():
    sheet, ctx = with_change(good_sheet(), "final", "home", value=1), make_ctx("overtime")
    sheet_before, ctx_before = copy.deepcopy(sheet), copy.deepcopy(ctx)
    run_check(sheet, ctx)
    assert sheet == sheet_before and ctx == ctx_before


# ------------------------------------------------------------------ read

def test_read_a_sheet_with_overtime():
    ctx = make_ctx("overtime")
    reading = call_sport("read", SPORT.rules.read, overtime_sheet(), ctx)
    assert isinstance(reading, Reading)
    assert reading.score == Score(final={"home": 24, "away": 22}, periods={"home": [12, 9], "away": [11, 10]},
                                  extra={"home": [3], "away": [1]}, decided_in="overtime",
                                  final_at={"home": "sheet.final.home", "away": "sheet.final.away"})
    assert reading.lines == [Line("home", "ann-b", "player", {"pts": 9}), Line("home", "joe-k", "player", {"pts": 0}),
                             Line("away", "tom-w", "player", {"pts": 4}), Line("away", "lou-d", "player", {"pts": 0})]
    assert reading.team_lines == {}


def test_read_a_sheet_without_overtime_or_players():
    sheet = good_sheet()
    del sheet["players"]
    reading = call_sport("read", SPORT.rules.read, sheet, make_ctx())
    assert reading.score.extra == {} and reading.score.decided_in == "regulation" and reading.lines == []


# ------------------------------------------------------------------ present

def present(sheet, ctx):
    reading = call_sport("read", SPORT.rules.read, sheet, ctx)
    return call_sport("present", SPORT.rules.present, reading, ctx)


def test_present_the_line_score():
    shown = present(overtime_sheet(), make_ctx("overtime"))
    line = shown["line_score"]
    assert (line["shape"], line["corner"], line["total_label"]) == ("periods", "Team", "Final")
    assert [c["label"] for c in line["columns"]] == ["H1", "H2", "OT"]
    home, away = line["rows"]["home"], line["rows"]["away"]
    assert home["cells"] == [{"v": 12, "won": True}, {"v": 9}, {"v": 3, "won": True}]      # H2: 9 v 10, away wins
    assert away["cells"] == [{"v": 11}, {"v": 10, "won": True}, {"v": 1}]
    assert (home["total"], away["total"]) == (24, 22)
    assert shown["tiles"] == []


def test_present_a_tied_period_marks_nobody():
    sheet = {"periods": {"home": [10, 5], "away": [10, 6]}, "final": {"home": 15, "away": 16}}
    cells = present(sheet, make_ctx())["line_score"]["rows"]
    assert cells["home"]["cells"] == [{"v": 10}, {"v": 5}] and cells["away"]["cells"] == [{"v": 10}, {"v": 6, "won": True}]


def test_present_the_card_names_the_top_scorer():
    card = present(good_sheet(), make_ctx())["card"]
    assert card == {"note": "Top: #7 Ann B. 9 pts", "strong": "#7 Ann B.", "link_label": "Box score"}


def test_present_the_card_without_points():
    sheet = good_sheet()
    del sheet["players"]
    assert present(sheet, make_ctx())["card"]["note"] is None
    sheet["players"] = {"home": [{"player": "ann-b"}]}
    assert present(sheet, make_ctx())["card"]["strong"] is None


def test_present_a_box_score_for_each_side_with_players_and_a_note():
    blocks = present(good_sheet(), make_ctx())["blocks"]
    assert [b["type"] for b in blocks] == ["stat_table", "stat_table", "note"]
    home = blocks[0]
    assert (home["side"], home["caption"]) == ("home", "Otters box score")
    assert home["columns"] == [{"key": "pts", "label": "PTS", "title": "Points", "key_col": True}]
    assert home["rows"] == [{"player": "ann-b", "cells": {"pts": "9"}}, {"player": "joe-k", "cells": {"pts": "0"}}]
    assert home["totals"] == {"label": "Team · 2 played", "cells": {"pts": "21"}}
    assert blocks[1]["caption"] == "Ravens box score"
    sheet = good_sheet()
    del sheet["players"]["away"]
    assert [b["type"] for b in present(sheet, make_ctx())["blocks"]] == ["stat_table", "note"]
    assert all(b["type"] in BLOCK_TYPES for b in blocks)


def test_present_changes_neither_the_reading_nor_the_context():
    ctx = make_ctx("overtime")
    reading = call_sport("read", SPORT.rules.read, overtime_sheet(), ctx)
    before, ctx_before = copy.deepcopy(reading), copy.deepcopy(ctx)
    SPORT.rules.present(reading, ctx)
    assert reading == before and ctx == ctx_before


# ------------------------------------------------------------------ derive

@pytest.mark.parametrize("counts, ppg", [
    ({"gp": 4, "pts": 29}, 7.3),          # 7.25 rounds half up, not to even
    ({"gp": 3, "pts": 10}, 3.3),
    ({"gp": 1, "pts": 0}, 0.0),
    ({"gp": 8, "pts": 66}, 8.3),          # 8.25
    ({"gp": 0, "pts": 0}, None),
    ({"pts": 5}, None),
])
def test_derive_points_per_game(counts, ppg):
    before = dict(counts)
    assert call_sport("derive", SPORT.rules.derive, counts, "player") == {"ppg": ppg}
    assert counts == before


# ------------------------------------------------------------------ sample.py

@pytest.mark.parametrize("overtime", ["none", "overtime"])
@pytest.mark.parametrize("outcome", ["win_home", "win_away", "tie", "ot"])
@pytest.mark.parametrize("game_type", ["regular", "playoff"])
def test_sample_sheets_pass_the_checks_whatever_is_asked(overtime, outcome, game_type):
    ctx = make_ctx(overtime, game_type=game_type)
    game = SampleGame("2026-11-05-1", {"home": ["ann-b", "joe-k"], "away": ["tom-w"]}, outcome)
    for seed in range(20):
        sheet = SPORT.sample.sheet(random.Random(seed), game, ctx)
        assert run_check(sheet, ctx) == [], (seed, sheet)
        final = sheet["final"]
        if game_type == "playoff" or overtime == "overtime" or outcome in ("win_home", "win_away"):
            assert final["home"] != final["away"]
        if outcome == "win_home":
            assert final["home"] > final["away"]
        if outcome == "win_away":
            assert final["away"] > final["home"]


def test_sample_ties_and_overtime_follow_the_rules():
    game = SampleGame("g", {"home": ["ann-b"], "away": ["tom-w"]}, "tie")
    tie = SPORT.sample.sheet(random.Random(1), game, make_ctx())
    assert "overtime" not in tie and tie["final"]["home"] == tie["final"]["away"]
    ot = SPORT.sample.sheet(random.Random(1), game, make_ctx("overtime"))
    assert "overtime" in ot and ot["final"]["home"] != ot["final"]["away"]


def test_sample_player_points_add_up_and_nobody_is_listed_for_an_empty_side():
    game = SampleGame("g", {"home": ["ann-b", "joe-k"], "away": []}, "win_home")
    sheet = SPORT.sample.sheet(random.Random(5), game, make_ctx())
    assert sum(r["pts"] for r in sheet["players"]["home"]) == sheet["final"]["home"]
    assert "away" not in sheet["players"]


def test_sample_is_the_same_every_time():
    game = SampleGame("g", {"home": ["ann-b", "joe-k"], "away": ["tom-w"]}, "ot")
    ctx = make_ctx("overtime")
    assert SPORT.sample.sheet(random.Random(9), game, ctx) == SPORT.sample.sheet(random.Random(9), game, ctx)


def test_the_sample_season_has_a_tie_or_an_overtime_game_and_playoffs_never_tie():
    from scripts import make_sample
    from scripts.core.problems import parse_yaml
    for overtime in ("none", "overtime"):
        files = make_sample.generate_season(
            SPORT, {"id": "sample-2026-27", "as_of": "2026-11-20"}, rules={"periods": 2, "overtime": overtime},
            standings={"ties": True})
        games = [parse_yaml(text) for name, text in files.items() if name.startswith("games/") and "forfeit" not in text]
        assert any(g["sheet"]["final"]["home"] == g["sheet"]["final"]["away"] for g in games) == (overtime == "none")
        assert any("overtime" in g["sheet"] for g in games) == (overtime == "overtime")
    files = make_sample.generate_season(
        SPORT, {"id": "sample-2025-26"}, rules={"periods": 2, "overtime": "none"}, standings={"ties": True})
    playoff_days = {"2025-12-04", "2025-12-11"}
    for name, text in files.items():
        if name[len("games/"):len("games/") + 10] in playoff_days:
            final = parse_yaml(text)["sheet"]["final"]
            assert final["home"] != final["away"]


def test_the_sample_season_has_no_tie_when_the_standings_do_not_allow_one():
    from scripts import make_sample
    from scripts.core.problems import parse_yaml
    files = make_sample.generate_season(
        SPORT, {"id": "sample-2026-27", "as_of": "2026-11-20"}, rules={"periods": 2, "overtime": "none"},
        standings={"ties": False})
    for name, text in files.items():
        if name.startswith("games/") and "forfeit" not in text:
            final = parse_yaml(text)["sheet"]["final"]
            assert final["home"] != final["away"]
