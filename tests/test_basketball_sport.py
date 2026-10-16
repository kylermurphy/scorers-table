"""The basketball sport (sports/basketball/, docs/stage-5-basketball-spec.md): sport.yml, `derive`, `present`
(line score, top performer, box score, fouls note), the standings it asks of the core with the Masters preset
from the README, and `check` on broken sheets. The checks themselves are in test_basketball_fixtures.py."""
import copy
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.core.config import deep_merge, normalise_standings, sport_decide_settings, sport_standings_defaults
from scripts.core.model import BLOCK_TYPES, CELL_FLAGS, Line, Player, Reading, Score, SportContext, Team
from scripts.core.problems import Checker, call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, check_option_value, check_standings, load_sport
from scripts.core.standings import StandingsGame, compute_standings, game_results

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "sports" / "basketball" / "fixtures"
README = ROOT / "sports" / "basketball" / "README.md"

SPORT, LOAD_PROBLEMS = load_sport("basketball", SPORTS_ROOT)
_CONTEXT = parse_yaml((FIXTURES / "context.yml").read_text(encoding="utf-8"))
TEAMS = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in _CONTEXT["teams"]}
PLAYERS = {p["id"]: Player(p["id"], p["name"], p["team"], p.get("number"), p.get("sub", False)) for p in _CONTEXT["players"]}


def make_ctx(folder="games", game_type="regular", **options):
    opts = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | options
    return SportContext(sport=SPORT.spec, options=opts, teams=TEAMS, players=PLAYERS, sides={"home": "aa", "away": "bb"},
                        game_type=game_type, folder=folder)


def fixture_sheet(name):
    return parse_yaml((FIXTURES / f"{name}.yml").read_text(encoding="utf-8"))["sheet"]


def reading_of(name, **options):
    ctx = make_ctx(**options)
    sheet = fixture_sheet(name)
    assert SPORT.rules.check(sheet, ctx) == [] or all(p.level == "warning" for p in SPORT.rules.check(sheet, ctx))
    return SPORT.rules.read(sheet, ctx)


def line(side, player, pts, ftm=0, fta=0, pf=0, tech=0, flagrant=0):
    return Line(side, player, "player", {"pts": pts, "ftm": ftm, "fta": fta, "pf": pf, "tech": tech, "flagrant": flagrant})


def made_reading(home_lines, away_lines, home=(5, 7, 5, 5), away=(5, 5, 6, 3), extra=None, facts=None):
    periods = {"home": list(home), "away": list(away)}
    final = {s: sum(p) + sum((extra or {}).get(s, [0])) for s, p in periods.items()}
    return Reading(score=Score(final=final, periods=periods, extra=extra or {},
                               decided_in="overtime" if extra else "regulation",
                               final_at={"home": "sheet.boxes.home.final", "away": "sheet.boxes.away.final"}),
                   lines=home_lines + away_lines, facts=facts or {"technicals": [], "flagrants": []})


def shown(reading, **options):
    return call_sport("present", SPORT.rules.present, reading, make_ctx(**options))


def blocks_of(result, kind):
    return [b for b in result["blocks"] if b["type"] == kind]


# ------------------------------------------------------------------ sport.yml

def test_the_sport_folder_loads_without_an_error():
    assert not [p for p in LOAD_PROBLEMS if p.level == "error"], LOAD_PROBLEMS
    assert SPORT.name == "Basketball" and SPORT.spec["default_layout"] == "basketball"
    assert README.read_text(encoding="utf-8").strip()


def test_the_sport_knows_no_league():
    for name in ("sport.yml", "rules.py"):
        text = (SPORT.folder / name).read_text(encoding="utf-8")
        assert "MBL-SS6" not in text and "Thunder Bay" not in text, name


def test_four_quarters_and_the_period_words():
    spec = SPORT.spec
    assert spec["line_score"] == {"shape": "quarters", "total_label": "Final", "corner": "Team", "periods": 4}
    assert spec["words"]["period"] == {"one": "Quarter", "many": "Quarters", "short": "Q"}
    assert spec["words"]["day"] == "Week"


