"""The slo-pitch sport (sports/slopitch/, docs/stage-5-slopitch-spec.md): sport.yml, `read` and `present` on the fixture
games (the approved Slopitch-Game mockup's numbers), `derive`, the standings it asks of the core, and `check` on broken
sheets. The checks themselves are in test_slopitch_fixtures.py. The sample generator (`sample.py`) is package 5's: its
season-level tests (a mercy-rule game, a walk-off, an extra-inning playoff game, limit innings and a game with no batting
lines over a season, every outcome under every option value) join this file with it, and test_sport_contract.py runs the
sample once it exists."""
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.core.config import normalise_standings, sport_decide_settings, sport_standings_defaults
from scripts.core.model import BLOCK_TYPES, CELL_FLAGS, Player, SportContext, Team
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, load_sport, when_matches
from scripts.core.standings import StandingsGame, compute_standings, game_results

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "sports" / "slopitch" / "fixtures"
README = ROOT / "sports" / "slopitch" / "README.md"

SPORT, LOAD_PROBLEMS = load_sport("slopitch", SPORTS_ROOT)
_CONTEXT = parse_yaml((FIXTURES / "context.yml").read_text(encoding="utf-8"))
TEAMS = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in _CONTEXT["teams"]}
PLAYERS = {p["id"]: Player(p["id"], p["name"], p["team"], p.get("number"), p.get("sub", False), p.get("position"))
           for p in _CONTEXT["players"]}


def make_ctx(folder="games", game_type="regular", **options):
    opts = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | options
    return SportContext(sport=SPORT.spec, options=opts, teams=TEAMS, players=PLAYERS, sides={"home": "aa", "away": "bb"},
                        game_type=game_type, folder=folder)


def case_of(name):
    return parse_yaml((FIXTURES / f"{name}.yml").read_text(encoding="utf-8"))


def fixture_sheet(name):
    return case_of(name)["sheet"]


def ctx_of(name, **options):
    fixture = case_of(name)["fixture"]
    return make_ctx(folder=fixture["folder"], game_type=fixture["game_type"], **{**fixture["options"], **options})


def reading_of(name, **options):
    ctx, sheet = ctx_of(name, **options), fixture_sheet(name)
    assert not [p for p in SPORT.rules.check(sheet, ctx) if p.level == "error"]
    return SPORT.rules.read(sheet, ctx)


def shown(name, **options):
    ctx = ctx_of(name, **options)
    return call_sport("present", SPORT.rules.present, reading_of(name, **options), ctx)


def block_of(result, kind, title=None):
    found = [b for b in result["blocks"] if b["type"] == kind and (title is None or b["title"] == title)]
    assert len(found) == 1, (kind, [b["type"] for b in result["blocks"]])
    return found[0]


def cells(line, side):
    return [c.get("v") for c in line["rows"][side]["cells"]]


# ------------------------------------------------------------------ sport.yml

def test_the_sport_folder_loads_without_a_problem():
    assert not LOAD_PROBLEMS, LOAD_PROBLEMS
    assert SPORT.name == "Slo-pitch" and SPORT.spec["default_layout"] == "slopitch"
    assert README.read_text(encoding="utf-8").strip()


def test_the_sport_knows_no_real_league():
    for name in ("sport.yml", "rules.py", "README.md"):
        text = (SPORT.folder / name).read_text(encoding="utf-8")
        assert "Masters" not in text and "Thunder Bay" not in text, name
    for path in FIXTURES.glob("*"):
        assert "Masters" not in path.read_text(encoding="utf-8"), path.name


def test_the_blurb_fits_the_landing_card():
    blurb = SPORT.spec["blurb"]
    assert 0 < len(blurb) <= 100 and "\n" not in blurb


