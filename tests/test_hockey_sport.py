"""The hockey sport (sports/hockey/, docs/stage-5-hockey-spec.md): sport.yml, `read` and `present` on the fixture games
(the approved Hockey-Game mockup's numbers), `derive`, the standings it asks of the core, and `check` on broken sheets.
The checks themselves are in test_hockey_fixtures.py. The sample generator (`sample.py`) is package 4's: its
season-level tests (a shutout, an overtime win, a shootout, two goalies, a bench penalty and a penalty shot over a
season, every outcome under every `overtime` value) join this file with it, and test_sport_contract.py runs the
sample once it exists."""
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.core.config import normalise_standings, sport_decide_settings, sport_standings_defaults
from scripts.core.model import BLOCK_TYPES, CELL_FLAGS, Player, SportContext, Team
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, load_sport
from scripts.core.standings import StandingsGame, compute_standings, game_results

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "sports" / "hockey" / "fixtures"
README = ROOT / "sports" / "hockey" / "README.md"

SPORT, LOAD_PROBLEMS = load_sport("hockey", SPORTS_ROOT)
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


def ctx_of(name):
    fixture = case_of(name)["fixture"]
    return make_ctx(folder=fixture["folder"], game_type=fixture["game_type"], **fixture["options"])


def reading_of(name):
    ctx, sheet = ctx_of(name), fixture_sheet(name)
    assert not [p for p in SPORT.rules.check(sheet, ctx) if p.level == "error"]
    return SPORT.rules.read(sheet, ctx)


def shown(name):
    return call_sport("present", SPORT.rules.present, reading_of(name), ctx_of(name))


def block_of(result, kind, title=None):
    found = [b for b in result["blocks"] if b["type"] == kind and (title is None or b["title"] == title)]
    assert len(found) == 1, (kind, [b["type"] for b in result["blocks"]])
    return found[0]


# ------------------------------------------------------------------ sport.yml

def test_the_sport_folder_loads_without_a_problem():
    assert not LOAD_PROBLEMS, LOAD_PROBLEMS
    assert SPORT.name == "Hockey" and SPORT.spec["default_layout"] == "hockey"
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


def test_periods_the_words_and_the_display_hints():
    spec = SPORT.spec
    assert spec["line_score"] == {"shape": "periods", "total_label": "T", "corner": "Period", "periods": "periods"}
    assert spec["words"]["period"] == {"one": "Period", "many": "Periods", "short": "P"}
    assert spec["words"]["day"] == "Week" and spec["words"]["surface"] == "Pad" and "extra" not in spec["words"]
    assert spec["words"]["points_for"]["label"] == "GF" and spec["words"]["points_against"]["label"] == "GA"
    assert spec["game_minutes"] == 75 and spec["positions"] == ["forward", "defence", "goalie"]
    assert spec["display"] == {"card": "rows", "card_foot": "status_note", "surface": "sub", "card_head": "", "matchup": "vs"}
    assert spec["labels"]["leaders"] == "Leaders" and spec["labels_by_layout"]["classic"]["leaders"] == "Scoring leaders"


def test_the_options_and_everything_the_league_decides():
    options = SPORT.spec["options"]
    assert {k: o["default"] for k, o in options.items()} == {
        "periods": 3, "period_minutes": 15, "overtime": "none", "playoff_overtime": "sudden_death", "overtime_minutes": 5,
        "shootout_rounds": 3, "clock": "elapsed", "goalie_shots": "none", "goal_cap": 0}
    assert options["overtime"]["values"] == ["none", "overtime", "shootout", "shootout_only"]
    assert options["playoff_overtime"]["values"] == ["sudden_death", "shootout"]
    assert options["clock"]["values"] == ["elapsed", "remaining"] and options["goalie_shots"]["values"] == ["none", "recorded"]
    assert (options["periods"]["min"], options["periods"]["max"]) == (2, 4)
    assert (options["period_minutes"]["min"], options["period_minutes"]["max"]) == (5, 30)
    assert (options["overtime_minutes"]["min"], options["overtime_minutes"]["max"]) == (1, 20)
    assert (options["shootout_rounds"]["min"], options["shootout_rounds"]["max"]) == (1, 5)
    assert (options["goal_cap"]["min"], options["goal_cap"]["max"]) == (0, 10)
    assert "decide" not in options["goalie_shots"]
    decided = dict(sport_decide_settings(SPORT.spec))
    assert set(decided) == {"rules.periods", "rules.period_minutes", "rules.overtime", "rules.playoff_overtime",
                            "rules.overtime_minutes", "rules.shootout_rounds", "rules.clock", "rules.goal_cap",
                            "standings.ties", "standings.forfeit", "standings.tiebreakers", "stats.minimums.goalie_min_games"}


