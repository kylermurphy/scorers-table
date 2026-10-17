"""The curling sport (sports/curling/, docs/stage-5-curling-spec.md): sport.yml, the hammer walk (against the
design-system sample's three games), `present` (line score, card, the numbers, the lineups), `derive`, the standings
it asks of the core, and `check` on broken sheets. The checks themselves are in test_curling_fixtures.py; the sample
generator (`sample.py`) is package 5's and is tested by test_sport_contract.py."""
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
from scripts.design_system import sample as design_sample

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "sports" / "curling" / "fixtures"
README = ROOT / "sports" / "curling" / "README.md"

SPORT, LOAD_PROBLEMS = load_sport("curling", SPORTS_ROOT)
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


def block_of(result, kind):
    found = [b for b in result["blocks"] if b["type"] == kind]
    assert len(found) == 1, (kind, [b["type"] for b in result["blocks"]])
    return found[0]


# ------------------------------------------------------------------ sport.yml

def test_the_sport_folder_loads_without_an_error():
    assert not [p for p in LOAD_PROBLEMS if p.level == "error"], LOAD_PROBLEMS
    assert not LOAD_PROBLEMS, LOAD_PROBLEMS
    assert SPORT.name == "Curling" and SPORT.spec["default_layout"] == "curling"
    assert README.read_text(encoding="utf-8").strip()


def test_the_sport_knows_no_real_league():
    for name in ("sport.yml", "rules.py", "README.md"):
        text = (SPORT.folder / name).read_text(encoding="utf-8")
        assert "Masters" not in text and "Thunder Bay" not in text, name
    for path in FIXTURES.glob("*"):
        assert "Masters" not in path.read_text(encoding="utf-8"), path.name


def test_ends_the_extra_end_and_the_words():
    spec = SPORT.spec
    assert spec["line_score"] == {"shape": "ends", "total_label": "Tot", "corner": "End", "periods": "ends"}
    assert spec["words"]["period"] == {"one": "End", "many": "Ends", "short": "E"}
    assert spec["words"]["extra"] == {"one": "Extra end", "short": "EE"}
    assert spec["words"]["day"] == "Draw" and spec["words"]["surface"] == "Sheet"
    assert spec["game_minutes"] == 120 and spec["positions"] == ["lead", "second", "vice", "skip"]
    assert spec["display"]["card"] == "lines" and spec["display"]["card_foot"] == "meta"
    assert spec["display"]["team_sub"] == "skip"
    assert [i["kind"] for i in spec["display"]["results_legend"]] == ["hammer", "mark", "x"]
    assert spec["labels"] == {"results": "Latest draw", "next": "Next draw", "leaders": "Rink leaders", "team": "Rink"}
    assert spec["labels_by_layout"]["classic"]["team"] == "Team" and spec["labels_by_layout"]["scoreboard"]["team"] == "Team"


def test_the_options_and_everything_the_league_decides():
    options = SPORT.spec["options"]
    assert (options["ends"]["type"], options["ends"]["default"], options["ends"]["min"], options["ends"]["max"]) == ("int", 8, 4, 10)
    assert options["ends"]["decide"] is True
    assert options["extra_end"]["values"] == ["playoffs", "always"] and options["extra_end"]["default"] == "playoffs"
    assert options["extra_end"]["decide"] is True
    assert options["lineups"]["values"] == ["recorded", "none"] and options["lineups"]["default"] == "recorded"
    assert "decide" not in options["lineups"]
    assert dict(sport_decide_settings(SPORT.spec)) == {
        "rules.ends": "Ends in a game", "rules.extra_end": "Extra end when a game is level after the last end",
        "standings.ties": "Ties", "standings.forfeit": "Forfeit", "standings.tiebreakers": "Tiebreakers"}


def test_the_default_standings_are_the_typical_club_rule():
    std = normalise_standings(sport_standings_defaults(SPORT.spec))
    assert std["rank_by"] == "points" and std["points"] == {"win": 2, "tie": 1, "loss": 0, "ot_win": 2, "ot_loss": 0}
    assert std["period_points"] == 0 and std["ties"] is True
    assert std["forfeit"] == {"score": [1, 0]} and std["tiebreakers"] == ["head_to_head", "diff"]
    assert std["columns"] == ["gp", "w", "l", "t", "pts", "pf", "pa"]