def test_the_options_and_everything_the_league_decides():
    assert SPORT.spec["options"]["overtime"]["values"] == ["overtime", "none"]
    assert SPORT.spec["options"]["overtime"]["default"] == "overtime" and SPORT.spec["options"]["overtime"]["decide"]
    assert SPORT.spec["options"]["foul_limit"]["default"] == 5 and not SPORT.spec["options"]["foul_limit"].get("decide")
    assert dict(sport_decide_settings(SPORT.spec)) == {
        "rules.overtime": "Overtime", "standings.ties": "Ties", "standings.forfeit": "Forfeit",
        "standings.tiebreakers": "Tiebreakers",
        "stats.minimums.ppg_min_games": "Minimum games for the points per game leaders",
        "stats.minimums.ft_min_attempts": "Minimum free throw attempts for the free throw % leaders"}


def test_the_default_standings_are_the_typical_club_rule():
    std = normalise_standings(sport_standings_defaults(SPORT.spec))
    assert std["rank_by"] == "points" and std["points"] == {"win": 2, "tie": 1, "loss": 0, "ot_win": 2, "ot_loss": 0}
    assert std["period_points"] == 0 and std["ties"] is False
    assert std["forfeit"] == {"score": [20, 0]} and std["tiebreakers"] == ["head_to_head", "diff", "points_for"]
    assert std["columns"] == ["gp", "w", "l", "pts", "diff"]


def test_the_stats_columns_and_leaderboards():
    stats = SPORT.spec["stats"]
    assert [s["key"] for s in stats["player"]] == ["pts", "ftm", "fta", "pf", "tech", "flagrant"]
    assert [(s["key"], s["label"], s["places"]) for s in stats["derived"]] == [("ppg", "PPG", 1), ("ft_pct", "FT%", 1)]
    assert stats["columns"]["player"] == {"table": ["gp", "pts", "ppg", "ftm", "fta", "ft_pct"],
                                          "totals": ["gp", "pts", "ppg", "ftm", "fta", "ft_pct", "tech"],
                                          "log": ["pts", "ftm", "fta", "tech"]}
    boards = {b["id"]: b for b in SPORT.spec["leaderboards"]}
    assert list(boards) == ["ppg", "ft_pct", "pts", "tech"]
    assert boards["ppg"]["tile"] and boards["ppg"]["edge"] == "hot" and boards["ppg"]["min"]["setting"] == "ppg_min_games"
    assert boards["ppg"]["min"]["cap_at_team_games"] is True
    assert boards["ft_pct"]["tile"] and boards["ft_pct"]["edge"] == "accent" and boards["ft_pct"]["zero"] is True
    assert boards["ft_pct"]["min"] == {"stat": "fta", "setting": "ft_min_attempts"}
    assert not boards["pts"].get("tile") and "min" not in boards["pts"]
    assert boards["tech"]["playoffs"] is True and boards["tech"]["home"] is False and boards["tech"]["player_rank"] is False
    assert SPORT.spec["minimums"]["ppg_min_games"]["default"] == 0 and SPORT.spec["minimums"]["ft_min_attempts"]["default"] == 10


# ------------------------------------------------------------------ derive

def test_derive_gives_the_unrounded_rates():
    got = SPORT.rules.derive({"gp": 8, "pts": 161, "ftm": 7, "fta": 8}, "player")
    assert got == {"ppg": 161 / 8, "ft_pct": 87.5}
    assert SPORT.rules.derive({"gp": 3, "pts": 61, "ftm": 1, "fta": 3}, "player")["ft_pct"] == 100 / 3     # not rounded to 33.3
    assert SPORT.rules.derive({"gp": 20, "pts": 403, "ftm": 0, "fta": 0}, "player")["ppg"] == 20.15


def test_derive_with_nothing_to_divide_by_gives_none():
    assert SPORT.rules.derive({"gp": 0, "pts": 0, "ftm": 0, "fta": 0}, "player") == {"ppg": None, "ft_pct": None}
    assert SPORT.rules.derive({"gp": 4, "pts": 30, "ftm": 0, "fta": 0}, "player") == {"ppg": 7.5, "ft_pct": None}
    assert SPORT.rules.derive({"gp": 4, "pts": 30, "ftm": 0, "fta": 5}, "player")["ft_pct"] == 0.0     # a real 0.0%
    assert SPORT.rules.derive({}, "player") == {"ppg": None, "ft_pct": None}


