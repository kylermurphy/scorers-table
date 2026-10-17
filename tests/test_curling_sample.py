"""The curling sample writer (sports/curling/sample.py): every outcome it can be asked for, under every value of
the league's `ends`, `extra_end` and `lineups` settings, and the committed sample seasons' one-of-everything.
The generic checks (a season that passes, the same on two runs, paths, drafts) are in test_sport_contract.py."""
import random
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from scripts import make_sample
from scripts.core.config import normalise_standings, sport_standings_defaults
from scripts.core.model import Player, SampleGame, SportContext, Team
from scripts.core.problems import call_sport
from scripts.core.sports import SPORTS_ROOT, load_sport

SPORT, PROBLEMS = load_sport("curling", SPORTS_ROOT, with_sample=True)
CONTEXT = yaml.safe_load((Path(__file__).resolve().parent.parent / "sports" / "curling" / "fixtures" / "context.yml").read_text(encoding="utf-8"))
TEAMS = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in CONTEXT["teams"]}
PLAYERS = {p["id"]: Player(p["id"], p["name"], p["team"], None, p.get("sub", False), p.get("position"))
           for p in CONTEXT["players"]}
FOUR = {"home": ["carol-d", "ken-w", "linda-f", "doug-h"], "away": ["pat-o", "brian-s", "joanne-t", "wayne-b"]}
WITH_SPARE = {"home": FOUR["home"] + ["ron-m"], "away": FOUR["away"]}
SEASONS = [{"id": "sample-2026-27", "as_of": "2026-11-20"}, {"id": "sample-2025-26"}]


def ctx_of(game_type="regular", folder="games", **options):
    opts = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | options
    return SportContext(sport=SPORT.spec, options=opts, teams=TEAMS, players=PLAYERS, sides={"home": "aa", "away": "bb"},
                        game_type=game_type, folder=folder)


def test_the_sample_loads():
    assert PROBLEMS == [] and SPORT is not None


@pytest.mark.parametrize("ends", [4, 6, 8, 10])
@pytest.mark.parametrize("extra_end", ["playoffs", "always"])
@pytest.mark.parametrize("game_type", ["regular", "playoff"])
@pytest.mark.parametrize("lineups", ["recorded", "none"])
def test_every_outcome_passes_the_checks_and_comes_out_as_asked(ends, extra_end, game_type, lineups):
    ctx = ctx_of(game_type, ends=ends, extra_end=extra_end, lineups=lineups)
    extra_allowed = game_type == "playoff" or extra_end == "always"
    for outcome in ("win_home", "win_away", "tie", "ot"):
        for n in range(12):
            game = SampleGame(f"2026-11-{n + 1:02d}-1", WITH_SPARE if n % 3 == 0 else FOUR, outcome)
            sheet = SPORT.sample.sheet(random.Random(f"{outcome}{n}"), game, ctx)
            assert call_sport("check", SPORT.rules.check, sheet, ctx) == [], (outcome, sheet)
            assert ("lineups" in sheet) == (lineups == "recorded")
            reading = call_sport("read", SPORT.rules.read, sheet, ctx)
            call_sport("present", SPORT.rules.present, reading, ctx)
            final = reading.score.final
            if outcome == "win_home":
                assert final["home"] > final["away"]
            elif outcome == "win_away":
                assert final["away"] > final["home"]
            elif extra_allowed:                          # level after the last end: the extra ends decide it
                assert "extra" in sheet and final["home"] != final["away"]
            else:                                        # a regular-season game with no extra end is a tie
                assert "extra" not in sheet and final["home"] == final["away"]
            if "extra" in sheet:
                assert extra_allowed
            assert len(sheet["ends"]["home"]) == ends == len(sheet["ends"]["away"])
            assert all(v in ("X", *range(9)) for side in sheet["ends"].values() for v in side)


def test_a_draft_may_write_a_spare_in_by_name_and_the_rules_only_warn():
    ctx = ctx_of(folder="drafts")
    named = 0
    for n in range(12):
        game = SampleGame(f"2026-11-{n + 1:02d}-1", FOUR, "win_home")
        sheet = SPORT.sample.sheet(random.Random(n), game, ctx)
        problems = call_sport("check", SPORT.rules.check, sheet, ctx)
        assert not [p for p in problems if p.level == "error"]
        named += any("name" in row for rows in sheet["lineups"].values() for row in rows)
    assert named


def test_a_spare_takes_the_place_of_a_regular_and_never_the_skip():
    ctx = ctx_of()
    for n in range(20):
        sheet = SPORT.sample.sheet(random.Random(n), SampleGame(f"2026-11-{n + 1:02d}-1", WITH_SPARE, "win_home"), ctx)
        rows = sheet["lineups"]["home"]
        assert [r["position"] for r in rows] == ["lead", "second", "vice", "skip"]
        spare = [r for r in rows if r["player"] == "ron-m"]
        assert len(spare) == 1 and spare[0]["position"] != "skip" and spare[0]["spare_for"] in FOUR["home"]
        assert spare[0]["spare_for"] not in [r["player"] for r in rows]


def test_the_sample_does_not_change_what_it_is_given():
    ctx, game = ctx_of(), SampleGame("2026-11-05-1", WITH_SPARE, "tie")
    before = (replace(game), ctx, {k: list(v) for k, v in game.players.items()})
    SPORT.sample.sheet(random.Random(1), game, ctx)
    assert game.players == before[2] and ctx == before[1]


# ------------------------------------------------------------------ the committed sample seasons

def season_games(season, **choose):
    rules = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | choose
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    files = make_sample.generate_season(SPORT, season, rules=rules, standings=standings)
    return {n: yaml.safe_load(t) for n, t in files.items() if n.startswith(("games/", "drafts/"))}


def sheets(games):
    return [g["sheet"] for g in games.values() if "sheet" in g]


@pytest.mark.parametrize("season", SEASONS, ids=lambda s: s["id"])
def test_a_sample_season_has_steals_blanks_big_ends_concessions_time_called_and_spares(season):
    games = season_games(season)
    all_sheets = sheets(games)
    boxes = [int(v) for s in all_sheets for side in s["ends"].values() for v in side if v != "X"]
    assert max(boxes) >= 3 and boxes.count(0) > boxes.count(1)          # most boxes are 0 (a rink scores in one end in two)
    assert sum(1 for s in all_sheets if "conceded" in s) >= 1
    assert sum(1 for s in all_sheets if "time_called" in s) >= 1
    assert any("spare_for" in row for s in all_sheets for side in s["lineups"].values() for row in side)
    assert all(len(row) <= 4 for s in all_sheets for row in s["lineups"].values())
    assert all(row["position"] in ("lead", "second", "vice", "skip") for s in all_sheets for side in s["lineups"].values()
               for row in side)


def test_the_past_season_has_an_extra_end_and_the_current_one_a_tie():
    past = sheets(season_games(SEASONS[1]))
    assert any("extra" in s for s in past)
    now = sheets(season_games(SEASONS[0]))
    assert not any("extra" in s for s in now)                           # no playoff game is played yet
    assert any(s["final"]["home"] == s["final"]["away"] for s in now)   # a regular-season tie


def test_with_extra_end_always_a_regular_season_season_has_extra_ends():
    assert any("extra" in s for s in sheets(season_games(SEASONS[0], extra_end="always")))