def test_players_have_games_played_only_and_teams_have_counts():
    stats = SPORT.spec["stats"]
    assert stats["player"] == [] and stats["derived"] == []
    assert stats["columns"]["player"] == {"table": ["gp"], "totals": ["gp"]}
    assert [(s["key"], s["label"]) for s in stats["team"]] == [
        ("ends_won", "EW"), ("stolen", "SE"), ("blanks", "BE"), ("big_ends", "3+"), ("hammer_ends", "HE"),
        ("hammer_scored", "HS"), ("ends", "E")]
    boards = {b["id"]: b for b in SPORT.spec["leaderboards"]}
    assert list(boards) == ["stolen", "ends_won", "big_ends"]
    assert all(b["of"] == "team" for b in boards.values())
    assert boards["stolen"]["tile"] and boards["stolen"]["edge"] == "hot"
    assert boards["ends_won"]["tile"] and boards["ends_won"]["edge"] == "accent"
    assert not boards["big_ends"].get("tile")
    assert SPORT.spec["minimums"] == {}


def test_derive_gives_nothing_because_curling_has_no_rates():
    assert SPORT.rules.derive({"gp": 8}, "player") == {}
    assert SPORT.rules.derive({}, "player") == {}
    assert call_sport("derive", SPORT.rules.derive, {"gp": 3}, "player") == {}


def test_the_readme_lists_every_check_with_its_path():
    text = README.read_text(encoding="utf-8")
    for path in ("`<key>`", "`hammer`", "`ends`", "`ends.<side>`", "`ends.<side>.<i>`", "`ends.home.<i>`", "`ends.home.0`",
                 "`conceded`", "`time_called`", "`extra`", "`extra.<side>`", "`extra.<side>.<i>`", "`extra.home.<i>`",
                 "`final`", "`final.<side>`", "`lineups`", "`lineups.<side>`", "`lineups.<side>.<i>`",
                 "`lineups.<side>.<i>.player`", "`lineups.<side>.<i>.position`", "`lineups.<side>.<i>.spare_for`"):
        assert path in text, path
    for how_to in ("A concession", "Time called", "An extra end", "A spare", "A three-player rink", "A forfeit"):
        assert how_to in text, how_to
    assert "hammer" in text.lower() and "Team Smith" in text          # the hammer rule, and the warning about rink names


# ------------------------------------------------------------------ read: the hammer walk against the sample's three games

def sample_games():
    return design_sample.CURLING["results"][:3]


@pytest.mark.parametrize("result", sample_games(), ids=lambda r: r["id"])
def test_the_hammer_walk_agrees_with_the_design_system_sample(result):
    home, away = result["home"], result["away"]
    scores = result["period_scores"]
    ends = {"home": ["X" if v is None else v for v in scores[home]], "away": ["X" if v is None else v for v in scores[away]]}
    sheet = {"hammer": "home" if result["hammer"] == home else "away", "ends": ends}
    if result["shook_hands_after"]:
        sheet["conceded"] = "away" if result["scores"][away] < result["scores"][home] else "home"
    sheet["final"] = {"home": result["scores"][home], "away": result["scores"][away]}
    ctx = make_ctx(lineups="none")
    assert SPORT.rules.check(sheet, ctx) == []
    reading = SPORT.rules.read(sheet, ctx)
    hammer = reading.facts["hammer_by_end"]
    played = len(hammer)
    assert played == len(scores[home]) - len(result["unplayed_ends"])
    stolen = {"home": [], "away": []}
    blank = []
    for i in range(played):
        h, a = ends["home"][i], ends["away"][i]
        if h == 0 and a == 0:
            blank.append(i + 1)
        else:
            scorer = "home" if h else "away"
            if hammer[i] != scorer:
                stolen[scorer].append(i + 1)
    assert stolen == {"home": result["stolen"][home], "away": result["stolen"][away]}
    assert blank == result["blank_ends"]
    assert reading.team_lines["home"]["stolen"] == len(result["stolen"][home])
    assert reading.team_lines["away"]["stolen"] == len(result["stolen"][away])
    assert reading.score.final == {"home": result["scores"][home], "away": result["scores"][away]}
    assert hammer[0] == sheet["hammer"]


