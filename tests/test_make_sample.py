"""scripts/make_sample.py: the playoff draw, and a draft that keeps a warning. The contract every sample must keep
is in test_sport_contract.py; basketball's own sheets are in test_basketball_sample.py."""
import csv
import io
from pathlib import Path

import pytest

from scripts import make_sample
from scripts.core.config import normalise_standings, sport_standings_defaults
from scripts.core.model import Problem
from scripts.core.sports import SPORTS_ROOT, load_sport
from scripts.core.problems import parse_yaml

PAST = {"id": "sample-2025-26"}
THIS = {"id": "sample-2026-27", "as_of": "2026-11-20"}


def sport_and_settings(sport_id):
    sport, problems = load_sport(sport_id, SPORTS_ROOT, with_sample=True)
    assert problems == [], problems
    rules = {key: opt["default"] for key, opt in sport.spec["options"].items()}
    return sport, rules, normalise_standings(sport_standings_defaults(sport.spec))


def playoff_rows(files):
    rows = list(csv.DictReader(io.StringIO(files["schedule.csv"])))
    return {r["round"] + str(i): r for i, r in enumerate(r for r in rows if r["type"] == "playoff")}


@pytest.mark.parametrize("sport_id", ["stub", "basketball"])
def test_a_semifinal_winner_is_never_drawn_into_the_other_semifinal(sport_id):
    """The seeds are fixed when the playoffs start. Counting playoff wins in them let an upset winner of
    semifinal 1 climb into semifinal 2, and the final became one team against itself (seen on many seeds)."""
    sport, rules, standings = sport_and_settings(sport_id)
    for n in range(8):
        files = make_sample.generate_season(sport, PAST, rules=rules, standings=standings, seed=f"seed-{n}")
        sf1, sf2, final = playoff_rows(files).values()
        assert len({sf1["home"], sf1["away"], sf2["home"], sf2["away"]}) == 4, (n, sf1, sf2)
        assert final["home"] != final["away"], (n, final)
        assert final["home"] in (sf1["home"], sf1["away"]) and final["away"] in (sf2["home"], sf2["away"]), n


def test_seeds_come_from_regular_season_wins_only_and_ties_go_by_roster_order():
    ids = ["a", "b", "c", "d"]
    assert make_sample.seed_order(ids, {"a": 1.0, "b": 3.0, "c": 3.0, "d": 0.5}) == ["b", "c", "a", "d"]


def test_resolving_a_semifinal_does_not_depend_on_what_the_other_one_did():
    row = lambda slot: make_sample.Row("x", None, "19:00", "1st", "4th", type="playoff", slot=slot)   # noqa: E731
    seeds = ["a", "b", "c", "d"]
    sf1, sf2 = row("sf1"), row("sf2")
    make_sample._resolve_playoff_teams(sf1, seeds, {}, 4)
    make_sample._resolve_playoff_teams(sf2, seeds, {"sf1": "d"}, 4)       # the 4th seed won semifinal 1
    assert (sf1.home, sf1.away, sf2.home, sf2.away) == ("a", "d", "b", "c")
    final = row("final")
    make_sample._resolve_playoff_teams(final, seeds, {"sf1": "d", "sf2": "b"}, 4)
    assert (final.home, final.away) == ("d", "b")


def test_playoff_rows_stay_placeholders_until_the_playoffs_begin():
    sport, rules, standings = sport_and_settings("basketball")
    files = make_sample.generate_season(sport, THIS, rules=rules, standings=standings)
    assert [(r["home"], r["away"]) for r in playoff_rows(files).values()] == [
        ("1st", "4th"), ("2nd", "3rd"), ("Winner SF1", "Winner SF2")]


def test_a_draft_may_keep_a_warning_but_not_an_error(monkeypatch):
    """The draft is never built; a sport's sample can leave it a warning (basketball's sub written in by name)."""
    sport, rules, standings = sport_and_settings("basketball")
    real_check = sport.rules.check

    def with_problem(level):
        def check(sheet, ctx):
            extra = [Problem(level, "players", "made up for the test")] if ctx.folder == "drafts" else []
            return real_check(sheet, ctx) + extra
        return check

    monkeypatch.setattr(sport.rules, "check", with_problem("warning"))
    files = make_sample.generate_season(sport, THIS, rules=rules, standings=standings)
    assert any(n.startswith("drafts/") for n in files)
    monkeypatch.setattr(sport.rules, "check", with_problem("error"))
    with pytest.raises(make_sample.SampleError, match="made up for the test"):
        make_sample.generate_season(sport, THIS, rules=rules, standings=standings)


def test_a_finished_sheet_with_a_warning_still_stops_the_script(monkeypatch):
    sport, rules, standings = sport_and_settings("basketball")
    real_check = sport.rules.check
    monkeypatch.setattr(sport.rules, "check", lambda sheet, ctx: real_check(sheet, ctx) + (
        [Problem("warning", "players", "made up for the test")] if ctx.folder == "games" else []))
    with pytest.raises(make_sample.SampleError, match="made up for the test"):
        make_sample.generate_season(sport, THIS, rules=rules, standings=standings)


def test_the_basketball_draft_has_a_name_only_sub():
    sport, rules, standings = sport_and_settings("basketball")
    files = make_sample.generate_season(sport, THIS, rules=rules, standings=standings)
    draft = parse_yaml(next(t for n, t in files.items() if n.startswith("drafts/")))
    rows = [r for side in draft["sheet"]["players"].values() for r in side]
    subs = [r for r in rows if "player" not in r]
    assert len(subs) == 1 and subs[0]["name"] and subs[0]["here"] is True