def test_innings_the_words_and_the_display_hints():
    spec = SPORT.spec
    assert spec["line_score"] == {"shape": "innings", "total_label": "R", "corner": "Inning", "periods": "innings"}
    assert spec["words"]["period"] == {"one": "Inning", "many": "Innings", "short": "Inn"}
    assert spec["words"]["day"] == "Week" and spec["words"]["surface"] == "Diamond"
    assert spec["words"]["extra"] == {"one": "Extra inning", "short": "Extras"}
    assert spec["words"]["points_for"]["label"] == "RF" and spec["words"]["points_against"]["label"] == "RA"
    assert spec["game_minutes"] == 75 and spec["games_per_day"] == 2 and spec["positions"] == []
    display = spec["display"]
    assert (display["card"], display["card_foot"], display["surface"]) == ("lines", "note", "label")
    assert (display["card_head"], display["matchup"]) == ("status_surface", "at")
    assert display["results_legend"] == [
        {"kind": "limit", "mark_option": "run_limit", "text": "Inning ended at the run limit."},
        {"kind": "x", "text": "Not needed."}]
    assert spec["labels_by_layout"]["scoreboard"] == {"leaders": "Hitting", "next": "Next up"}


def test_the_options_and_everything_the_league_decides():
    options = SPORT.spec["options"]
    assert {k: o["default"] for k, o in options.items()} == {
        "innings": 7, "run_limit": 5, "open_innings": "last", "limit_play": "stop", "mercy_runs": 15, "mercy_after": 5,
        "official_innings": 4, "time_limit": 60, "extra_innings": 0, "hr_limit": 0, "batting": "optional",
        "team_hits": "kept", "team_errors": "none"}
    assert options["open_innings"]["values"] == ["last", "none"] and options["limit_play"]["values"] == ["stop", "finish"]
    assert options["batting"]["values"] == ["none", "order", "optional", "every_game"]
    assert options["team_hits"]["values"] == ["kept", "none"] and options["team_errors"]["values"] == ["none", "kept"]
    assert (options["innings"]["min"], options["innings"]["max"]) == (3, 9)
    assert (options["run_limit"]["min"], options["run_limit"]["max"]) == (0, 20)
    assert (options["mercy_runs"]["min"], options["mercy_runs"]["max"]) == (0, 30)
    assert (options["mercy_after"]["min"], options["mercy_after"]["max"]) == (1, 9)
    assert (options["official_innings"]["min"], options["official_innings"]["max"]) == (1, 9)
    assert (options["time_limit"]["min"], options["time_limit"]["max"]) == (0, 180)
    assert (options["extra_innings"]["min"], options["extra_innings"]["max"]) == (0, 5)
    assert (options["hr_limit"]["min"], options["hr_limit"]["max"]) == (0, 10)
    assert all("decide" not in options[k] for k in ("batting", "team_hits", "team_errors"))
    decided = dict(sport_decide_settings(SPORT.spec))
    assert set(decided) == {"rules.innings", "rules.run_limit", "rules.open_innings", "rules.limit_play",
                            "rules.mercy_runs", "rules.mercy_after", "rules.official_innings", "rules.time_limit",
                            "rules.extra_innings", "rules.hr_limit", "standings.ties", "standings.forfeit",
                            "standings.tiebreakers", "stats.minimums.avg_min_pa"}


def test_the_default_standings_are_the_typical_rec_rule():
    std = normalise_standings(sport_standings_defaults(SPORT.spec))
    assert std["rank_by"] == "points" and std["points"] == {"win": 2, "tie": 1, "loss": 0, "ot_win": 2, "ot_loss": 0}
    assert std["period_points"] == 0 and std["ties"] is True
    assert std["forfeit"] == {"score": [7, 0]}
    assert std["tiebreakers"] == ["head_to_head", {"diff": {"cap": 7}}]
    assert std["columns"] == ["gp", "w", "l", "t", "pts", "pf", "pa"]