def test_the_sample_mockup_numbers_come_out_of_the_rules():
    """The Curling-Game mockup's table (the design-system sample, 'Scored with hammer' corrected to 3 of 5)."""
    rows = {r["label"]: r["values"] for r in design_sample.CURLING["game"]["sections"][0]["rows"]}
    reading = reading_of("clean")                        # the same game: Alpha is Button Pushers, Bravo is Hurry Hard
    t = reading.team_lines
    assert str(t["home"]["ends_won"]) == rows["Ends won"]["button_pushers"] and str(t["away"]["ends_won"]) == rows["Ends won"]["hurry_hard"]
    assert str(t["home"]["stolen"]) == rows["Stolen ends"]["button_pushers"]
    assert str(t["away"]["hammer_ends"]) == rows["Ends with hammer"]["hurry_hard"]
    assert f"{t['home']['hammer_scored']} of {t['home']['hammer_ends']}" == rows["Scored with hammer"]["button_pushers"]
    assert f"{t['away']['hammer_scored']} of {t['away']['hammer_ends']}" == rows["Scored with hammer"]["hurry_hard"]
    assert str(t["away"]["blanks"]) == rows["Blank ends"]["hurry_hard"]
    assert str(t["home"]["big_ends"]) == rows["Big ends (3+)"]["button_pushers"]


def test_a_blank_end_keeps_the_hammer_and_a_score_gives_it_up():
    reading = reading_of("steals-and-big-end")           # Alpha starts with the hammer
    assert reading.facts["hammer_by_end"] == ["home", "home", "away", "home", "home", "away", "home", "away"]
    reading = reading_of("blank-first-end")
    assert reading.facts["hammer_by_end"][:3] == ["home", "home", "home"]
    assert reading.facts["hammer_by_end"][3] == "away"          # Alpha scored 2 with it in end 3


def test_the_team_counts_add_up():
    for name in ("clean", "steals-and-big-end", "blank-first-end", "conceded", "two-extra-ends", "all-blank", "clean-10-ends"):
        reading = reading_of(name)
        t = reading.team_lines
        ends = t["home"]["ends"]
        assert ends == t["away"]["ends"] == len(reading.facts["hammer_by_end"])
        assert t["home"]["hammer_ends"] + t["away"]["hammer_ends"] == ends
        assert t["home"]["ends_won"] + t["away"]["ends_won"] + t["home"]["blanks"] + t["away"]["blanks"] == ends, name
        for side in ("home", "away"):
            assert t[side]["stolen"] + t[side]["hammer_scored"] == t[side]["ends_won"], name
            assert t[side]["blanks"] + t[side]["hammer_scored"] <= t[side]["hammer_ends"]


def test_read_gives_a_score_the_core_can_count():
    reading = reading_of("conceded")
    assert reading.score.periods["home"][6:] == [None, None]
    assert reading.score.final_at == {"home": "sheet.final.home", "away": "sheet.final.away"}
    reading = reading_of("two-extra-ends")
    assert reading.score.extra == {"home": [0, 1], "away": [0, 0]} and reading.score.decided_in == "overtime"
    assert reading_of("clean").score.extra == {}


# ------------------------------------------------------------------ present: the line score

def test_the_line_score_of_the_mockup_game_has_hammers_a_steal_and_a_blank_end():
    out = shown("clean")["line_score"]
    assert out["shape"] == "ends" and out["corner"] == "End" and out["total_label"] == "Tot" and out["extra_label"] is None
    assert [c["label"] for c in out["columns"]] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert [i for i, c in enumerate(out["columns"]) if c.get("blank")] == [0]
    assert out["rows"]["home"]["cells"] == [
        {"v": 0}, {"v": 0}, {"v": 1, "won": True, "hammer": True}, {"v": 1, "won": True, "mark": True}, {"v": 0},
        {"v": 3, "won": True, "hammer": True}, {"v": 0}, {"v": 2, "won": True, "hammer": True}]
    assert out["rows"]["away"]["cells"] == [
        {"v": 0, "hammer": True}, {"v": 2, "won": True, "hammer": True}, {"v": 0}, {"v": 0, "hammer": True},
        {"v": 1, "won": True, "hammer": True}, {"v": 0}, {"v": 2, "won": True, "hammer": True}, {"v": 0}]
    assert (out["rows"]["home"]["total"], out["rows"]["away"]["total"]) == (7, 5)
    assert not out["rows"]["home"]["hammer_first"] and not out["rows"]["away"]["hammer_first"]
    assert out["title"] == "End by end" and out["meta"] == "8 ends · no extra end"
    assert out["note"] == "Bravo had hammer in the first end." and out["note_strong"] == "Bravo"
    assert [(i["kind"], i["text"]) for i in out["legend"]] == [
        ("hammer", "Hammer (last rock)"), ("mark", "Stolen end"), ("blank", "Blank end")]
    assert out["mark_word"] == "stolen end" and out["void_word"] == "not played" and out["blank_word"] == "blank end"
    assert out["hammer_word"] == "Hammer" and out["caption"] == "Points by end"