def test_the_default_standings_are_the_typical_rec_rule():
    std = normalise_standings(sport_standings_defaults(SPORT.spec))
    assert std["rank_by"] == "points" and std["points"] == {"win": 2, "tie": 1, "loss": 0, "ot_win": 2, "ot_loss": 0}
    assert std["period_points"] == 0 and std["ties"] is True
    assert std["forfeit"] == {"score": [1, 0]} and std["tiebreakers"] == ["wins", "head_to_head", "diff"]
    assert std["columns"] == ["gp", "w", "l", "t", "pts", "pf", "pa"]


def test_two_stat_groups_with_their_columns_and_boards():
    stats = SPORT.spec["stats"]
    assert [s["key"] for s in stats["skater"]] == ["g", "a", "pts", "pim", "ppg", "shg", "gwg"]
    assert [s["key"] for s in stats["goalie"]] == ["w", "l", "t", "otl", "ga", "sa", "sho", "a", "pim"]
    assert stats["labels"] == {"skater": "Skaters", "goalie": "Goalies"}
    derived = {d["key"]: d for d in stats["derived"]}
    assert derived["gaa"]["places"] == 2 and derived["gaa"]["group"] == "goalie"
    assert derived["sv_pct"]["places"] == 3 and derived["sv_pct"]["format"] == "dot" and derived["sv_pct"]["group"] == "goalie"
    assert stats["columns"]["skater"]["table"] == ["gp", "g", "a", "pts", "pim"]
    assert stats["columns"]["goalie"]["table"] == ["gp", "w", "l", "t", "ga", "gaa", "sho", "sv_pct"]
    boards = {b["id"]: b for b in SPORT.spec["leaderboards"]}
    assert list(boards) == ["points", "goals", "assists", "pim", "gaa", "shutouts", "sv_pct"]
    assert boards["points"]["columns"] == ["g", "a", "pts"] and not boards["points"].get("home") is False
    assert boards["gaa"]["order"] == "asc" and boards["gaa"]["zero"] and boards["gaa"]["tile"] and boards["gaa"]["edge"] == "accent"
    assert boards["shutouts"]["tile"] and boards["shutouts"]["edge"] == "hot"
    assert boards["pim"]["playoffs"] and boards["pim"]["player_rank"] is False and boards["pim"]["home"] is False
    assert boards["sv_pct"]["home"] is False and boards["sv_pct"]["zero"]
    assert SPORT.spec["minimums"]["goalie_min_games"]["default"] == 4
    assert boards["gaa"]["min"] == {"stat": "gp", "setting": "goalie_min_games", "cap_at_team_games": True}


# ------------------------------------------------------------------ derive

def test_goalie_rates_are_per_game_and_none_without_a_denominator():
    d = SPORT.rules.derive({"gp": 4, "ga": 10, "sa": 100}, "goalie")
    assert d == {"gaa": 2.5, "sv_pct": 0.9}
    assert SPORT.rules.derive({"gp": 4, "ga": 10, "sa": 0}, "goalie")["sv_pct"] is None
    assert SPORT.rules.derive({"gp": 0, "ga": 0}, "goalie") == {"gaa": None, "sv_pct": None}
    assert SPORT.rules.derive({"gp": 3, "ga": 0, "sa": 20}, "goalie") == {"gaa": 0.0, "sv_pct": 1.0}


def test_skaters_have_no_rates():
    assert SPORT.rules.derive({"gp": 8, "g": 4}, "skater") == {}
    assert SPORT.rules.derive({}, "skater") == {}


# ------------------------------------------------------------------ present: the approved Hockey-Game mockup