def test_the_core_rounds_derived_values_half_up():
    from scripts.core.fmt import decimal
    assert decimal(SPORT.rules.derive({"gp": 20, "pts": 403, "ftm": 0, "fta": 0}, "player")["ppg"], 1) == "20.2"
    assert decimal(SPORT.rules.derive({"gp": 8, "pts": 0, "ftm": 1, "fta": 8}, "player")["ft_pct"], 1) == "12.5"
    assert decimal(SPORT.rules.derive({"gp": 1, "pts": 0, "ftm": 1, "fta": 16}, "player")["ft_pct"], 1) == "6.3"   # 6.25


# ------------------------------------------------------------------ present: the line score

def test_the_line_score_marks_each_teams_biggest_quarter():
    out = shown(reading_of("clean"))["line_score"]
    assert out["shape"] == "quarters" and out["corner"] == "Team" and out["total_label"] == "Final"
    assert [c["label"] for c in out["columns"]] == ["Q1", "Q2", "Q3", "Q4"]
    assert out["rows"]["home"]["cells"] == [{"v": 5}, {"v": 7, "won": True}, {"v": 5}, {"v": 5}]
    assert out["rows"]["away"]["cells"] == [{"v": 5}, {"v": 5}, {"v": 6, "won": True}, {"v": 3}]
    assert (out["rows"]["home"]["total"], out["rows"]["away"]["total"]) == (22, 19)
    assert out["legend"] == [{"kind": "won", "text": "Biggest quarter for each team"}]
    assert out["won_word"] == "biggest quarter" and out["caption"] == "Points by quarter"


def test_every_quarter_equal_to_the_biggest_is_marked():
    reading = made_reading([line("home", "al-a", 5)], [line("away", "bo-c", 5)], home=(7, 4, 7, 4), away=(0, 0, 0, 0))
    out = shown(reading)["line_score"]
    assert [c.get("won", False) for c in out["rows"]["home"]["cells"]] == [True, False, True, False]
    assert not any(c.get("won") for c in out["rows"]["away"]["cells"])         # a team that never scored marks nothing


def test_an_overtime_game_has_an_ot_column_that_is_never_marked():
    out = shown(reading_of("overtime"))["line_score"]
    assert [c["label"] for c in out["columns"]] == ["Q1", "Q2", "Q3", "Q4", "OT"]
    assert out["rows"]["home"]["cells"][-1] == {"v": 3} and out["rows"]["away"]["cells"][-1] == {"v": 2}
    assert (out["rows"]["home"]["total"], out["rows"]["away"]["total"]) == (25, 24)
    out = shown(reading_of("scoreless-overtime"))["line_score"]
    assert out["rows"]["home"]["cells"][-1] == {"v": 0}


def test_present_has_only_known_keys_blocks_and_flags_for_every_fixture_that_reads():
    for path in sorted(FIXTURES.glob("*.expected.json")):
        expected = json.loads(path.read_text(encoding="utf-8"))
        if not expected["reading"]:
            continue
        name = path.name[:-len(".expected.json")]
        case = parse_yaml((FIXTURES / f"{name}.yml").read_text(encoding="utf-8"))
        ctx = make_ctx(folder=case["fixture"]["folder"], game_type=case["fixture"]["game_type"], **case["fixture"]["options"])
        reading = SPORT.rules.read(case["sheet"], ctx)
        result = call_sport("present", SPORT.rules.present, reading, ctx)
        assert set(result) <= {"line_score", "card", "tiles", "blocks"}, name
        assert all(b["type"] in BLOCK_TYPES for b in result["blocks"]), name
        for row in result["line_score"]["rows"].values():
            assert len(row["cells"]) == len(result["line_score"]["columns"])
            assert all(set(c) <= {"v", *CELL_FLAGS} for c in row["cells"])


# ------------------------------------------------------------------ present: the card and the top performer

def test_the_card_names_the_top_scorer_and_the_hero_tiles_come_from_the_line_score():
    result = shown(reading_of("clean"))
    assert result["tiles"] is None
    assert result["card"] == {"note": "Top: #4 Al A. 9 pts", "strong": "#4 Al A.", "link_label": "Box score",
                              "note_long": "Top scorer: #4 Al A. 9 pts, 2-3 FT"}
    tile = blocks_of(result, "top_performer")
    assert tile == [{"type": "top_performer", "label": "Top scorer", "player": "al-a", "side": "home", "value": 9,
                     "unit": "Points", "detail": "Alpha · 2-3 free throws"}]
    assert result["blocks"][0]["type"] == "top_performer"