def test_a_concession_has_x_cells_a_not_played_key_and_a_meta_that_says_so():
    out = shown("conceded")["line_score"]
    assert out["meta"] == "Shook hands after 6 of 8 ends"
    assert out["rows"]["home"]["cells"][6:] == [{"v": None, "void": True}, {"v": None, "void": True}]
    assert out["rows"]["away"]["cells"][6:] == [{"v": None, "void": True}, {"v": None, "void": True}]
    assert not any(c.get("blank") for c in out["columns"])          # an X column is not a blank end
    assert out["legend"][-1] == {"kind": "x", "text": "Not played", "mark": "X"}
    assert all(set(c) <= {"v", *CELL_FLAGS} for row in out["rows"].values() for c in row["cells"])


def test_the_meta_for_each_way_a_game_ends():
    metas = {name: shown(name)["line_score"]["meta"] for name in (
        "clean", "clean-6-ends", "clean-10-ends", "conceded", "time-called", "time-called-tie", "extra-end-playoff",
        "two-extra-ends", "time-called-after-last-end", "extra-blank-time-called", "tie-regular-season")}
    assert metas == {
        "clean": "8 ends · no extra end", "clean-6-ends": "6 ends · no extra end", "clean-10-ends": "10 ends · no extra end",
        "conceded": "Shook hands after 6 of 8 ends", "time-called": "Time called after 7 of 8 ends",
        "time-called-tie": "Time called after 6 of 8 ends", "extra-end-playoff": "8 ends · extra end",
        "two-extra-ends": "8 ends · 2 extra ends", "time-called-after-last-end": "8 ends · no extra end · time called",
        "extra-blank-time-called": "8 ends · extra end · time called", "tie-regular-season": "8 ends · no extra end"}


def test_extra_ends_are_ee_columns_and_a_steal_in_an_extra_end_is_marked():
    out = shown("extra-end-playoff")["line_score"]
    assert [c["label"] for c in out["columns"]] == ["1", "2", "3", "4", "5", "6", "7", "8", "EE"]
    assert out["rows"]["home"]["cells"][-1] == {"v": 1, "won": True, "mark": True}      # Bravo kept the hammer through two blanks
    assert out["rows"]["away"]["cells"][-1] == {"v": 0, "hammer": True}
    assert (out["rows"]["home"]["total"], out["rows"]["away"]["total"]) == (5, 4)
    out = shown("two-extra-ends")["line_score"]
    assert [c["label"] for c in out["columns"]][-2:] == ["EE1", "EE2"]
    assert out["columns"][-2].get("blank") is True and not out["columns"][-1].get("blank")


def test_a_scoreless_game_is_all_blank_columns_and_the_hammer_stays():
    out = shown("all-blank")["line_score"]
    assert all(c.get("blank") for c in out["columns"])
    assert all(c.get("hammer") for c in out["rows"]["home"]["cells"]) and not any(c.get("hammer") for c in out["rows"]["away"]["cells"])
    assert not any(c.get("won") or c.get("mark") for row in out["rows"].values() for c in row["cells"])


def test_the_compact_line_score_on_the_card_has_no_hammer_cells_and_no_blank_shading():
    card = shown("clean")["card"]
    out = card["line_score"]
    assert out["title"] is None and out["meta"] is None and out["note"] is None and out["legend"] == []
    assert [c["label"] for c in out["columns"]] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert not any(c.get("blank") for c in out["columns"])
    assert not any("hammer" in c for row in out["rows"].values() for c in row["cells"])
    assert out["rows"]["away"]["hammer_first"] is True and out["rows"]["home"]["hammer_first"] is False
    assert out["rows"]["home"]["cells"][3] == {"v": 1, "won": True, "mark": True}
    assert card["note"] is None and card["strong"] is None and card["link_label"] == "Game" and card["meta_extra"] == []