def test_one_batting_group_shown_only_while_the_league_keeps_lines():
    stats = SPORT.spec["stats"]
    assert [s["key"] for s in stats["player"]] == ["ab", "r", "h", "rbi", "hr", "bb"]
    assert [s["key"] for s in stats["derived"]] == ["pa", "avg", "obp"] and stats["team"] == []
    assert stats["labels"] == {"player": "Batting"}
    assert (stats["derived"][1]["places"], stats["derived"][1]["format"]) == (3, "dot")
    assert stats["derived"][0]["places"] == 0
    shown_when = [*stats["player"], *stats["derived"], *SPORT.spec["leaderboards"]]
    assert all(item["when"] == {"batting": ["optional", "every_game"]} for item in shown_when)
    assert when_matches({"batting": ["optional", "every_game"]}, {"batting": "order"}) is False
    assert stats["columns"]["player"]["table"] == ["gp", "ab", "h", "avg", "hr", "rbi", "r", "bb"]
    assert stats["columns"]["player"]["totals"] == ["gp", "pa", "ab", "r", "h", "hr", "rbi", "bb", "avg", "obp"]
    assert stats["columns"]["player"]["log"] == ["ab", "r", "h", "rbi", "hr", "bb"]


def test_the_boards_and_the_minimum_per_team_game():
    boards = {b["id"]: b for b in SPORT.spec["leaderboards"]}
    assert list(boards) == ["avg", "hr", "rbi", "hits", "runs", "obp"]
    assert boards["avg"]["tile"] and boards["avg"]["edge"] == "hot" and boards["avg"]["zero"] is True
    assert boards["avg"]["min"] == {"stat": "pa", "setting": "avg_min_pa", "per_team_game": True}
    assert boards["obp"]["min"] == boards["avg"]["min"]
    assert boards["hr"]["tile"] and boards["hr"]["edge"] == "accent"
    assert [k for k, b in boards.items() if b.get("home", True)] == ["avg", "hr"]
    assert SPORT.spec["minimums"]["avg_min_pa"]["default"] == 2


# ------------------------------------------------------------------ derive

def test_pa_avg_and_obp_come_from_the_counts_and_are_none_without_a_denominator():
    derive = SPORT.rules.derive
    got = derive({"gp": 3, "ab": 12, "h": 5, "bb": 2, "r": 3, "rbi": 4, "hr": 1}, "player")
    assert got["pa"] == 14 and got["avg"] == 5 / 12 and got["obp"] == 7 / 14
    assert derive({"gp": 1, "ab": 0, "h": 0, "bb": 0}, "player") == {"pa": 0, "avg": None, "obp": None}
    assert derive({"gp": 1, "ab": 0, "h": 0, "bb": 2}, "player") == {"pa": 2, "avg": None, "obp": 1.0}
    assert derive({"gp": 2}, "player") == {"pa": 0, "avg": None, "obp": None}


# ------------------------------------------------------------------ present: the approved Slopitch-Game mockup

def test_present_returns_only_known_keys_blocks_and_flags():
    for name in ("clean", "tie", "walk-off", "called-mercy", "called-time-top", "extra-innings-playoff", "bats-first-home",
                 "batting-none", "batting-order", "optional-one-side", "limit-inning", "run-limit-0", "e-kept"):
        result = shown(name)
        assert set(result) == {"line_score", "card", "tiles", "blocks"}
        assert all(b["type"] in BLOCK_TYPES for b in result["blocks"])
        for line in (result["line_score"], result["card"]["line_score"]):
            for row in line["rows"].values():
                assert all(set(c) <= {"v", *CELL_FLAGS} for c in row["cells"]), name
                assert len(row["cells"]) == len(line["columns"])
        assert result["tiles"] is None


def test_the_line_score_is_the_mockup():
    line = shown("clean")["line_score"]
    assert (line["shape"], line["corner"], line["total_label"], line["title"]) == ("innings", "Inning", "R", "Line score")
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3", "4", "5", "6", "7"]
    assert [c.get("open") for c in line["columns"]] == [None] * 6 + [True]
    assert cells(line, "away") == [2, 0, 5, 1, 0, 3, 0] and line["rows"]["away"]["total"] == 11
    assert cells(line, "home") == [1, 5, 0, 3, 5, 0, None] and line["rows"]["home"]["total"] == 14
    assert [i for i, c in enumerate(line["rows"]["home"]["cells"]) if c.get("mark")] == [1, 4]
    assert [i for i, c in enumerate(line["rows"]["away"]["cells"]) if c.get("mark")] == [2]
    assert line["rows"]["home"]["cells"][6] == {"v": None, "void": True}
    assert line["mark_word"] == "run limit" and line["void_word"] == "not needed" and "first" not in line
    assert [c.get("void") for c in line["rows"]["away"]["cells"]] == [None] * 7