def test_a_top_scorer_with_no_free_throws_has_no_ft_in_the_long_note_or_the_detail():
    reading = made_reading([line("home", "al-a", 12), line("home", "amy-b", 3)], [line("away", "bo-c", 8)])
    result = shown(reading)
    assert result["card"]["note_long"] == "Top scorer: #4 Al A. 12 pts"
    assert blocks_of(result, "top_performer")[0]["detail"] == "Alpha"


def test_two_players_tied_for_the_most_points_each_get_a_tile():
    reading = made_reading([line("home", "al-a", 12, 2, 4)], [line("away", "bo-c", 12, 0, 0), line("away", "bev-d", 3)])
    result = shown(reading)
    assert [(b["player"], b["side"], b["value"]) for b in blocks_of(result, "top_performer")] == [("al-a", "home", 12), ("bo-c", "away", 12)]
    assert result["card"] == {"note": "Top: #4 Al A. and #5 Bo C. 12 pts", "strong": "#4 Al A. and #5 Bo C.", "link_label": "Box score"}


def test_three_or_more_tied_have_no_tile_and_a_counted_note():
    reading = made_reading([line("home", "al-a", 12), line("home", "amy-b", 12)], [line("away", "bo-c", 12), line("away", "bev-d", 3)])
    result = shown(reading)
    assert blocks_of(result, "top_performer") == []
    assert result["card"] == {"note": "3 players with 12 pts", "strong": "3 players", "link_label": "Box score"}


def test_nobody_scoring_means_no_tile_and_no_card_note():
    result = shown(made_reading([line("home", "al-a", 0)], [line("away", "bo-c", 0)]))
    assert blocks_of(result, "top_performer") == [] and result["card"]["note"] is None and result["card"]["strong"] is None


# ------------------------------------------------------------------ present: the box score and the notes

def test_the_box_score_has_the_players_ticked_here_in_sheet_order_and_a_totals_row():
    boxes = blocks_of(shown(reading_of("clean")), "stat_table")
    assert [b["side"] for b in boxes] == ["home", "away"]
    home = boxes[0]
    assert home["caption"] == "Alpha box score" and home["number_col"] is True and home["title"] is None
    assert [(c["key"], c["label"], c["key_col"]) for c in home["columns"]] == [("pts", "PTS", True), ("ft", "FTM-FTA", False), ("pf", "PF", False)]
    assert [r["player"] for r in home["rows"]] == ["al-a", "amy-b", "ann-c"]         # Ari D. was not ticked Here
    assert home["rows"][0]["cells"] == {"pts": "9", "ft": "2-3", "pf": "2"}
    assert home["totals"] == {"label": "Team · 3 played", "cells": {"pts": "22", "ft": "3-5", "pf": "3"}}
    assert home["note"] == "Free throws 60.0%"
    away = boxes[1]
    assert away["totals"] == {"label": "Team · 3 played", "cells": {"pts": "19", "ft": "3-5", "pf": "3"}}


def test_the_free_throw_note_is_one_decimal_half_up_and_missing_with_no_attempts():
    reading = made_reading([line("home", "al-a", 9, 1, 8)], [line("away", "bo-c", 9)])
    boxes = blocks_of(shown(reading), "stat_table")
    assert boxes[0]["note"] == "Free throws 12.5%" and boxes[1]["note"] is None
    reading = made_reading([line("home", "al-a", 9, 1, 16)], [line("away", "bo-c", 9, 2, 3)])
    boxes = blocks_of(shown(reading), "stat_table")
    assert boxes[0]["note"] == "Free throws 6.3%" and boxes[1]["note"] == "Free throws 66.7%"


def test_the_fouls_note_names_technicals_and_flagrants_with_the_quarter_and_never_the_notes_text():
    result = shown(reading_of("flagrant"))
    notes = [b["text"] for b in blocks_of(result, "note")]
    assert notes == ["Technical fouls: #5 Bo C. (Bravo). Flagrant fouls: #5 Bo C. (Bravo), Q3.",
                     "PF = personal fouls. Points come from the running score on the score sheet; free throws from its circles."]
    assert "elbow" not in json.dumps(result)