def test_present_returns_only_known_keys_blocks_and_flags():
    for name in ("clean", "ot-win", "shootout-win", "shootout-only", "two-goalies-decision", "tie", "shots-recorded",
                 "bench-penalty", "goals-left-out", "no-shutout-empty-net"):
        result = shown(name)
        assert set(result) == {"line_score", "card", "tiles", "blocks"}
        assert all(b["type"] in BLOCK_TYPES for b in result["blocks"])
        for row in result["line_score"]["rows"].values():
            assert all(set(c) <= {"v", *CELL_FLAGS} for c in row["cells"]), name
        assert result["tiles"] is None


def test_the_line_score_has_the_periods_and_a_total():
    line = shown("clean")["line_score"]
    assert (line["shape"], line["corner"], line["total_label"]) == ("periods", "Period", "T")
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3"]
    assert [c["v"] for c in line["rows"]["home"]["cells"]] == [2, 1, 2] and line["rows"]["home"]["total"] == 5
    assert [c["v"] for c in line["rows"]["away"]["cells"]] == [1, 2, 0] and line["rows"]["away"]["total"] == 3
    assert not any(set(c) - {"v"} for row in line["rows"].values() for c in row["cells"])


def test_the_foot_names_the_goalies_and_the_penalty_minutes():
    split = shown("clean")["line_score"]["split"]
    assert split == [[{"t": "Goalies: "}, {"t": "#31 Len T.", "b": True}, {"t": " · "}, {"t": "#1 Murray B.", "b": True}],
                     [{"t": "PIM 4–4"}]]


def test_overtime_and_the_shootout_are_their_own_columns():
    line = shown("ot-win")["line_score"]
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3", "OT"]
    assert [c["v"] for c in line["rows"]["home"]["cells"]] == [1, 0, 1, 1] and line["rows"]["home"]["total"] == 3
    line = shown("shootout-win")["line_score"]
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3", "OT", "SO"]
    assert [c["v"] for c in line["rows"]["home"]["cells"]] == [1, 0, 1, 0, 1]
    assert [c["v"] for c in line["rows"]["away"]["cells"]] == [0, 1, 1, 0, 0]
    line = shown("shootout-only")["line_score"]
    assert [c["label"] for c in line["columns"]] == ["1", "2", "3", "SO"]
    assert [c["label"] for c in shown("ot-scoreless-tie")["line_score"]["columns"]] == ["1", "2", "3", "OT"]


def test_the_card_names_the_winning_goal_a_tie_or_the_shootout():
    card = shown("clean")["card"]
    assert (card["note"], card["strong"], card["link_label"]) == ("GWG #12 Gord P.", "#12 Gord P.", "Game sheet")
    assert shown("tie")["card"]["note"] == "Tie" and shown("tie")["card"]["strong"] is None
    assert shown("shootout-win")["card"]["note"] == "Won in a shootout"
    assert shown("ot-win")["card"]["note"] == "GWG #12 Gord P."
    assert shown("ot-scoreless-tie")["card"]["note"] == "Tie"


def test_the_scoring_summary_has_a_group_for_every_period_with_its_tally_and_running_score():
    events = block_of(shown("clean"), "events")
    assert events["title"] == "Scoring"
    assert [g["label"] for g in events["groups"]] == ["1st period", "2nd period", "3rd period"]
    assert [[(t["side"], t["n"]) for t in g["tally"]] for g in events["groups"]] == [
        [("home", 2), ("away", 1)], [("home", 1), ("away", 2)], [("home", 2), ("away", 0)]]
    first = events["groups"][0]["events"][0]
    assert first == {"time": "4:12", "side": "home", "player": "gord-p", "name": "#12 Gord P.", "badge": None,
                     "sub": "Assists: #4 Barry S., #17 Ken L.", "score": "1–0"}
    assert events["groups"][1]["events"][2]["sub"] == "Unassisted"
    third = events["groups"][2]["events"]
    assert [(e["time"], e["badge"], e["score"]) for e in third] == [("5:31", "GWG", "4–3"), ("12:09", None, "5–3")]
    assert events["note"] == "Score shown Alpha first. Times are time elapsed in the period."
    assert all(g["empty"] for g in events["groups"])