def test_the_h_column_is_on_by_default_and_the_e_column_follows_the_option():
    line = shown("clean")["line_score"]
    assert line["extras"] == [{"label": "H", "title": "Hits"}]
    assert line["rows"]["home"]["extras"] == [18] and line["rows"]["away"]["extras"] == [15]
    line = shown("e-kept", team_errors="kept")["line_score"]
    assert line["extras"] == [{"label": "H", "title": "Hits"}, {"label": "E", "title": "Errors"}]
    assert line["rows"]["home"]["extras"] == [18, 1] and line["rows"]["away"]["extras"] == [15, 2]
    line = shown("h-none-quiet", team_hits="none")["line_score"]
    assert line["extras"] == [] and line["rows"]["home"]["extras"] == []


def test_the_h_of_a_side_with_lines_comes_from_the_lines_when_the_box_is_empty():
    assert shown("h-from-lines")["line_score"]["rows"]["away"]["extras"] == [15]


def test_the_legend_is_two_stacked_keys_for_the_limit_and_the_x():
    line = shown("clean")["line_score"]
    assert line["legend_stack"] is True and line["legend"] == [
        {"kind": "limit", "mark": "5", "text": "Circled: the inning ended at the 5-run limit. The 7th is open (no limit)."},
        {"kind": "x", "mark": "X", "text": "Alpha led after the top of the 7th, so they didn't bat."}]
    assert shown("clean", run_limit=6)["line_score"]["legend"][0]["mark"] == "6"
    assert shown("tie")["line_score"]["legend"][0]["kind"] == "limit" and len(shown("tie")["line_score"]["legend"]) == 1
    assert [i["kind"] for i in shown("run-limit-0")["line_score"]["legend"]] == ["x"]


def test_extra_innings_are_more_columns_and_are_open():
    line = shown("extra-innings-playoff")["line_score"]
    assert [c["label"] for c in line["columns"]] == [str(i) for i in range(1, 10)]
    assert [c.get("open") for c in line["columns"]] == [None] * 6 + [True] * 3
    assert cells(line, "away") == [1, 0, 2, 0, 3, 1, 2, 0, 2] and cells(line, "home") == [0, 3, 1, 2, 0, 2, 1, 0, 3]
    assert line["rows"]["home"]["total"] == 12
    assert "extra innings are open" in line["legend"][0]["text"]
    assert shown("extra-innings-playoff", open_innings="none")["line_score"]["columns"][6].get("open") is None


def test_a_called_game_marks_the_innings_it_never_reached_and_says_why():
    line = shown("called-mercy")["line_score"]
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3", "4", "5", "6", "7"]
    assert cells(line, "away") == [3, 5, 5, 4, 5, None, None]
    assert [c.get("void") for c in line["rows"]["home"]["cells"]] == [None] * 5 + [True, True]
    assert line["void_word"] == "not played"
    assert line["legend"][-1] == {"kind": "x", "mark": "X", "text": "Called after 5 innings: mercy rule."}
    line = shown("called-mercy-home-leads")["line_score"]
    assert line["legend"][-1]["text"] == "Called after 4½ innings: mercy rule."
    assert [c.get("void") for c in line["rows"]["home"]["cells"]][4:] == [True, True, True]


def test_a_coin_toss_game_says_who_batted_first():
    line = shown("bats-first-home")["line_score"]
    assert line["first"] == "home" and cells(line, "away")[-1] is None
    assert line["legend"][-1]["text"] == "Bravo led after the top of the 7th, so they didn't bat."
    assert shown("bats-first-home")["card"]["line_score"]["first"] == "home"