def test_the_fouls_note_only_when_there_were_fouls():
    notes = [b["text"] for b in blocks_of(shown(reading_of("overtime")), "note")]
    assert notes == ["Technical fouls: #5 Bo C. (Bravo).", notes[1]] and notes[1].startswith("PF = personal fouls")
    notes = [b["text"] for b in blocks_of(shown(reading_of("page-two")), "note")]
    assert len(notes) == 1 and notes[0].startswith("PF = personal fouls")


def test_several_fouls_and_overtime_flagrants():
    facts = {"technicals": [{"side": "home", "player": "al-a", "num": "4", "count": 2},
                            {"side": "away", "player": "bo-c", "num": "5", "count": 1}],
             "flagrants": [{"side": "home", "player": "al-a", "num": "4", "q": "OT"}, {"side": "away", "player": "bev-d", "num": "11", "q": 1}]}
    reading = made_reading([line("home", "al-a", 5, tech=2, pf=2, flagrant=1)], [line("away", "bo-c", 5)], facts=facts)
    text = [b["text"] for b in blocks_of(shown(reading), "note")][0]
    assert text == ("Technical fouls: #4 Al A. (Alpha) ×2; #5 Bo C. (Bravo). "
                    "Flagrant fouls: #4 Al A. (Alpha), OT; #11 Bev D. (Bravo), Q1.")


def test_a_side_with_nobody_in_the_box_score_has_no_table():
    assert [b["side"] for b in blocks_of(shown(made_reading([line("home", "al-a", 5)], [])), "stat_table")] == ["home"]


# ------------------------------------------------------------------ the standings it asks of the core

def games_from(*names, **options):
    return [StandingsGame(f"g{i}", "aa", "bb", reading_of(name, **options), file=f"games/g{i}.yml") for i, name in enumerate(names)]


def table_of(games, standings, teams=TEAMS):
    """{team: every standings column's value}, whatever columns the league shows."""
    standings = {**standings, "columns": ["gp", "w", "l", "t", "pw", "pts", "pf", "pa", "diff"]}
    return {r["team"]: r["values"] for r in compute_standings(games, teams, standings, regulation_periods=4).rows}


def readme_preset():
    """The yaml block under 'The Masters preset' in the README, parsed."""
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## The Masters preset"):]
    block = re.search(r"```yaml\n(.*?)```", section, re.S).group(1)
    return parse_yaml(block)


def test_the_readme_preset_is_valid_league_yml():
    preset = readme_preset()
    assert set(preset) == {"rules", "standings"}
    c = Checker("league.yml")
    check_standings(c, preset["standings"], "standings", [])
    check_option_value(c, preset["rules"]["overtime"], "rules.overtime", SPORT.spec["options"]["overtime"])
    assert c.problems == []


def test_the_masters_preset_gives_a_point_for_each_quarter_won_and_three_for_a_win():
    standings = normalise_standings(deep_merge(sport_standings_defaults(SPORT.spec), readme_preset()["standings"]))
    clean = table_of(games_from("clean"), standings)
    assert clean["aa"]["pts"] == 5 and clean["bb"]["pts"] == 1 and clean["aa"]["pw"] == 2 and clean["bb"]["pw"] == 1
    # tied after overtime: it stands, nothing for the tie or the overtime; the quarters still count (aa 1, bb 2)
    tie = table_of(games_from("tie"), standings)
    assert (tie["aa"]["t"], tie["aa"]["pts"], tie["bb"]["pts"]) == (1, 1, 2)
    # an overtime win is a win: 3, and the quarters
    ot = table_of(games_from("overtime"), standings)
    assert (ot["aa"]["w"], ot["aa"]["pts"], ot["bb"]["pts"]) == (1, 4, 2)
    assert ot["aa"]["diff"] == 1 and ot["aa"]["pf"] == 25 and ot["bb"]["pa"] == 25