def test_a_period_with_no_goals_says_so_and_the_marks_follow_the_scorer():
    events = block_of(shown("goals-left-out"), "events")
    assert [g["events"] for g in events["groups"]] == [[], [], []]
    assert events["groups"][0]["empty"] == "No scoring"
    events = block_of(shown("en-goal"), "events")
    assert events["groups"][2]["events"][-1]["name"] == "#12 Gord P. (EN)"
    assert block_of(shown("pp-goal"), "events")["groups"][0]["events"][2]["name"] == "#17 Ken L. (PP)"
    assert block_of(shown("ps-goal"), "events")["groups"][1]["events"][0]["name"] == "#14 Rod B. (PS)"
    assert block_of(shown("sh-goal"), "events")["groups"][1]["events"][1]["name"] == "#8 Doug H. (SH)"


def test_the_summary_says_when_times_are_time_left():
    assert block_of(shown("clock-remaining"), "events")["note"].endswith("Times are time left in the period.")


def test_overtime_and_the_shootout_get_their_own_groups():
    events = block_of(shown("ot-win"), "events")
    assert [g["label"] for g in events["groups"]] == ["1st period", "2nd period", "3rd period", "Overtime"]
    assert events["groups"][3]["events"][0]["badge"] == "GWG" and events["groups"][3]["events"][0]["score"] == "3–2"
    assert block_of(shown("ot-scoreless-tie"), "events")["groups"][3]["empty"] == "No scoring"
    events = block_of(shown("shootout-win"), "events")
    assert [g["label"] for g in events["groups"]][-2:] == ["Overtime", "Shootout"]
    shootout = events["groups"][-1]
    assert [(t["side"], t["n"]) for t in shootout["tally"]] == [("home", 2), ("away", 1)]
    assert [(e["side"], e["sub"], e["score"]) for e in shootout["events"]] == [
        ("home", "Scored", "1–0"), ("away", "Missed", "1–0"), ("home", "Missed", "1–0"), ("away", "Scored", "1–1"),
        ("home", "Scored", "2–1"), ("away", "Missed", "2–1")]
    assert [g["label"] for g in block_of(shown("playoff-sudden-death-ot2"), "events")["groups"]][-2:] == ["Overtime", "2nd overtime"]


def test_the_penalty_table_has_a_row_for_each_penalty_and_names_a_bench_penalty():
    penalties = block_of(shown("clean"), "penalties")
    assert penalties["title"] == "Penalties" and penalties["legend"] == ["home", "away"]
    assert [(r["period"], r["time"], r["side"], r["player"], r["infraction"], r["minutes"]) for r in penalties["rows"]] == [
        ("1", "12:15", "away", "bob-c", "Tripping", 2), ("2", "9:02", "home", "ken-l", "Hooking", 2),
        ("3", "8:44", "away", "gary-n", "Slashing", 2), ("3", "14:10", "home", "doug-h", "Body contact", 2)]
    bench = block_of(shown("bench-penalty"), "penalties")["rows"]
    assert bench[1]["text"] == "Bench (served by #6 Terry W.)" and bench[1]["player"] is None and bench[1]["side"] == "home"
    assert [b["type"] for b in shown("penalties-left-out")["blocks"]] == ["events", "group", "group"]


def test_the_goalies_table_shows_each_goalies_result_and_goals_against():
    group = block_of(shown("clean"), "group", "Goalies")
    assert group["note"] == "Both goalies played the full game."
    table = group["blocks"][0]
    assert table["type"] == "stat_table" and table["team_col"] is True and table["player_label"] == "Goalie"
    assert [(c["key"], c.get("style")) for c in table["columns"]] == [("result", "strong"), ("ga", "big")]
    assert [(r["player"], r["side"], r["cells"]) for r in table["rows"]] == [
        ("len-t", "home", {"result": "W", "ga": "3"}), ("murray-b", "away", {"result": "L", "ga": "5"})]
    rows = block_of(shown("ot-win"), "group", "Goalies")["blocks"][0]["rows"]
    assert [r["cells"]["result"] for r in rows] == ["W", "OTL"]
    rows = block_of(shown("tie"), "group", "Goalies")["blocks"][0]["rows"]
    assert [r["cells"]["result"] for r in rows] == ["T", "T"]