def test_the_card_has_its_own_compact_line_score_with_no_open_marks_or_legend():
    card = shown("clean")["card"]
    line = card["line_score"]
    assert line["legend"] == [] and line["title"] is None and not any(c.get("open") for c in line["columns"])
    assert cells(line, "away") == [2, 0, 5, 1, 0, 3, 0] and line["rows"]["home"]["extras"] == [18]
    assert [i for i, c in enumerate(line["rows"]["home"]["cells"]) if c.get("mark")] == [1, 4]


def test_the_card_names_the_top_bat():
    card = shown("clean")["card"]
    # Gary T., Ron B. and Norm W. each have 3 hits in 4 at-bats: Ron B.'s 3 RBI decide it
    assert card["note"] == "Top bat: Ron B. 3 for 4" and card["strong"] == "Ron B." and card["link_label"] == "Box score"
    assert card["meta_extra"] == []


def test_the_top_bat_is_most_hits_then_fewest_at_bats_then_rbi_then_batting_order():
    reading = reading_of("clean")
    rows = reading.facts["batting"]["home"]
    rows[2]["line"] = {"ab": 3, "r": 2, "h": 3, "rbi": 3, "hr": 1, "bb": 0}            # Ron B.: 3 for 3 beats Gary T.'s 3 for 4
    card = call_sport("present", SPORT.rules.present, reading, ctx_of("clean"))["card"]
    assert card["note"] == "Top bat: Ron B. 3 for 3"
    rows[0]["line"] = {"ab": 3, "r": 2, "h": 3, "rbi": 5, "hr": 0, "bb": 0}            # same hits and at-bats: more RBI wins
    assert call_sport("present", SPORT.rules.present, reading, ctx_of("clean"))["card"]["note"] == "Top bat: Gary T. 3 for 3"
    for side in ("home", "away"):
        for row in reading.facts["batting"][side]:
            row["line"] = {"ab": 3, "r": 0, "h": 0, "rbi": 0, "hr": 0, "bb": 0}
    assert call_sport("present", SPORT.rules.present, reading, ctx_of("clean"))["card"]["note"] is None


def test_a_game_with_no_batting_lines_has_no_top_bat():
    assert shown("tie")["card"]["note"] is None and shown("batting-none")["card"]["note"] is None
    assert shown("batting-order")["card"]["note"] is None


def test_the_facts_list_home_runs_three_hit_games_and_limit_innings_with_the_winner_first():
    facts = block_of(shown("clean"), "facts")
    assert facts["title"] is None
    rows = {r["label"]: r["items"] for r in facts["rows"]}
    assert list(rows) == ["Home runs", "3+ hits", "Limit innings"]
    assert rows["Home runs"] == [
        {"side": "home", "players": [{"player": "ron-b", "extra": None}, {"player": "dave-k", "extra": None}], "text": None},
        {"side": "away", "players": [{"player": "phil-g", "extra": None}], "text": None}]
    assert rows["3+ hits"] == [
        {"side": "home", "players": [{"player": "gary-t", "extra": None}, {"player": "ron-b", "extra": None}], "text": None},
        {"side": "away", "players": [{"player": "norm-w", "extra": None}], "text": None}]
    assert rows["Limit innings"] == [{"side": None, "players": [], "text": "Alpha 2 (2nd, 5th)"},
                                     {"side": None, "players": [], "text": "Bravo 1 (3rd)"}]


def test_a_player_with_two_home_runs_gets_a_count_and_a_row_with_nothing_is_left_out():
    reading = reading_of("clean")
    reading.facts["hr_players"]["home"][0]["hr"] = 2
    facts = block_of(call_sport("present", SPORT.rules.present, reading, ctx_of("clean")), "facts")
    assert facts["rows"][0]["items"][0]["players"][0] == {"player": "ron-b", "extra": "2"}
    assert "facts" not in [b["type"] for b in shown("tie")["blocks"]]      # no lines and no limit innings: nothing to list