def test_the_card_foot_says_how_a_game_stopped():
    assert shown("conceded")["card"]["meta_extra"] == ["Shook hands after 6"]
    assert shown("time-called")["card"]["meta_extra"] == ["Time called after 7"]
    assert shown("time-called-after-last-end")["card"]["meta_extra"] == []
    assert shown("extra-end-playoff")["card"]["meta_extra"] == []
    out = shown("conceded")["card"]["line_score"]
    assert out["rows"]["home"]["cells"][-1] == {"v": None, "void": True}


# ------------------------------------------------------------------ present: the numbers and the lineups

def test_the_game_in_numbers_has_the_mockup_rows_and_bold_cells():
    block = block_of(shown("clean"), "numbers")
    assert block["title"] == "The game in numbers" and block["corner"] == "This game"
    assert block["note"] == "A blank counts to the rink that had hammer and kept it."
    assert [(r["label"], r["cells"], r["key"], r["hot"]) for r in block["rows"]] == [
        ("Ends won", {"home": "4", "away": "3"}, "home", False),
        ("Stolen ends", {"home": "1", "away": "0"}, "home", True),
        ("Ends with hammer", {"home": "3", "away": "5"}, None, False),
        ("Scored with hammer", {"home": "3 of 3", "away": "3 of 5"}, "home", False),
        ("Blank ends", {"home": "0", "away": "1"}, None, False),
        ("Big ends (3+)", {"home": "1", "away": "0"}, "home", False)]


def test_a_level_row_has_no_bold_cell_and_no_steal_is_not_hot():
    block = block_of(shown("all-blank"), "numbers")
    rows = {r["label"]: r for r in block["rows"]}
    assert all(r["key"] is None and not r["hot"] for r in block["rows"])
    assert rows["Scored with hammer"]["cells"] == {"home": "0 of 8", "away": "0 of 0"}
    assert rows["Blank ends"]["cells"] == {"home": "8", "away": "0"}
    block = block_of(shown("steals-and-big-end"), "numbers")
    stolen = next(r for r in block["rows"] if r["label"] == "Stolen ends")
    assert stolen["cells"] == {"home": "0", "away": "2"} and stolen["key"] == "away" and stolen["hot"] is True


def test_the_roster_has_the_lineups_in_throwing_order_the_skip_bold_and_the_spare_marked():
    block = block_of(shown("clean"), "roster")
    assert block["title"] == "Lineups" and block["link_label"] == "Rink" and block["note"] == "In throwing order, as on the score card."
    assert [t["side"] for t in block["teams"]] == ["home", "away"]
    assert [(r["role"], r["player"], r["key"], r["spare_for"]) for r in block["teams"][0]["rows"]] == [
        ("Lead", "carol-d", False, None), ("Second", "ken-w", False, None), ("Vice", "linda-f", False, None),
        ("Skip", "doug-h", True, None)]
    assert [(r["role"], r["player"], r["key"], r["spare_for"]) for r in block["teams"][1]["rows"]] == [
        ("Lead", "pat-o", False, None), ("Second", "ron-m", False, "brian-s"), ("Vice", "joanne-t", False, None),
        ("Skip", "wayne-b", True, None)]


def test_a_three_player_rink_and_a_draft_spare_without_an_id_are_shorter_lists():
    block = block_of(shown("three-player-rink"), "roster")
    assert [r["role"] for r in block["teams"][0]["rows"]] == ["Lead", "Vice", "Skip"]
    block = block_of(shown("draft-with-name"), "roster")
    assert [r["role"] for r in block["teams"][1]["rows"]] == ["Lead", "Vice", "Skip"]


def test_a_league_with_no_lineups_has_no_roster_block():
    result = shown("lineups-none")
    assert [b["type"] for b in result["blocks"]] == ["numbers"]


