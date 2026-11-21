"""The hockey sample seasons (sports/hockey/sample.py): season-level facts the spec promises (section 7), and that the
sample passes the rules under every overtime option. The contract test (test_sport_contract.py) already runs the
sample for every value of every `choice` option; these tests count what the seasons hold."""
import pytest

from scripts import make_sample
from scripts.core.sports import SPORTS_ROOT, load_sport

SPORT, PROBLEMS = load_sport("hockey", SPORTS_ROOT, with_sample=True)
CURRENT = {"id": "sample-2026-27", "as_of": "2026-11-20"}
PAST = {"id": "sample-2025-26"}


def season(which, **options):
    rules = {key: opt["default"] for key, opt in SPORT.spec["options"].items()} | options
    from scripts.core.config import normalise_standings, sport_standings_defaults
    standings = normalise_standings(sport_standings_defaults(SPORT.spec))
    found = []
    make_sample.generate_season(SPORT, which, rules=rules, standings=standings, collect=found)
    return found


def goals_of(sheet):
    return sheet["goals"]


def facts(found):
    """Counts over a season's sheets."""
    out = dict.fromkeys("shutout ot_win so two_goalies spare_in_net bench ps en pp sh major cut tie ot2".split(), 0)
    for sheet, ctx, game in found:
        score, rows = sheet["score"], sheet["goals"]
        home, away = score["home"], score["away"]
        out["tie"] += home["final"] == away["final"]
        out["so"] += home["so"] is not None
        out["ot_win"] += any(not isinstance(g["period"], int) for g in rows)
        out["ot2"] += any(g["period"] == "OT2" for g in rows)
        out["shutout"] += any(len(sheet["goalies"][s]) == 1 and sheet["goalies"][s][0]["ga"] == 0 and
                              not any(g["side"] != s and not g.get("en") for g in rows) for s in ("home", "away"))
        out["two_goalies"] += any(len(r) == 2 for r in sheet["goalies"].values())
        out["bench"] += any(p["num"] == "bench" for p in sheet["penalties"])
        out["ps"] += any(g.get("ps") for g in rows)
        out["en"] += any(g.get("en") for g in rows)
        out["pp"] += sum(g.get("strength") == "PP" for g in rows)
        out["sh"] += sum(g.get("strength") == "SH" for g in rows)
        out["major"] += any(p["minutes"] >= 5 for p in sheet["penalties"])
        out["cut"] += (not home["periods"][-1] and not away["periods"][-1]
                       and abs(home["final"] - away["final"]) >= 5 and not home["ot"])
        for side in ("home", "away"):
            by_num = {r["num"]: r.get("player") for r in sheet["roster"][side]}
            for row in sheet["goalies"][side]:
                player = ctx.players.get(by_num[row["num"]])
                out["spare_in_net"] += bool(player and player.team != ctx.sides[side])
    return out


def test_the_name_pool_holds_every_player_and_spare():
    pool = len(make_sample.FIRST_NAMES) * len(make_sample.INITIALS)
    assert pool >= len(SPORT.sample.TEAMS) * SPORT.sample.PLAYERS_PER_TEAM + make_sample.SPARES


def test_the_current_season_shows_the_everyday_things_with_the_defaults():
    found = facts(season(CURRENT))
    for key in ("shutout", "two_goalies", "bench", "ps", "en", "pp", "sh", "cut", "tie"):
        assert found[key], key
    assert found["so"] == 0                       # the defaults play no shootout: ties are ties
    # a spare in net depends on who dressed (make_sample draws that): the two seasons together have one
    assert found["spare_in_net"] + facts(season(PAST))["spare_in_net"] >= 1


def test_the_past_season_has_a_playoff_overtime_win_with_the_defaults():
    found = facts(season(PAST))
    assert found["ot_win"] >= 1 and found["so"] == 0 and found["major"] >= 1


@pytest.mark.parametrize("mode", ["overtime", "shootout", "shootout_only"])
def test_every_overtime_option_passes_and_a_shootout_appears_where_it_is_played(mode):
    seen = {}
    for which in (CURRENT, PAST):
        for key, n in facts(season(which, overtime=mode)).items():
            seen[key] = seen.get(key, 0) + n
    assert (seen["so"] > 0) == (mode != "overtime")
    if mode != "shootout_only":
        assert seen["ot_win"] > 0


def test_a_season_with_a_playoff_shootout_and_shots_recorded_passes():
    found = season(PAST, playoff_overtime="shootout", overtime="shootout", goalie_shots="recorded")
    assert all("shots" in row for sheet, _, _ in found for rows in sheet["goalies"].values() for row in rows)
    assert facts(found)["so"] > 0


@pytest.mark.parametrize("options", [{"clock": "remaining"}, {"periods": 2}, {"periods": 4, "period_minutes": 10},
                                     {"overtime_minutes": 3, "shootout_rounds": 5, "overtime": "shootout"},
                                     {"goal_cap": 2}])
def test_the_sample_also_passes_other_option_values(options):
    assert season(CURRENT, **options) and season(PAST, **options)


def test_the_sample_is_the_same_on_every_run():
    first = [sheet for sheet, _, _ in season(CURRENT)]
    assert first == [sheet for sheet, _, _ in season(CURRENT)]