def test_the_facts_say_what_stopped_a_called_game():
    rows = {r["label"]: r["items"] for r in block_of(shown("called-mercy"), "facts")["rows"]}
    assert rows["Called"] == [{"side": None, "players": [], "text": "After 5 innings: mercy rule, 15 runs"}]
    rows = {r["label"]: r["items"] for r in block_of(shown("called-time"), "facts")["rows"]}
    assert rows["Called"][0]["text"] == "After 6 innings: time limit, 60 minutes"
    rows = {r["label"]: r["items"] for r in block_of(shown("called-under-official"), "facts")["rows"]}
    assert rows["Called"][0]["text"] == "After 3 innings: weather"
    rows = {r["label"]: r["items"] for r in block_of(shown("called-mercy-home-leads"), "facts")["rows"]}
    assert rows["Called"][0]["text"] == "After 4½ innings: mercy rule, 15 runs"


def test_a_league_with_no_run_limit_has_no_limit_row():
    assert "facts" not in [b["type"] for b in shown("run-limit-0")["blocks"]]


def test_the_batting_tables_are_one_per_side_in_batting_order_with_totals():
    result = shown("clean")
    tables = [b for b in result["blocks"] if b["type"] == "stat_table"]
    assert [(t["side"], t["title"], t["heading"]) for t in tables] == [
        ("away", "Bravo batting", "plain"), ("home", "Alpha batting", "plain")]
    away = tables[0]
    assert away["number_col"] is True and away["number_label"] == "#" and away["player_label"] == "Batter"
    assert [c["label"] for c in away["columns"]] == ["AB", "R", "H", "RBI", "HR", "BB"]
    assert [r["num"] for r in away["rows"]] == [str(i) for i in range(1, 11)]
    assert away["rows"][0] == {"player": "norm-w", "num": "1", "cells": {"ab": "4", "r": "2", "h": "3", "rbi": "0", "hr": "0", "bb": "0"}}
    assert away["totals"] == {"label": "Totals", "cells": {"ab": "34", "r": "11", "h": "15", "rbi": "10", "hr": "1", "bb": "0"}}
    assert tables[1]["totals"]["cells"] == {"ab": "33", "r": "14", "h": "18", "rbi": "13", "hr": "2", "bb": "0"}
    assert result["blocks"][-1] == {"type": "note", "text": "# = batting order from the score sheet."}


def test_after_a_coin_toss_the_team_that_batted_first_is_listed_first():
    result = shown("bats-first-home")
    assert [b["side"] for b in result["blocks"] if b["type"] == "stat_table"] == []     # no lines in that fixture
    roster = block_of(result, "roster", "Batting order")
    assert [t["side"] for t in roster["teams"]] == ["home", "away"]
    assert [t["side"] for t in block_of(shown("batting-order"), "roster", "Batting order")["teams"]] == ["away", "home"]


def test_a_league_that_keeps_the_order_only_gets_a_batting_order_list():
    result = shown("batting-order")
    assert not [b for b in result["blocks"] if b["type"] == "stat_table"]
    roster = block_of(result, "roster", "Batting order")
    assert [t["side"] for t in roster["teams"]] == ["away", "home"]
    assert [r["role"] for r in roster["teams"][0]["rows"]] == [str(i) for i in range(1, 11)]
    assert roster["teams"][0]["rows"][0] == {"role": "1", "player": "norm-w", "key": False, "spare_for": None}


def test_a_game_with_lines_for_one_side_shows_a_table_and_a_list():
    result = shown("optional-one-side")
    assert [b["side"] for b in result["blocks"] if b["type"] == "stat_table"] == ["away"]
    assert [t["side"] for t in block_of(result, "roster")["teams"]] == ["home"]


def test_a_league_that_keeps_team_results_only_has_no_batting_block():
    result = shown("batting-none")
    assert [b["type"] for b in result["blocks"]] == []
    assert shown("tie")["blocks"][0]["type"] == "roster"


# ------------------------------------------------------------------ standings

def games_from(*names):
    games = []
    for i, name in enumerate(names):
        reading = reading_of(name)
        games.append(StandingsGame(f"g{i}", "aa", "bb", reading, type=case_of(name)["fixture"]["game_type"],
                                   file=f"games/g{i}.yml"))
    return games


def defaults():
    return normalise_standings(sport_standings_defaults(SPORT.spec))