def test_two_goalies_are_both_listed_and_the_note_says_who_took_the_decision():
    group = block_of(shown("two-goalies-decision"), "group", "Goalies")
    assert group["note"] == "Alpha used two goalies; #35 Stu G. took the decision."
    rows = group["blocks"][0]["rows"]
    assert [(r["player"], r["cells"]["result"], r["cells"]["ga"]) for r in rows] == [
        ("len-t", "–", "2"), ("stu-g", "W", "1"), ("murray-b", "L", "5")]


def test_shots_and_the_save_percentage_show_only_when_recorded():
    table = block_of(shown("shots-recorded"), "group", "Goalies")["blocks"][0]
    assert [c["key"] for c in table["columns"]] == ["result", "ga", "sa", "sv"]
    assert [(r["cells"]["sa"], r["cells"]["sv"]) for r in table["rows"]] == [("28", ".893"), ("30", ".833")]
    assert [c["key"] for c in block_of(shown("clean"), "group", "Goalies")["blocks"][0]["columns"]] == ["result", "ga"]


def test_the_skaters_tables_list_players_with_a_goal_an_assist_or_a_penalty_and_a_total():
    group = block_of(shown("clean"), "group", "Skaters")
    assert group["intro"] == "Players with a goal, assist or penalty." and len(group["blocks"]) == 2
    home, away = group["blocks"]
    assert (home["side"], home["heading"], away["side"], away["heading"]) == ("home", "small", "away", "small")
    assert [c["key"] for c in home["columns"]] == ["g", "a", "pts", "pim"] and home["columns"][2]["key_col"] is True
    assert [(r["player"], r["cells"]) for r in home["rows"]][0] == ("gord-p", {"g": "2", "a": "2", "pts": "4", "pim": "0"})
    assert [r["player"] for r in home["rows"]] == ["gord-p", "ken-l", "barry-s", "doug-h", "terry-w"]
    assert home["totals"] == {"label": "Total", "cells": {"g": "5", "a": "7", "pts": "12", "pim": "4"}}
    assert away["totals"]["cells"] == {"g": "3", "a": "3", "pts": "6", "pim": "4"}
    assert [r["player"] for r in away["rows"]] == ["wayne-k", "rod-b", "phil-a", "bob-c", "gary-n"]


def test_a_goalie_with_an_assist_or_a_penalty_is_listed_with_the_skaters():
    home = block_of(shown("goalie-assist"), "group", "Skaters")["blocks"][0]
    row = next(r for r in home["rows"] if r["player"] == "len-t")
    assert row["cells"] == {"g": "0", "a": "1", "pts": "1", "pim": "2"}


def test_a_bench_penalty_is_in_the_team_total_and_in_no_row():
    home = block_of(shown("bench-penalty"), "group", "Skaters")["blocks"][0]
    assert home["totals"]["cells"]["pim"] == "6" and sum(int(r["cells"]["pim"]) for r in home["rows"]) == 4


def test_the_final_panel_foot_for_a_game_with_nobody_in_net_is_still_valid():
    assert shown("no-shutout-empty-net")["line_score"]["split"][-1] == [{"t": "PIM 0–0"}]


# ------------------------------------------------------------------ the standings it asks of the core

def games_from(*names):
    return [StandingsGame(f"g{i}", "aa", "bb", reading_of(name), type=case_of(name)["fixture"]["game_type"],
                          file=f"games/g{i}.yml") for i, name in enumerate(names)]


def defaults():
    return normalise_standings(sport_standings_defaults(SPORT.spec))


def table_of(games, standings):
    standings = {**standings, "columns": ["gp", "w", "l", "t", "otw", "otl", "pts", "pf", "pa", "diff"]}
    return {r["team"]: r["values"] for r in compute_standings(games, TEAMS, standings, regulation_periods=3).rows}


def test_a_win_is_two_points_a_tie_one_and_a_loss_nothing():
    row = table_of(games_from("clean", "tie"), defaults())
    assert (row["aa"]["w"], row["aa"]["t"], row["aa"]["pts"], row["bb"]["l"], row["bb"]["t"], row["bb"]["pts"]) == (1, 1, 3, 1, 1, 1)
    assert (row["aa"]["pf"], row["aa"]["pa"], row["aa"]["diff"]) == (7, 5, 2)


