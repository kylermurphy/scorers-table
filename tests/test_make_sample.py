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


# ------------------------------------------------------------------ the optional constants of sample.py (E11)

EXTRA_SPORTS = Path(__file__).resolve().parent / "fixtures" / "sports" / "_extra"


def rinks():
    """The throwaway sport (tests/fixtures/sports/_extra/rinks): 4 teams, 3 players a team, NUMBERS False,
    POSITIONS lead/second/skip, SURFACES A/B, TIMES 18:30/20:45 and its own NOTES."""
    sport, problems = load_sport("rinks", EXTRA_SPORTS, with_sample=True)
    assert problems == [], problems
    rules = {key: opt["default"] for key, opt in sport.spec["options"].items()}
    return sport, rules, normalise_standings(sport_standings_defaults(sport.spec))


def schedule(files):
    return list(csv.DictReader(io.StringIO(files["schedule.csv"])))


def test_the_constants_of_a_sport_are_used():
    sport, rules, standings = rinks()
    files = make_sample.generate_season(sport, THIS, rules=rules, standings=standings)
    rows = schedule(files)
    regular = [r for r in rows if r["type"] == "regular"]
    assert {r["surface"] for r in regular} == {"A", "B"}
    assert {(r["surface"], r["time"]) for r in regular} == {("A", "18:30"), ("B", "20:45")}
    assert [(r["surface"], r["time"]) for r in rows if r["type"] == "playoff"] == [
        ("A", "18:30"), ("B", "20:45"), ("A", "18:30")]
    players = parse_yaml(files["players.yml"])
    regulars = [p for p in players if p.get("team")]
    assert len(regulars) == 3 * 4 and not any("number" in p for p in players)
    for team in sport.sample.TEAMS:
        assert [p["position"] for p in regulars if p["team"] == team[0]] == ["lead", "second", "skip"]
    assert not any("position" in p for p in players if not p.get("team"))
    texts = {n["text"] for name, t in files.items() if name.startswith("games/")
             for n in (parse_yaml(t).get("notes") or [])}
    assert texts <= set(sport.sample.NOTES)


def test_without_the_constants_the_defaults_are_the_old_ones():
    """The stub says only PLAYERS_PER_TEAM: courts 1, 2, the two draw times, jersey numbers with a 00, no position."""
    sport, rules, standings = sport_and_settings("stub")
    for name in ("TIMES", "SURFACES", "NUMBERS", "POSITIONS", "NOTES"):
        assert not hasattr(sport.sample, name)
    files = make_sample.generate_season(sport, THIS, rules=rules, standings=standings)
    regular = [r for r in schedule(files) if r["type"] == "regular"]
    assert {(r["surface"], r["time"]) for r in regular} == {("1", "19:00"), ("2", "20:15")}
    players = parse_yaml(files["players.yml"])
    assert any(p.get("number") == "00" for p in players) and not any("position" in p for p in players)
    assert sum(1 for p in players if p.get("team") and "number" not in p) == len(sport.sample.TEAMS)   # the last of each


def test_make_players_without_numbers_or_with_positions():
    import random
    teams = [make_sample.Team("a", "Alpha", "ALP"), make_sample.Team("b", "Bravo", "BRA")]
    players, roster, spares = make_sample.make_players(random.Random(1), teams, 3, numbers=False,
                                                       positions=["lead", "skip"])
    assert [p.number for p in players] == [None] * len(players)
    assert [p.position for p in players if p.team == "a"] == ["lead", "skip", None]      # fewer positions than players
    assert len(roster["a"]) == 3 and len(spares) == make_sample.SPARES
    numbered, _, _ = make_sample.make_players(random.Random(1), teams, 3)
    assert numbered[0].number == "00" and numbered[2].number is None and numbered[1].number is not None


def test_basketball_players_are_unchanged_by_the_new_arguments():
    """The draw order of the random numbers is what keeps the committed sample byte for byte the same."""
    import random
    teams = [make_sample.Team("a", "Alpha", "ALP"), make_sample.Team("b", "Bravo", "BRA")]
    assert make_sample.make_players(random.Random(5), teams, 8) == make_sample.make_players(
        random.Random(5), teams, 8, numbers=True, positions=None)


@pytest.mark.parametrize("name, value, message", [
    ("TIMES", ["7pm"], "TIMES"), ("TIMES", [], "TIMES"), ("SURFACES", "AB", "SURFACES"), ("SURFACES", ["A", ""], "SURFACES"),
    ("NUMBERS", "no", "NUMBERS"), ("POSITIONS", ["lead", "vice"], "does not list"), ("NOTES", [3], "NOTES"),
    ("SURFACES", ["A"], "names 1 sheets"),
])
def test_a_bad_constant_stops_the_script_with_its_name(monkeypatch, name, value, message):
    sport, rules, standings = rinks()
    monkeypatch.setattr(sport.sample, name, value)
    with pytest.raises(make_sample.SampleError, match=message):
        make_sample.generate_season(sport, THIS, rules=rules, standings=standings)


def test_positions_for_a_sport_without_any_stop_the_script(monkeypatch):
    sport, rules, standings = sport_and_settings("stub")
    monkeypatch.setattr(sport.sample, "POSITIONS", ["lead"], raising=False)
    with pytest.raises(make_sample.SampleError, match="lists no positions"):
        make_sample.generate_season(sport, THIS, rules=rules, standings=standings)


def test_a_sport_without_a_surface_word_ignores_the_surfaces():
    sport, rules, standings = rinks()
    spec = {**sport.spec, "words": {**sport.spec["words"], "surface": None}}
    files = make_sample.generate_season(make_sample.SportDef(sport.id, sport.folder, spec, sport.rules, sport.sample),
                                        THIS, rules=rules, standings=standings)
    assert {r["surface"] for r in schedule(files)} == {""}


def test_one_draw_time_is_enough(monkeypatch):
    sport, rules, standings = rinks()
    monkeypatch.setattr(sport.sample, "TIMES", ["19:30"])
    rows = schedule(make_sample.generate_season(sport, THIS, rules=rules, standings=standings))
    assert {r["time"] for r in rows} == {"19:30"}