def test_the_masters_forfeit_is_four_to_nothing_and_seven_points():
    standings = normalise_standings(deep_merge(sport_standings_defaults(SPORT.spec), readme_preset()["standings"]))
    games = [StandingsGame("g1", "aa", "bb", None, forfeit="bb", file="games/g1.yml")]
    row = table_of(games, standings)
    assert (row["aa"]["pts"], row["aa"]["pf"], row["aa"]["pw"], row["bb"]["pts"], row["bb"]["pf"]) == (7, 4, 4, 0, 0)


def test_by_default_a_win_is_two_points_and_a_quarter_is_worth_nothing():
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    row = table_of(games_from("clean", "overtime"), standings)
    assert (row["aa"]["pts"], row["bb"]["pts"], row["aa"]["w"]) == (4, 0, 2)
    games = [StandingsGame("g1", "aa", "bb", None, forfeit="bb", file="games/g1.yml")]
    row = table_of(games, standings)
    assert (row["aa"]["pf"], row["bb"]["pf"], row["aa"]["pts"]) == (20, 0, 2) and row["aa"]["diff"] == 20


def test_by_default_a_tied_game_is_the_cores_error_at_the_final_box_of_the_sheet():
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    game = games_from("tie")[0]
    results, problems = game_results(game, standings, 4)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.boxes.home.final")]
    assert game.reading.score.final_at["home"] == problems[0].at
    game = replace(game, type="playoff")
    _, problems = game_results(game, replace_ties(standings, True), 4)
    assert [(p.level, p.at) for p in problems] == [("error", "sheet.boxes.home.final")]       # never in a playoff


def replace_ties(standings, value):
    return {**standings, "ties": value}


def test_with_ties_allowed_a_tie_is_a_point_each():
    standings = replace_ties(normalise_standings(sport_standings_defaults(SPORT.spec)), True)
    row = table_of(games_from("tie"), standings)
    assert (row["aa"]["t"], row["aa"]["pts"], row["bb"]["pts"]) == (1, 1, 1)


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
                           ("float", 2.5), ("true", True), ("long", "M" * 30), ("deep", {"a": [1]})):
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
    for value in ("hello", None, [], 3, {}, {"players": 1, "running": 2, "lines": 3, "boxes": 4, "notes": 5}):
        yield f"whole sheet {value!r}", value


@pytest.mark.parametrize("name", ["flagrant", "overtime", "jersey-zero-and-double-zero"])
@pytest.mark.parametrize("folder", ["games", "drafts"])
def test_check_never_raises_and_never_changes_its_input(name, folder):
    ctx = make_ctx(folder=folder)
    sheet = fixture_sheet(name)
    for what, broken in mutations(sheet):
        before, ctx_before = copy.deepcopy(broken), copy.deepcopy(ctx)
        problems = call_sport("check", SPORT.rules.check, broken, ctx)
        assert broken == before and ctx == ctx_before, what
        final = call_sport("check", SPORT.rules.check, broken, replace(ctx, folder="games"))
        draft = call_sport("check", SPORT.rules.check, broken, replace(ctx, folder="drafts"))
        assert sum(p.level == "error" for p in draft) <= sum(p.level == "error" for p in final), what
        assert all(p.message and p.message == p.message.strip() and p.at == p.at.strip() for p in problems), what


def test_a_sheet_that_check_accepts_can_always_be_read():
    ctx = make_ctx()
    for what, broken in mutations(fixture_sheet("flagrant")):
        problems = SPORT.rules.check(broken, ctx)
        if not any(p.level == "error" for p in problems):
            call_sport("read", SPORT.rules.read, broken, ctx)       # raises InternalError if read cannot cope


def test_the_overtime_rule_changes_only_the_overtime_checks():
    sheet = fixture_sheet("overtime")
    assert SPORT.rules.check(sheet, make_ctx()) == []
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(overtime="none"))} == {"boxes.home.ot", "boxes.away.ot"}
    assert SPORT.rules.check(fixture_sheet("clean"), make_ctx(overtime="none")) == []


def test_the_foul_limit_is_an_option():
    sheet = fixture_sheet("clean")
    sheet["players"]["home"][0]["fouls"] = 6
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx())] == ["players.home.0.fouls"]
    assert SPORT.rules.check(sheet, make_ctx(foul_limit=6)) == []
    sheet["players"]["home"][0]["fouls"] = 7
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx(foul_limit=6))] == ["players.home.0.fouls"]