def test_an_overtime_or_shootout_loss_is_a_loss_unless_the_league_pays_for_it():
    row = table_of(games_from("ot-win"), defaults())
    assert (row["aa"]["w"], row["aa"]["otw"], row["aa"]["pts"], row["bb"]["l"], row["bb"]["otl"], row["bb"]["pts"]) == (1, 1, 2, 1, 1, 0)
    paid = {**defaults(), "points": {**defaults()["points"], "ot_loss": 1}}
    row = table_of(games_from("ot-win", "shootout-win"), paid)
    assert (row["bb"]["pts"], row["bb"]["otl"], row["aa"]["pts"]) == (2, 2, 4)


def test_a_shootout_goal_counts_in_goals_for_and_against():
    row = table_of(games_from("shootout-win"), defaults())
    assert (row["aa"]["pf"], row["aa"]["pa"], row["bb"]["pf"], row["bb"]["pa"]) == (3, 2, 2, 3)
    assert (row["aa"]["otw"], row["bb"]["otl"]) == (1, 1)


def test_a_tied_playoff_game_is_the_cores_error_at_the_final_box():
    game = games_from("playoff-scoreless-ot")[0]
    results, problems = game_results(game, defaults(), 3)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.score.home.final")]
    assert game.reading.score.final_at["home"] == problems[0].at


def test_with_ties_not_allowed_a_regular_season_tie_is_the_cores_error_at_the_final_box():
    results, problems = game_results(games_from("tie")[0], {**defaults(), "ties": False}, 3)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.score.home.final")]


def test_the_forfeit_is_one_to_nothing():
    row = table_of([StandingsGame("g1", "aa", "bb", None, forfeit="bb", file="games/g1.yml")], defaults())
    assert (row["aa"]["w"], row["aa"]["pts"], row["aa"]["pf"], row["bb"]["pf"], row["bb"]["pts"], row["aa"]["diff"]) == (1, 2, 1, 0, 0, 1)


# ------------------------------------------------------------------ the options change only the checks they should

def test_the_overtime_setting_changes_only_the_overtime_and_shootout_checks():
    level, ot_win = fixture_sheet("tie"), fixture_sheet("ot-win")
    assert SPORT.rules.check(level, make_ctx()) == []
    assert {p.at for p in SPORT.rules.check(level, make_ctx(overtime="overtime"))} == {"score.home.ot", "score.away.ot"}
    assert {p.at for p in SPORT.rules.check(level, make_ctx(overtime="shootout"))} == {
        "score.home.ot", "score.away.ot", "shootout", "score.home.so", "score.away.so"}
    assert {p.at for p in SPORT.rules.check(level, make_ctx(overtime="shootout_only"))} == {"shootout", "score.home.so", "score.away.so"}
    assert SPORT.rules.check(ot_win, make_ctx(overtime="overtime")) == []
    assert SPORT.rules.check(ot_win, make_ctx(overtime="shootout")) == []
    assert {p.at for p in SPORT.rules.check(ot_win, make_ctx(overtime="shootout_only"))} >= {"score.home.ot", "goals.4.period"}


def test_a_playoff_game_always_plays_overtime_and_the_playoff_setting_decides_the_shootout():
    level = fixture_sheet("tie")
    assert {p.at for p in SPORT.rules.check(level, make_ctx(game_type="playoff"))} == {"score.home.ot", "score.away.ot"}
    assert {p.at for p in SPORT.rules.check(level, make_ctx(game_type="playoff", overtime="shootout"))} == {"score.home.ot", "score.away.ot"}
    assert SPORT.rules.check(fixture_sheet("playoff-shootout"), make_ctx(game_type="playoff", playoff_overtime="shootout")) == []
    assert {p.at for p in SPORT.rules.check(fixture_sheet("playoff-shootout"), make_ctx(game_type="playoff"))} >= {"shootout"}
    assert SPORT.rules.check(fixture_sheet("ot-win"), make_ctx(game_type="playoff")) == []