def table_of(games, standings):
    standings = {**standings, "columns": ["gp", "w", "l", "t", "otw", "otl", "pts", "pf", "pa", "diff"]}
    return {r["team"]: r["values"] for r in compute_standings(games, TEAMS, standings, regulation_periods=7).rows}


def test_a_win_is_two_points_a_tie_one_and_a_loss_nothing():
    row = table_of(games_from("clean", "tie"), defaults())
    assert (row["aa"]["w"], row["aa"]["t"], row["aa"]["pts"], row["bb"]["l"], row["bb"]["t"], row["bb"]["pts"]) == (1, 1, 3, 1, 1, 1)
    assert (row["aa"]["pf"], row["aa"]["pa"], row["aa"]["diff"]) == (24, 21, 3)


def test_an_extra_inning_win_counts_like_any_win():
    row = table_of(games_from("extra-innings-regular-2"), defaults())
    assert (row["aa"]["w"], row["aa"]["otw"], row["aa"]["pts"], row["bb"]["l"], row["bb"]["pts"]) == (1, 1, 2, 1, 0)


def test_a_tied_playoff_game_is_the_cores_error_at_the_r_box():
    game = replace(games_from("tie")[0], type="playoff")
    results, problems = game_results(game, defaults(), 7)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.totals.home.r")]
    assert game.reading.score.final_at["home"] == problems[0].at


def test_with_ties_not_allowed_a_regular_season_tie_is_the_cores_error_at_the_r_box():
    results, problems = game_results(games_from("tie")[0], {**defaults(), "ties": False}, 7)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.totals.home.r")]


def test_the_forfeit_is_seven_to_nothing():
    row = table_of([StandingsGame("g1", "aa", "bb", None, forfeit="bb", file="games/g1.yml")], defaults())
    assert (row["aa"]["w"], row["aa"]["pts"], row["aa"]["pf"], row["bb"]["pf"], row["bb"]["pts"], row["aa"]["diff"]) == (1, 2, 7, 0, 0, 7)


def test_the_run_difference_tiebreaker_counts_a_game_at_most_seven_either_way():
    assert defaults()["tiebreakers"][1] == {"diff": {"cap": 7}}
    row = table_of(games_from("called-mercy"), defaults())      # 22-4: Bravo won by 18, counted as 7 in the tiebreak only
    assert row["bb"]["diff"] == 18 and row["bb"]["pts"] == 2


# ------------------------------------------------------------------ the options change only the checks they should

def checks(name, **options):
    return [(p.level, p.at) for p in SPORT.rules.check(fixture_sheet(name), ctx_of(name, **options))]


def test_the_innings_option_is_the_regulation_length_and_the_open_inning():
    sheet = {"runs": {"away": [1, 0, 2, 1, 3], "home": [0, 2, 0, 3, 1]},
             "totals": {"away": {"r": 7, "h": 5}, "home": {"r": 6, "h": 7}}, "batting": {"away": [{"player": "norm-w"}], "home": [{"player": "gary-t"}]}}
    assert SPORT.rules.check(sheet, make_ctx(innings=5)) == []
    assert [(p.level, p.at) for p in SPORT.rules.check(sheet, make_ctx(innings=7))] == [("error", "called")]
    reading = SPORT.rules.read(sheet, make_ctx(innings=5))
    assert reading.facts["innings"] == 5 and reading.facts["limited"] == [True] * 4 + [False]
    assert len(reading.score.periods["home"]) == 5


def test_the_mercy_and_official_settings_only_move_the_called_game_warnings():
    assert checks("called-mercy") == []
    assert checks("called-mercy", mercy_runs=25) == [("warning", "called")]
    assert checks("called-mercy", mercy_after=6) == [("warning", "called")]
    assert checks("called-under-official") == [("warning", "called")]
    assert checks("called-under-official", official_innings=3) == []


def test_the_extra_innings_setting_does_not_touch_a_playoff_game():
    assert checks("extra-innings-playoff") == [] and checks("extra-innings-playoff", extra_innings=0) == []
    assert checks("extra-innings-regular-0", extra_innings=2) == []


