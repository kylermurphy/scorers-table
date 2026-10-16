"""sports/basketball/sample.py: every outcome under both `overtime` values, the quirks of a made-up season
(technicals, a flagrant foul, an overtime game, absent players, a sub written in by name on the draft)."""
import copy
import random
from dataclasses import replace

import pytest

from scripts import make_sample
from scripts.core.config import normalise_standings, sport_standings_defaults
from scripts.core.model import SampleGame, SportContext, Team
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, load_sport

SPORT, PROBLEMS = load_sport("basketball", SPORTS_ROOT, with_sample=True)
assert PROBLEMS == []
OUTCOMES = ("win_home", "win_away", "tie", "ot")


def context(overtime, game_type="regular", folder="games"):
    rng = random.Random(1)
    teams = [Team(i, n, c) for i, n, c in SPORT.sample.TEAMS]
    players, roster, spares = make_sample.make_players(rng, teams, SPORT.sample.PLAYERS_PER_TEAM)
    options = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | {"overtime": overtime}
    ctx = SportContext(sport=SPORT.spec, options=options, teams={t.id: t for t in teams},
                       players={p.id: p for p in players}, sides={"home": "rapids", "away": "herons"},
                       game_type=game_type, folder=folder)
    return ctx, {"home": roster["rapids"][:7], "away": roster["herons"][:6] + spares[:1]}


def draw(seed, outcome, overtime, **kw):
    ctx, played = context(overtime, **kw)
    game = SampleGame(f"2026-11-05-{seed}", played, outcome)
    sheet = SPORT.sample.sheet(random.Random(seed), game, ctx)
    reading = call_sport("read", SPORT.rules.read, sheet, ctx)
    return sheet, reading, call_sport("check", SPORT.rules.check, sheet, ctx), game, ctx


@pytest.mark.parametrize("overtime", ["overtime", "none"])
@pytest.mark.parametrize("game_type", ["regular", "playoff"])
@pytest.mark.parametrize("outcome", OUTCOMES)
def test_every_outcome_passes_the_checks_under_both_overtime_values(outcome, overtime, game_type):
    for seed in range(12):
        sheet, reading, problems, _, _ = draw(seed, outcome, overtime, game_type=game_type)
        assert problems == [], (seed, problems)
        final = reading.score.final
        if game_type == "playoff":
            assert final["home"] != final["away"], "a playoff game never ends tied"
        elif outcome in ("win_home", "win_away"):
            assert (final["home"] > final["away"]) == (outcome == "win_home") and final["home"] != final["away"]
            assert reading.score.decided_in == "regulation"
        elif overtime == "none":                              # a tie, or "ot" bent to a tie: level, no overtime boxes
            assert final["home"] == final["away"] and reading.score.decided_in == "regulation" and not reading.score.extra
            assert sheet["boxes"]["home"]["ot"] is None
        elif outcome == "ot":
            assert final["home"] != final["away"] and reading.score.decided_in == "overtime"
        else:                                                 # a tie with overtime: still level after it
            assert final["home"] == final["away"] and reading.score.decided_in == "overtime" and reading.score.extra


def test_an_overtime_game_is_level_after_the_fourth_quarter_and_fills_both_ot_boxes():
    sheet, reading, problems, _, _ = draw(3, "ot", "overtime")
    assert problems == []
    boxes = sheet["boxes"]
    assert boxes["home"]["q4"] == boxes["away"]["q4"] and boxes["home"]["ot"] == boxes["home"]["final"] > boxes["home"]["q4"]
    assert reading.score.extra["home"][0] > 0 and reading.score.extra["away"][0] > 0


def test_a_players_points_come_from_the_running_score_and_free_throws_from_the_circles():
    sheet, reading, _, _, _ = draw(5, "win_home", "overtime")
    for side in ("home", "away"):
        lines = [ln for ln in reading.lines if ln.side == side]
        assert sum(ln.counts["pts"] for ln in lines) == reading.score.final[side]    # every row has a player id
        for ln in lines:
            assert ln.counts["ftm"] <= ln.counts["fta"] and ln.counts["ftm"] <= ln.counts["pts"]


def test_a_draft_has_a_sub_written_in_by_name_with_a_warning_and_no_error():
    found = 0
    for seed in range(8):
        sheet, _, problems, _, _ = draw(seed, "win_home", "overtime", folder="drafts")
        rows = [r for side in sheet["players"].values() for r in side]
        names = [r for r in rows if "player" not in r]
        assert len(names) <= 1
        assert not [p for p in problems if p.level == "error"], problems
        if names:
            found += 1
            assert [p.level for p in problems] == ["warning"] and problems[0].at.endswith(".player")
    assert found
    sheet, _, problems, _, _ = draw(2, "win_home", "overtime")
    assert all("name" not in r for side in sheet["players"].values() for r in side) and problems == []


def test_the_sample_changes_nothing_it_is_given_and_repeats_itself():
    ctx, played = context("overtime")
    game = SampleGame("2026-11-12-1", played, "ot")
    before = copy.deepcopy((ctx, game))
    first = SPORT.sample.sheet(random.Random(4), game, ctx)
    assert (ctx, game) == before and first == SPORT.sample.sheet(random.Random(4), game, ctx)


def test_a_player_with_no_number_in_players_yml_still_gets_a_unique_jersey_on_the_sheet():
    ctx, played = context("overtime")
    nameless = next(p for p in ctx.players.values() if p.team == "rapids" and p.number is None)
    played["home"] = [*played["home"], nameless.id] if nameless.id not in played["home"] else played["home"]
    game = SampleGame("2026-11-12-2", played, "win_home")
    sheet = SPORT.sample.sheet(random.Random(8), game, ctx)
    assert call_sport("check", SPORT.rules.check, sheet, ctx) == []
    nums = [r["num"] for r in sheet["players"]["home"]]
    assert len(nums) == len(set(map(str, nums)))


@pytest.fixture(scope="module")
def season():
    rules = {key: opt["default"] for key, opt in SPORT.spec["options"].items()}
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    return make_sample.generate_season(SPORT, {"id": "sample-2026-27", "as_of": "2026-11-20"}, rules=rules, standings=standings)


def test_the_sample_season_has_technicals_a_flagrant_foul_absent_players_and_a_spare(season):
    games = [parse_yaml(t) for n, t in season.items() if n.startswith("games/")]
    sheets = [g["sheet"] for g in games if "sheet" in g]
    rows = [r for s in sheets for side in s["players"].values() for r in side]
    assert any(r.get("tech") for r in rows)
    assert any(n.get("kind") == "flagrant" for s in sheets for n in s.get("notes", []))
    assert any(r["here"] is False for r in rows)
    spares = {p["id"] for p in parse_yaml(season["players.yml"]) if p.get("sub")}
    assert spares and all(r.get("player") not in spares or r["here"] for r in rows)


def test_the_sample_season_scores_look_like_basketball(season):
    for text in (t for n, t in season.items() if n.startswith("games/")):
        game = parse_yaml(text)
        if "sheet" in game:
            for box in game["sheet"]["boxes"].values():
                assert 30 <= box["final"] <= 120