def test_present_has_only_known_keys_blocks_and_flags_for_every_fixture_that_reads():
    for path in sorted(FIXTURES.glob("*.expected.json")):
        expected = json.loads(path.read_text(encoding="utf-8"))
        if not expected["reading"]:
            continue
        name = path.name[:-len(".expected.json")]
        result = shown(name)
        assert set(result) <= {"line_score", "card", "tiles", "blocks"}, name
        assert all(b["type"] in BLOCK_TYPES for b in result["blocks"]), name
        for ls in (result["line_score"], result["card"]["line_score"]):
            for row in ls["rows"].values():
                assert len(row["cells"]) == len(ls["columns"]), name
                assert all(set(c) <= {"v", *CELL_FLAGS} for c in row["cells"]), name
        assert result["tiles"] is None


# ------------------------------------------------------------------ the standings it asks of the core

def games_from(*names):
    return [StandingsGame(f"g{i}", "aa", "bb", reading_of(name), type=case_of(name)["fixture"]["game_type"],
                          file=f"games/g{i}.yml") for i, name in enumerate(names)]


def table_of(games, standings):
    """{team: every standings column's value}, whatever columns the league shows."""
    standings = {**standings, "columns": ["gp", "w", "l", "t", "otw", "otl", "pw", "pts", "pf", "pa", "diff"]}
    return {r["team"]: r["values"] for r in compute_standings(games, TEAMS, standings, regulation_periods=8).rows}


def defaults():
    return normalise_standings(sport_standings_defaults(SPORT.spec))


def test_a_win_is_two_points_a_tie_one_and_the_ends_are_worth_nothing():
    row = table_of(games_from("clean", "tie-regular-season"), defaults())
    assert (row["aa"]["w"], row["aa"]["t"], row["aa"]["pts"], row["bb"]["l"], row["bb"]["t"], row["bb"]["pts"]) == (1, 1, 3, 1, 1, 1)
    assert (row["aa"]["pf"], row["aa"]["pa"]) == (11, 9) and row["aa"]["diff"] == 2


def test_an_extra_end_win_is_a_full_win_and_the_extra_end_is_not_a_scheduled_end():
    row = table_of(games_from("extra-end-playoff", "clean"), defaults())      # the playoff game is not counted
    assert (row["aa"]["gp"], row["aa"]["w"], row["aa"]["pts"]) == (1, 1, 2)
    row = table_of(games_from("extra-end-always"), defaults())               # Bravo won 6-4 in an extra end
    assert (row["bb"]["w"], row["bb"]["otw"], row["bb"]["pts"], row["aa"]["l"], row["aa"]["otl"], row["aa"]["pts"]) == (1, 1, 2, 1, 1, 0)
    assert (row["bb"]["pf"], row["aa"]["pf"]) == (6, 4)
    assert (row["aa"]["pw"], row["bb"]["pw"]) == (3, 3)          # ends won in the scheduled ends only: the extra end is not one
    lines = reading_of("extra-end-always").team_lines
    assert (lines["home"]["ends_won"], lines["away"]["ends_won"]) == (3, 4)       # the team stat counts it


def test_a_conceded_game_is_a_normal_win_and_loss_with_the_score_as_it_stands():
    row = table_of(games_from("conceded"), defaults())
    assert (row["aa"]["w"], row["aa"]["pts"], row["bb"]["l"], row["aa"]["pf"], row["bb"]["pf"]) == (1, 2, 1, 8, 3)


def test_a_tied_playoff_game_is_the_cores_error_at_the_total_box():
    game = games_from("time-called-tie-playoff")[0]
    results, problems = game_results(game, defaults(), 8)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.final.home")]
    assert game.reading.score.final_at["home"] == problems[0].at


def test_with_ties_not_allowed_a_regular_season_tie_is_the_cores_error_at_the_total_box():
    standings = {**defaults(), "ties": False}
    results, problems = game_results(games_from("tie-regular-season")[0], standings, 8)
    assert results is None and [(p.level, p.at) for p in problems] == [("error", "sheet.final.home")]


def test_the_forfeit_is_one_to_nothing():
    row = table_of([StandingsGame("g1", "aa", "bb", None, forfeit="bb", file="games/g1.yml")], defaults())
    assert (row["aa"]["w"], row["aa"]["pts"], row["aa"]["pf"], row["bb"]["pf"], row["bb"]["pts"], row["aa"]["diff"]) == (1, 2, 1, 0, 0, 1)


