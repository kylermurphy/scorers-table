"""The slo-pitch sample seasons (sports/slopitch/sample.py): season-level facts the spec promises (section 7), and
that the sample passes the rules under every option value. The contract test (test_sport_contract.py) already runs the
sample for every value of every `choice` option; these tests count what the seasons hold and try the number options
and some combinations too."""
import pytest

from scripts import make_sample
from scripts.core.sports import SPORTS_ROOT, load_sport

SPORT, PROBLEMS = load_sport("slopitch", SPORTS_ROOT, with_sample=True)
CURRENT = {"id": "sample-2026-27", "as_of": "2026-11-20"}
PAST = {"id": "sample-2025-26"}
LIMIT = 5


def season(which, **options):
    rules = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | options
    from scripts.core.config import normalise_standings, sport_standings_defaults
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    found = []
    make_sample.generate_season(SPORT, which, rules=rules, standings=standings, collect=found)
    return found


def totals(sheet):
    return {s: sum(v for v in sheet["runs"][s] if v != "X") for s in ("away", "home")}


def facts(found):
    """Counts over a season's sheets (finished games and the draft)."""
    out = dict.fromkeys("mercy mercy_x called walk_off x extras tie no_lines limit_box name_row home_run".split(), 0)
    for sheet, ctx, game in found:
        runs, total = sheet["runs"], totals(sheet)
        n = len(runs["away"])
        out["mercy"] += sheet.get("called") == "mercy"
        out["mercy_x"] += sheet.get("called") == "mercy" and runs["home"][-1] == "X"
        out["called"] += sheet.get("called") not in (None, "mercy")
        out["x"] += "X" in runs["home"]
        out["extras"] += n > 7
        out["tie"] += total["away"] == total["home"]
        if n == 7 and runs["home"][-1] != "X" and sum(runs["home"][:-1]) <= sum(runs["away"]) < total["home"]:
            out["walk_off"] += 1
        rows = [r for side in sheet.get("batting", {}).values() for r in side]
        out["no_lines"] += bool(rows) and all("ab" not in r for r in rows) and ctx.folder == "games"
        out["limit_box"] += any(v == LIMIT for side in runs.values() for v in side[:6])
        out["name_row"] += any("name" in r for r in rows)
        out["home_run"] += any(r.get("hr") for r in rows)
    return out


def test_the_name_pool_holds_every_player_and_spare():
    pool = len(make_sample.FIRST_NAMES) * len(make_sample.INITIALS)
    assert pool >= len(SPORT.sample.TEAMS) * SPORT.sample.PLAYERS_PER_TEAM + make_sample.SPARES


def test_the_league_is_the_made_up_one_of_the_design_system():
    assert SPORT.sample.LEAGUE_NAME == "Maple Park Slo-Pitch"
    assert [t[1] for t in SPORT.sample.TEAMS] == ["Sluggers", "Mudcats", "Dugout Dogs", "Line Drives", "Long Balls", "Bunters"]


@pytest.mark.parametrize("which", [CURRENT, PAST], ids=["current", "past"])
def test_each_season_shows_the_everyday_things_with_the_defaults(which):
    found = facts(season(which))
    for key in ("mercy", "called", "walk_off", "x", "tie", "no_lines", "limit_box", "home_run"):
        assert found[key], key
    assert found["mercy_x"] + facts(season(PAST if which is CURRENT else CURRENT))["mercy_x"] >= 1


def test_the_current_season_has_a_draft_with_a_batter_written_in_by_name():
    found = season(CURRENT)
    drafts = [s for s, ctx, _ in found if ctx.folder == "drafts"]
    assert len(drafts) == 1 and facts([(s, c, g) for s, c, g in found if c.folder == "drafts"])["name_row"] == 1


def test_the_past_season_has_a_playoff_game_in_extra_innings_and_none_in_the_regular_season():
    found = season(PAST)
    extras = [(s, c) for s, c, _ in found if len(s["runs"]["away"]) > 7]
    assert len(extras) >= 1 and all(c.game_type == "playoff" for _, c in extras)
    for sheet, ctx in extras:                                           # level after seven, level until the last inning
        away, home = sheet["runs"]["away"], sheet["runs"]["home"]
        assert sum(away[:7]) == sum(home[:7])
        assert all(away[i] == home[i] for i in range(7, len(away) - 1)) and away[-1] != home[-1]
    assert not any(len(s["runs"]["away"]) > 7 for s, c, _ in found if c.game_type == "regular")


def test_playoff_games_are_always_decided():
    for which in (CURRENT, PAST):
        assert all(totals(s)["away"] != totals(s)["home"] for s, c, _ in season(which) if c.game_type == "playoff")


def test_a_mercy_game_is_called_with_a_lead_of_fifteen_after_five_innings():
    seen = 0
    for which in (CURRENT, PAST):
        for sheet, ctx, _ in season(which):
            if sheet.get("called") == "mercy":
                seen += 1
                lead = abs(totals(sheet)["away"] - totals(sheet)["home"])
                assert lead >= 15 and len(sheet["runs"]["away"]) == 5
                assert "X" not in sheet["runs"]["away"]
    assert seen >= 2


def test_limit_innings_never_pass_the_limit_and_the_last_inning_is_open():
    over_limit = open_seventh = 0
    for which in (CURRENT, PAST):
        for sheet, ctx, _ in season(which):
            for side, boxes in sheet["runs"].items():
                over_limit += any(v != "X" and v > LIMIT for v in boxes[:6])
                open_seventh += len(boxes) >= 7 and boxes[6] != "X" and boxes[6] > LIMIT
    assert over_limit == 0 and open_seventh >= 1