def test_the_hr_limit_is_off_by_default_and_a_warning_when_set():
    assert checks("clean") == [] and checks("clean", hr_limit=2) == [] and checks("clean", hr_limit=1) == [("warning", "batting.home")]


def test_the_batting_setting_changes_what_a_game_must_carry():
    assert checks("clean", batting="every_game") == []
    assert ("error", "batting") in checks("clean", batting="none")
    assert ("error", "batting.away.0.ab") in checks("clean", batting="order")
    assert checks("batting-order", batting="optional") == checks("tie")


def test_a_season_override_can_turn_errors_on_and_the_e_box_is_then_required():
    assert checks("clean", team_errors="kept") == [("error", "totals.home.e"), ("error", "totals.away.e")]


# ------------------------------------------------------------------ check on broken sheets: never raises, never changes its input

def walk(node, path=()):
    yield path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, path + (i,))


def get(node, path):
    for key in path:
        node = node[key]
    return node


def mutations(sheet):
    for path in walk(sheet):
        if not path:
            continue
        for how, value in (("delete", None), ("none", None), ("minus", -1), ("text", "x"), ("block", {}), ("list", []),
                           ("float", 2.5), ("true", True), ("false", False), ("big", 99), ("big-text", "X" * 30),
                           ("deep", {"a": [1]}), ("x", "X"), ("home", "home"), ("mercy", "mercy"), ("huge", 10 ** 9)):
            broken = copy.deepcopy(sheet)
            parent = get(broken, path[:-1])
            if how == "delete":
                del parent[path[-1]]
            else:
                parent[path[-1]] = value
            yield f"{how} {path}", broken
    for path in walk(sheet):
        if isinstance(get(sheet, path), dict):
            broken = copy.deepcopy(sheet)
            get(broken, path)["zzz"] = 1
            yield f"unknown key under {path}", broken
    for value in ("hello", None, [], 3, {}, {"runs": 1, "totals": 2, "called": 3, "bats_first": 4, "batting": 5}):
        yield f"whole sheet {value!r}", value


NAMES = ["clean", "walk-off", "called-mercy-home-leads", "extra-innings-playoff", "bats-first-home", "tie"]


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("folder", ["games", "drafts"])
def test_check_never_raises_and_never_changes_its_input(name, folder):
    ctx = replace(ctx_of(name), folder=folder)
    sheet = fixture_sheet(name)
    for what, broken in mutations(sheet):
        before, ctx_before = copy.deepcopy(broken), copy.deepcopy(ctx)
        problems = call_sport("check", SPORT.rules.check, broken, ctx)
        assert broken == before and ctx == ctx_before, what
        final = call_sport("check", SPORT.rules.check, broken, replace(ctx, folder="games"))
        draft = call_sport("check", SPORT.rules.check, broken, replace(ctx, folder="drafts"))
        assert sum(p.level == "error" for p in draft) <= sum(p.level == "error" for p in final), what
        assert all(p.message and p.message == p.message.strip() and p.at == p.at.strip() for p in problems), what


@pytest.mark.parametrize("name", NAMES + ["batting-order", "optional-one-side", "e-kept"])
def test_a_sheet_that_check_accepts_can_always_be_read_and_presented(name):
    ctx = ctx_of(name)
    for what, broken in mutations(fixture_sheet(name)):
        problems = SPORT.rules.check(broken, ctx)
        if not any(p.level == "error" for p in problems):
            reading = call_sport("read", SPORT.rules.read, broken, ctx)       # raises InternalError if read cannot cope
            call_sport("present", SPORT.rules.present, reading, ctx)


def test_the_readme_names_every_rule_and_the_fixtures_exist_for_each_case_it_names():
    text = README.read_text(encoding="utf-8")
    for case in ("clean", "tie", "walk-off", "called-mercy", "extra-innings-playoff", "bats-first-home", "batting-order"):
        assert (FIXTURES / f"{case}.yml").is_file()
    for needle in ("run limit", "open inning", "mercy", "walk-off", "called", "extra inning", "coin toss", "substitute",
                   "spare", "forfeit", "bats_first", "limit_play", "X"):
        assert needle.lower() in text.lower(), needle