def test_period_points_are_off_but_a_league_may_pay_for_ends_won():
    paid = {**defaults(), "period_points": 1}
    row = table_of(games_from("clean"), paid)
    assert row["aa"]["pts"] == 2 + 4 and row["bb"]["pts"] == 3        # 4 ends to Alpha, 3 to Bravo: blank ends pay nobody


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
                           ("float", 2.5), ("true", True), ("big", 99), ("big-text", "X" * 30), ("deep", {"a": [1]}),
                           ("capital-x", "X")):
            broken = copy.deepcopy(sheet)
            parent = get(broken, path[:-1])
            if how == "delete":
                if isinstance(parent, list):
                    del parent[path[-1]]
                else:
                    del parent[path[-1]]
            else:
                parent[path[-1]] = value
            yield f"{how} {path}", broken
    for path in walk(sheet):
        if isinstance(get(sheet, path), dict):
            broken = copy.deepcopy(sheet)
            get(broken, path)["zzz"] = 1
            yield f"unknown key under {path}", broken
    for value in ("hello", None, [], 3, {}, {"hammer": 1, "ends": 2, "extra": 3, "final": 4, "lineups": 5, "conceded": [1],
                                              "time_called": {}}):
        yield f"whole sheet {value!r}", value


@pytest.mark.parametrize("name", ["clean", "conceded", "two-extra-ends", "time-called"])
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


@pytest.mark.parametrize("name", ["clean", "conceded", "two-extra-ends"])
def test_a_sheet_that_check_accepts_can_always_be_read_and_presented(name):
    ctx = ctx_of(name)
    for what, broken in mutations(fixture_sheet(name)):
        problems = SPORT.rules.check(broken, ctx)
        if not any(p.level == "error" for p in problems):
            reading = call_sport("read", SPORT.rules.read, broken, ctx)       # raises InternalError if read cannot cope
            call_sport("present", SPORT.rules.present, reading, ctx)


def test_the_number_of_ends_is_an_option():
    sheet = fixture_sheet("clean")
    assert SPORT.rules.check(sheet, make_ctx()) == []
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(ends=6))} == {"ends.home", "ends.away"}
    assert {p.at for p in SPORT.rules.check(sheet, make_ctx(ends=10))} == {"ends.home", "ends.away"}
    assert SPORT.rules.check(fixture_sheet("clean-6-ends"), make_ctx(ends=6)) == []
    assert SPORT.rules.check(fixture_sheet("clean-10-ends"), make_ctx(ends=10)) == []
    for n in (4, 5, 7, 9):
        sheet = {"hammer": "home", "ends": {"home": [1] + [0] * (n - 1), "away": [0] * n}, "final": {"home": 1, "away": 0}}
        assert SPORT.rules.check(sheet, make_ctx(ends=n, lineups="none")) == [], n


def test_the_extra_end_rule_changes_only_the_extra_end_checks():
    level = fixture_sheet("level-playoff-no-extra")
    assert [p.at for p in SPORT.rules.check(level, make_ctx(game_type="playoff"))] == ["extra"]
    assert [p.at for p in SPORT.rules.check(level, make_ctx(game_type="regular", extra_end="always"))] == ["extra"]
    assert SPORT.rules.check(level, make_ctx(game_type="regular")) == []          # a tie
    extra = fixture_sheet("extra-end-playoff")
    assert SPORT.rules.check(extra, make_ctx(game_type="playoff")) == []
    assert SPORT.rules.check(extra, make_ctx(game_type="regular", extra_end="always")) == []
    assert [p.at for p in SPORT.rules.check(extra, make_ctx(game_type="regular"))] == ["extra"]
    assert SPORT.rules.check(fixture_sheet("clean"), make_ctx(extra_end="always")) == []


def test_lineups_none_changes_only_the_lineup_checks():
    sheet = fixture_sheet("clean")
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx(lineups="none"))] == ["lineups"]
    sheet.pop("lineups")
    assert SPORT.rules.check(sheet, make_ctx(lineups="none")) == []
    assert [p.at for p in SPORT.rules.check(sheet, make_ctx())] == ["lineups"]


def test_a_game_file_can_be_read_with_no_final_box_in_a_draft():
    sheet = fixture_sheet("clean")
    sheet.pop("final")
    ctx = make_ctx(folder="drafts")
    assert [(p.level, p.at) for p in SPORT.rules.check(sheet, ctx)] == [("warning", "final")]
    assert SPORT.rules.read(sheet, ctx).score.final == {"home": 7, "away": 5}