def test_the_batting_lines_add_up_to_the_runs_and_the_h_box():
    for which in (CURRENT, PAST):
        for sheet, ctx, _ in season(which):
            for side, rows in sheet["batting"].items():
                assert 10 <= len(rows) <= 13
                lined = [r for r in rows if "ab" in r]
                if lined:
                    assert len(lined) == len(rows)
                    assert sum(r["r"] for r in lined) == sheet["totals"][side]["r"] == totals(sheet)[side]
                    assert sum(r["h"] for r in lined) == sheet["totals"][side]["h"]
                    assert sum(r["rbi"] for r in lined) <= sheet["totals"][side]["r"]
                    assert all(r["h"] <= r["ab"] and r["hr"] <= r["h"] for r in lined)


def test_a_game_has_lines_for_both_teams_or_for_neither():
    for which in (CURRENT, PAST):
        for sheet, ctx, _ in season(which):
            kinds = {all("ab" in r for r in rows) for rows in sheet["batting"].values()}
            assert len(kinds) == 1


def test_scores_are_in_the_low_teens_on_average():
    runs = [v for which in (CURRENT, PAST) for s, c, _ in season(which) if "called" not in s for v in totals(s).values()]
    assert 10 <= sum(runs) / len(runs) <= 16


OPTIONS = [{"innings": 3}, {"innings": 5}, {"innings": 6}, {"innings": 9}, {"run_limit": 0}, {"run_limit": 1}, {"run_limit": 3},
           {"run_limit": 8}, {"run_limit": 20}, {"open_innings": "none"}, {"open_innings": "none", "run_limit": 1},
           {"limit_play": "finish"}, {"limit_play": "finish", "open_innings": "none"},
           {"limit_play": "finish", "open_innings": "none", "run_limit": 1}, {"mercy_runs": 0}, {"mercy_runs": 8},
           {"mercy_runs": 30}, {"mercy_after": 1}, {"mercy_after": 3}, {"mercy_after": 9}, {"official_innings": 1},
           {"official_innings": 6}, {"official_innings": 9}, {"time_limit": 0}, {"extra_innings": 2}, {"extra_innings": 5},
           {"extra_innings": 2, "open_innings": "none", "run_limit": 2}, {"hr_limit": 1}, {"hr_limit": 10},
           {"batting": "none"}, {"batting": "order"}, {"batting": "every_game"}, {"team_hits": "none"},
           {"team_hits": "none", "batting": "none"}, {"team_errors": "kept"},
           {"team_hits": "none", "batting": "order", "team_errors": "kept"},
           {"innings": 9, "run_limit": 0, "mercy_runs": 0},
           {"innings": 3, "extra_innings": 3, "run_limit": 1, "open_innings": "none"}]


@pytest.mark.parametrize("options", OPTIONS, ids=lambda o: ",".join(f"{k}={v}" for k, v in o.items()))
def test_the_sample_passes_the_rules_under_every_option_value(options):
    """generate_season runs the sport's check on every sheet (warnings count) and raises on any problem."""
    assert season(CURRENT, **options) and season(PAST, **options)


@pytest.mark.parametrize("value", ["none", "order", "optional", "every_game"])
def test_the_batting_option_decides_what_the_sheet_keeps(value):
    for which in (CURRENT, PAST):
        for sheet, ctx, _ in season(which, batting=value):
            rows = [r for side in sheet.get("batting", {}).values() for r in side]
            if value == "none":
                assert "batting" not in sheet
            elif value == "order":
                assert rows and not any("ab" in r for r in rows)
            elif value == "every_game":
                assert rows and all("ab" in r for r in rows)


def test_the_h_and_e_boxes_follow_team_hits_and_team_errors():
    for sheet, _, _ in season(CURRENT):
        assert all(set(b) == {"r", "h"} for b in sheet["totals"].values())
    for sheet, _, _ in season(CURRENT, team_errors="kept", team_hits="none"):
        assert all(set(b) == {"r", "e"} for b in sheet["totals"].values())


def test_with_extra_innings_allowed_a_tie_is_played_out_level_and_a_playoff_game_is_still_decided():
    found = season(CURRENT, extra_innings=2)
    ties = [s for s, c, _ in found if totals(s)["away"] == totals(s)["home"]]
    assert ties and all(len(s["runs"]["away"]) == 9 for s in ties)
    assert all(totals(s)["away"] != totals(s)["home"] for s, c, _ in season(PAST, extra_innings=2) if c.game_type == "playoff")


def test_the_limit_option_moves_the_limit_innings():
    found = season(CURRENT, run_limit=3)
    assert all(v <= 3 for s, _, _ in found for boxes in s["runs"].values() for v in boxes[:6] if v != "X")
    assert any(v == 3 for s, _, _ in found for boxes in s["runs"].values() for v in boxes[:6])
    assert any(v > 5 for s, _, _ in season(CURRENT, run_limit=0) for boxes in s["runs"].values() for v in boxes if v != "X")


def test_a_game_that_cannot_be_called_is_played_out():
    """mercy_after at or past the last inning: no mercy game can be had, so none is written."""
    assert not any("called" in s and s["called"] == "mercy" for s, _, _ in season(CURRENT, mercy_after=9))
    assert not any("called" in s for s, _, _ in season(CURRENT, innings=3))


def test_the_sample_is_the_same_on_every_run():
    first = [sheet for sheet, _, _ in season(CURRENT)]
    assert first == [sheet for sheet, _, _ in season(CURRENT)]