def test_the_number_and_length_of_periods_are_options():
    sheet = fixture_sheet("clean")
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(periods=2))} >= {"score.home.periods", "goals.6.period"}
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(periods=4))} == {"score.home.periods", "score.away.periods"}
    assert SPORT.rules.check(fixture_sheet("periods-2"), make_ctx(periods=2, period_minutes=20)) == []
    assert [p.at for p in SPORT.rules.check(fixture_sheet("periods-2"), make_ctx(periods=2))] == ["goals.5.time"]
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(period_minutes=12))} == {"goals.2.time", "goals.7.time", "penalties.0.time", "penalties.3.time"}


def test_the_shootout_rounds_are_an_option():
    sheet = fixture_sheet("shootout-win")
    ctx = make_ctx(overtime="shootout")
    assert SPORT.rules.check(sheet, ctx) == []
    assert [(p.level, p.at) for p in SPORT.rules.check(sheet, replace(ctx, options={**ctx.options, "shootout_rounds": 2}))] == []     # level after two: one more round decides it
    assert [(p.level, p.at) for p in SPORT.rules.check(sheet, replace(ctx, options={**ctx.options, "shootout_rounds": 1}))] == [("warning", "shootout")]
    assert [(p.level, p.at) for p in SPORT.rules.check(sheet, replace(ctx, options={**ctx.options, "shootout_rounds": 5}))] == [("warning", "shootout")]


def test_the_clock_setting_only_reverses_the_order_warnings():
    sheet = fixture_sheet("clean")
    assert {p.level for p in SPORT.rules.check(sheet, make_ctx(clock="remaining"))} == {"warning"}
    assert SPORT.rules.check(fixture_sheet("clock-remaining"), make_ctx()) != []
    assert {p.level for p in SPORT.rules.check(fixture_sheet("clock-remaining"), make_ctx())} == {"warning"}


def test_a_league_that_records_shots_needs_them_and_one_that_does_not_forbids_them():
    sheet = fixture_sheet("shots-recorded")
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx())] == ["goalies.home.0.shots", "goalies.away.0.shots"]
    assert {p.at for p in SPORT.rules.check(fixture_sheet("clean"), make_ctx(goalie_shots="recorded"))} == {"goalies.home.0.shots", "goalies.away.0.shots"}


def test_the_goal_cap_is_off_by_default():
    sheet = fixture_sheet("clean")
    assert SPORT.rules.check(sheet, make_ctx()) == [] and SPORT.rules.check(sheet, make_ctx(goal_cap=2)) == []
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx(goal_cap=1))] == ["goals.5.num", "goals.6.num"]


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
                           ("deep", {"a": [1]}), ("ot", "OT"), ("bench", "bench"), ("time", "4:12"), ("zero-text", "00")):
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
    for value in ("hello", None, [], 3, {}, {"roster": 1, "goals": 2, "penalties": 3, "goalies": 4, "shootout": 5, "score": 6}):
        yield f"whole sheet {value!r}", value


@pytest.mark.parametrize("name", ["clean", "two-goalies-decision", "shootout-win", "bench-penalty", "ot-win"])
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


@pytest.mark.parametrize("name", ["clean", "two-goalies-decision", "shootout-win", "bench-penalty", "ot-win",
                                  "playoff-sudden-death-ot2", "shots-recorded"])
def test_a_sheet_that_check_accepts_can_always_be_read_and_presented(name):
    ctx = ctx_of(name)
    for what, broken in mutations(fixture_sheet(name)):
        problems = SPORT.rules.check(broken, ctx)
        if not any(p.level == "error" for p in problems):
            reading = call_sport("read", SPORT.rules.read, broken, ctx)       # raises InternalError if read cannot cope
            call_sport("present", SPORT.rules.present, reading, ctx)


def test_the_readme_lists_every_check_path_and_the_fixtures_exist_for_each_case_it_names():
    text = README.read_text(encoding="utf-8")
    for case in ("clean", "tie", "ot-win", "shootout-win", "two-goalies-decision", "bench-penalty"):
        assert (FIXTURES / f"{case}.yml").is_file()
    for needle in ("goals.6", "GWG", "shutout", "decision", "bench", "penalty shot", "overtime", "shootout", "forfeit",
                   "game cut short", "spare goalie"):
        assert needle.lower() in text.lower(), needle
