"""Tests for scripts/core/loader.py: seasons.yml rules, teams, players, schedule.csv, the game file envelope
(each check with its exact path), the sport's check and read, drafts never opened, an empty current season.

They use the fake sports in tests/fixtures/sports/ (`tiny`, with `rules` swapped for small fakes where a test
needs to see what the loader passes in) and the fixture data in tests/fixtures/data/valid/ or files written
into tmp_path. Nothing here depends on sports/ or on sample data.
"""
import datetime as dt
import shutil
import types
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.core.config import build_league
from scripts.core.loader import (
    LoadedData, choose_active, load_data, shown_seasons, work_out_byes,
)
from scripts.core.model import Line, Problem, Reading, Score
from scripts.core.problems import InternalError

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "data" / "valid"
TODAY = dt.date(2026, 11, 20)

TEAMS = "- {id: otters, name: Otters, code: OTT}\n- {id: ravens, name: Ravens, code: RAV}\n- {id: moose, name: Moose, code: MOO}\n"
PLAYERS = "- {id: ann-b, name: Ann B., team: otters, number: 7}\n- {id: tom-w, name: Tom W., team: ravens}\n"
SCHEDULE = ("game_id,date,time,home,away\n"
            "2026-11-05-1,2026-11-05,19:00,otters,ravens\n"
            "2026-11-12-1,2026-11-12,19:00,moose,otters\n")
GAME = ("game_id: 2026-11-05-1\nstatus: final\nhome: otters\naway: ravens\nchecked_by: Lee M.\n"
        "sheet:\n  final: {home: 21, away: 20}\n")
S1 = "data/s1"


# ------------------------------------------------------------------ helpers

class Data:
    """A throwaway repository: tmp_path/data/seasons.yml and one season folder `s1` (current)."""

    def __init__(self, root: Path, *, teams=TEAMS, players=PLAYERS, schedule=SCHEDULE, seasons=None):
        self.root = root
        self.put("seasons.yml", seasons if seasons is not None else "- {id: s1, label: One, current: true}\n")
        (self.root / "data" / "s1").mkdir(parents=True, exist_ok=True)
        for name, text in (("teams.yml", teams), ("players.yml", players), ("schedule.csv", schedule)):
            if text is not None:
                self.put(f"s1/{name}", text)

    def put(self, rel: str, text: str | bytes) -> Path:
        path = self.root / "data" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path

    def game(self, name: str, text: str = GAME) -> Path:
        return self.put(f"s1/games/{name}.yml", text)


def league_for(sports_root, *, sample_data=False, sport="tiny", **extra):
    raw = {"name": "Example League", "sport": sport, "timezone": "UTC", "sample_data": sample_data, **extra}
    league, problems = build_league(raw, sports_root=sports_root, root=ROOT)
    assert league is not None, problems
    return league


def fake_rules(check=None, read=None):
    """A rules module like tiny's, with `check` and/or `read` replaced."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("tiny_rules_copy", ROOT / "tests/fixtures/sports/tiny/rules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if check:
        module.check = check
    if read:
        module.read = read
    return module


def load(data: Data, sports_root, *, rules=None, spec=None, sample_data=False, today=TODAY) -> LoadedData:
    league = league_for(sports_root, sample_data=sample_data)
    sport = league.sport_def
    if rules is not None:
        sport = replace(sport, rules=rules)
    if spec:
        sport = replace(sport, spec={**sport.spec, **spec})
    return load_data(data.root, league, sport, today=today)


def errs(result: LoadedData) -> dict[tuple[str, str], str]:
    """{(file, path): message} of the errors; fails if two errors share a file and path."""
    found = {(p.file, p.at): p.message for p in result.problems if p.level == "error"}
    assert len(found) == sum(p.level == "error" for p in result.problems), result.problems
    return found


def warns(result: LoadedData) -> dict[tuple[str, str], str]:
    return {(p.file, p.at): p.message for p in result.problems if p.level == "warning"}


def only_error(result: LoadedData) -> tuple[tuple[str, str], str]:
    found = errs(result)
    assert len(found) == 1, found
    return next(iter(found.items()))


def season(result: LoadedData, sid="s1"):
    return result.loaded[sid]


# ------------------------------------------------------------------ the valid fixture

def test_the_valid_fixture_loads_without_a_problem(sports_root):
    league = league_for(sports_root, sample_data=True)
    result = load_data(FIXTURE_ROOT, league, league.sport_def, today=TODAY)
    assert result.problems == [] and result.ok
    assert [s.id for s in result.seasons] == ["2026-27", "sample-2026-27", "sample-2025-26"]
    stand_in = result.loaded["sample-2026-27"]
    assert list(stand_in.teams) == ["otters", "ravens", "moose"]
    assert [t.slot for t in stand_in.teams.values()] == [1, 4, 3]
    assert stand_in.teams["moose"].colour == "#7A4A1E"
    assert [p.label for p in stand_in.players.values()] == ["#7 Ann B.", "#00 Joe K.", "Tom W.", "Sam P."]
    assert list(stand_in.games) == ["2026-11-05-1", "2026-11-12-1"]
    assert stand_in.games["2026-11-05-1"].photo == "sheets/2026-11-05-1.jpg"
    assert stand_in.games["2026-11-12-1"].forfeit == "moose" and stand_in.games["2026-11-12-1"].reading is None
    assert stand_in.folder == "data/sample-2026-27"


def test_the_active_season_and_the_shown_seasons_follow_sample_mode(sports_root):
    real = load_data(FIXTURE_ROOT, league_for(sports_root), league_for(sports_root).sport_def, today=TODAY)
    assert (real.active, real.shown) == ("2026-27", ["2026-27"])
    sample_league = league_for(sports_root, sample_data=True)
    sample = load_data(FIXTURE_ROOT, sample_league, sample_league.sport_def, today=TODAY)
    assert (sample.active, sample.shown) == ("sample-2026-27", ["sample-2026-27", "sample-2025-26"])


def test_a_real_past_season_is_shown_in_both_modes():
    from scripts.core.loader import SeasonDef
    defs = [SeasonDef("s1", "s1", 0, current=True), SeasonDef("s0", "s0", 1),
            SeasonDef("sample-s1", "x", 2, sample=True, stands_in_for="s1"), SeasonDef("sample-old", "x", 3, sample=True)]
    assert shown_seasons(defs, False) == ["s1", "s0"]
    assert shown_seasons(defs, True) == ["s0", "sample-s1", "sample-old"]      # seasons.yml order
    assert choose_active(defs, True).id == "sample-s1" and choose_active(defs, False).id == "s1"
    assert choose_active([SeasonDef("a", "a", 0)], False) is None and shown_seasons([SeasonDef("a", "a", 0)], False) == []


def test_a_season_with_overrides_gets_its_own_settings(sports_root):
    league = league_for(sports_root, sample_data=True)
    result = load_data(FIXTURE_ROOT, league, league.sport_def, today=TODAY)
    old = result.loaded["sample-2025-26"].settings
    assert old.standings["points"]["win"] == 3 and old.standings["points"]["ot_win"] == 3
    assert result.loaded["sample-2026-27"].settings.standings["points"]["win"] == 2
    assert league.standings["points"]["win"] == 2           # the League itself is unchanged


def test_the_decide_placeholders_are_per_season(sports_root, tmp_path):
    d = Data(tmp_path, seasons="- {id: s1, current: true, overrides: {rules: {overtime: overtime}}}\n")
    result = load(d, sports_root)
    assert result.ok
    left = [p.setting for p in season(result).settings.placeholders]
    assert "rules.overtime" not in left and "standings.tiebreakers" in left


# ------------------------------------------------------------------ an empty current season

def test_an_empty_current_season_is_fine(sports_root):
    league = league_for(sports_root)
    result = load_data(FIXTURE_ROOT, league, league.sport_def, today=TODAY)
    empty = result.loaded["2026-27"]
    assert result.problems == []
    assert (empty.teams, empty.players, empty.schedule, empty.games, empty.byes) == ({}, {}, [], {}, {})


def test_a_season_folder_with_no_files_at_all_is_fine(sports_root, tmp_path):
    d = Data(tmp_path, teams=None, players=None, schedule=None)
    assert load(d, sports_root).problems == []


def test_a_header_only_schedule_and_empty_yaml_files_are_fine(sports_root, tmp_path):
    d = Data(tmp_path, teams="", players="# nobody yet\n", schedule="game_id,date,time,home,away\n")
    assert load(d, sports_root).problems == []


# ------------------------------------------------------------------ seasons.yml

def seasons_errors(sports_root, tmp_path, text, **kw):
    return errs(load(Data(tmp_path, seasons=text), sports_root, **kw))


def test_seasons_file_missing_or_empty_or_wrong_kind(sports_root, tmp_path):
    d = Data(tmp_path)
    (tmp_path / "data" / "seasons.yml").unlink()
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == ("data/seasons.yml", "") and "Cannot read" in msg
    assert seasons_errors(sports_root, tmp_path, "[]\n") == {("data/seasons.yml", ""): errs_msg_no_season()}
    assert ("data/seasons.yml", "") in seasons_errors(sports_root, tmp_path, "")
    assert ("data/seasons.yml", "") in seasons_errors(sports_root, tmp_path, "id: s1\n")


def errs_msg_no_season():
    return "lists no season. Add at least one, like '- {id: 2026-27, label: \"2026–27\", current: true}'."


def test_exactly_one_season_is_current(sports_root, tmp_path):
    found = seasons_errors(sports_root, tmp_path, "- {id: s1}\n")
    assert list(found) == [("data/seasons.yml", "")] and "no current season" in found[("data/seasons.yml", "")]
    (tmp_path / "data" / "s2").mkdir()
    found = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true}\n- {id: s2, current: true}\n")
    assert list(found) == [("data/seasons.yml", "1.current")] and "'s1' is already the current season" in found[("data/seasons.yml", "1.current")]


def test_a_sample_season_is_never_current(sports_root, tmp_path):
    found = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true, sample: true}\n")
    assert ("data/seasons.yml", "0.current") in found and "never the current one" in found[("data/seasons.yml", "0.current")]


def test_unknown_and_missing_keys_have_paths(sports_root, tmp_path):
    found = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true, venu: Gym}\n- {label: Two}\n- plain\n")
    assert set(found) == {("data/seasons.yml", "0.venu"), ("data/seasons.yml", "1.id"), ("data/seasons.yml", "2")}
    assert "Did you mean 'venue'" in found[("data/seasons.yml", "0.venu")]


@pytest.mark.parametrize("bad", ["Two Words", "UPPER", "-x", ""])
def test_a_season_id_must_be_an_id(sports_root, tmp_path, bad):
    found = seasons_errors(sports_root, tmp_path, f"- {{id: s1, current: true}}\n- {{id: '{bad}'}}\n")
    assert ("data/seasons.yml", "1.id") in found


def test_a_season_id_may_not_repeat_and_needs_its_folder(sports_root, tmp_path):
    found = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true}\n- {id: s1}\n- {id: nope}\n")
    assert "listed twice" in found[("data/seasons.yml", "1.id")]
    assert "no folder. Create data/nope/" in found[("data/seasons.yml", "2.id")]


def test_label_defaults_to_the_id_and_must_be_text(sports_root, tmp_path):
    result = load(Data(tmp_path, seasons="- {id: s1, current: true}\n"), sports_root)
    assert result.seasons[0].label == "s1"
    found = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true, label: 5, venue: '', as_of: 2026-01-01}\n")
    assert {k[1] for k in found} == {"0.label", "0.venue", "0.as_of"}


def test_stands_in_for_rules(sports_root, tmp_path):
    (tmp_path / "data" / "x1").mkdir(parents=True)
    (tmp_path / "data" / "x2").mkdir(parents=True)
    base = "- {id: s1, current: true}\n"
    f = seasons_errors(sports_root, tmp_path, base + "- {id: x1, stands_in_for: s1}\n")
    assert set(f) == {("data/seasons.yml", "1.stands_in_for")} and "Add 'sample: true'" in f[("data/seasons.yml", "1.stands_in_for")]
    f = seasons_errors(sports_root, tmp_path, base + "- {id: x1, sample: true, stands_in_for: zzz}\n")
    assert "not a season in this file" in f[("data/seasons.yml", "1.stands_in_for")]
    f = seasons_errors(sports_root, tmp_path, base + "- {id: x1, sample: true, stands_in_for: x1}\n")
    assert "cannot stand in for itself" in f[("data/seasons.yml", "1.stands_in_for")]
    f = seasons_errors(sports_root, tmp_path, base + "- {id: x1, sample: true}\n- {id: x2, sample: true, stands_in_for: x1}\n")
    assert "itself a sample season" in f[("data/seasons.yml", "2.stands_in_for")]


def test_at_most_one_sample_stands_in_for_a_season(sports_root, tmp_path):
    (tmp_path / "data" / "x1").mkdir(parents=True)
    (tmp_path / "data" / "x2").mkdir(parents=True)
    f = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true}\n- {id: x1, sample: true, stands_in_for: s1}\n"
                                              "- {id: x2, sample: true, stands_in_for: s1}\n")
    assert set(f) == {("data/seasons.yml", "2.stands_in_for")}
    assert "'x1' already stands in for 's1'" in f[("data/seasons.yml", "2.stands_in_for")]


def test_sample_data_needs_a_stand_in(sports_root, tmp_path):
    f = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true}\n", sample_data=True)
    assert set(f) == {("data/seasons.yml", "")} and "stands_in_for: s1" in f[("data/seasons.yml", "")]


def test_as_of_is_a_sample_only_date(sports_root, tmp_path):
    (tmp_path / "data" / "x1").mkdir(parents=True)
    f = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true, as_of: 2026-11-20}\n")
    assert "only a sample season has as_of" in f[("data/seasons.yml", "0.as_of")]
    f = seasons_errors(sports_root, tmp_path, "- {id: s1, current: true}\n- {id: x1, sample: true, as_of: 20-11-2026}\n")
    assert "not a date" in f[("data/seasons.yml", "1.as_of")]
    result = load(Data(tmp_path, seasons="- {id: s1, current: true}\n- {id: x1, sample: true, as_of: 2026-11-20}\n"), sports_root,
                  today=dt.date(2030, 1, 1))
    assert result.seasons[1].as_of == dt.date(2026, 11, 20)
    assert (season(result, "x1").today, season(result, "s1").today) == (dt.date(2026, 11, 20), dt.date(2030, 1, 1))


def test_season_overrides_are_checked_with_their_path(sports_root, tmp_path):
    f = seasons_errors(sports_root, tmp_path,
                       "- {id: s1, current: true, overrides: {standings: {points: {win: lots}}, rules: {periodz: 3}}}\n")
    assert set(f) == {("data/seasons.yml", "0.overrides.standings.points.win"), ("data/seasons.yml", "0.overrides.rules.periodz")}


def test_today_defaults_to_the_date_in_the_league_time_zone(sports_root, tmp_path):
    d = Data(tmp_path)
    league = league_for(sports_root)
    result = load_data(d.root, league, league.sport_def)
    assert isinstance(result.today, dt.date) and abs((result.today - dt.date.today()).days) <= 1


# ------------------------------------------------------------------ teams.yml

def team_errors(sports_root, tmp_path, text, **kw):
    return errs(load(Data(tmp_path, teams=text, players=None, schedule=None), sports_root, **kw))


def test_teams_defaults_slots_wrap_and_colour_is_upper_case(sports_root, tmp_path):
    rows = "".join(f"- {{id: t{i}, name: Team {i}, code: T{i}}}\n" for i in range(7))
    rows += "- {id: own, name: Own, code: OWN, slot: 2, colour: '#abcdef'}\n"
    teams = season(load(Data(tmp_path, teams=rows, players=None, schedule=None), sports_root)).teams
    assert [t.slot for t in teams.values()] == [1, 2, 3, 4, 5, 6, 1, 2]
    assert (teams["own"].colour, teams["t0"].colour, teams["t0"].code) == ("#ABCDEF", None, "T0")


def test_team_keys_have_paths(sports_root, tmp_path):
    f = team_errors(sports_root, tmp_path, "- {id: a1, name: A, code: AA, nick: x}\n- {id: b1, name: B}\n- just text\n")
    assert set(f) == {(f"{S1}/teams.yml", p) for p in ("0.nick", "1.code", "2")}


def test_teams_file_must_be_a_list(sports_root, tmp_path):
    assert set(team_errors(sports_root, tmp_path, "id: otters\n")) == {(f"{S1}/teams.yml", "")}


def test_team_id_name_and_code_are_unique(sports_root, tmp_path):
    f = team_errors(sports_root, tmp_path,
                    "- {id: a1, name: Otters, code: OTT}\n- {id: a1, name: otters, code: OTT}\n")
    assert set(f) == {(f"{S1}/teams.yml", p) for p in ("1.id", "1.name", "1.code")}
    assert "already used by row 0" in f[(f"{S1}/teams.yml", "1.name")]


@pytest.mark.parametrize("code", ["o", "ottos", "ott", "O-T", "O T"])
def test_team_code_is_two_to_four_capitals_or_digits(sports_root, tmp_path, code):
    f = team_errors(sports_root, tmp_path, f"- {{id: a1, name: A, code: '{code}'}}\n")
    assert set(f) == {(f"{S1}/teams.yml", "0.code")}


@pytest.mark.parametrize("code", ["OT", "OTTR", "A1", "123"])
def test_valid_team_codes(sports_root, tmp_path, code):
    assert team_errors(sports_root, tmp_path, f"- {{id: a1, name: A, code: '{code}'}}\n") == {}


@pytest.mark.parametrize("slot", [0, 7, "two", 1.5, True])
def test_team_slot_is_one_to_six(sports_root, tmp_path, slot):
    f = team_errors(sports_root, tmp_path, f"- {{id: a1, name: A, code: AA, slot: {str(slot).lower()}}}\n")
    assert set(f) == {(f"{S1}/teams.yml", "0.slot")}


@pytest.mark.parametrize("colour", ["red", "#12345", "123456", "#GGGGGG"])
def test_team_colour_is_a_hex(sports_root, tmp_path, colour):
    f = team_errors(sports_root, tmp_path, f"- {{id: a1, name: A, code: AA, colour: '{colour}'}}\n")
    assert set(f) == {(f"{S1}/teams.yml", "0.colour")}


def test_team_id_must_be_an_id_and_numbers_are_text(sports_root, tmp_path):
    f = team_errors(sports_root, tmp_path, "- {id: Bad Id, name: A, code: AA}\n")
    assert set(f) == {(f"{S1}/teams.yml", "0.id")}
    teams = season(load(Data(tmp_path, teams="- {id: 12, name: Twelve, code: T12}\n", players=None, schedule=None), sports_root)).teams
    assert list(teams) == ["12"]


# ------------------------------------------------------------------ players.yml

def player_errors(sports_root, tmp_path, text, **kw):
    return errs(load(Data(tmp_path, players=text, schedule=None), sports_root, **kw))


def players_of(sports_root, tmp_path, text, **kw):
    return season(load(Data(tmp_path, players=text, schedule=None), sports_root, **kw)).players


@pytest.mark.parametrize("name", ["Ann Bell", "ann b.", "Ann B", "Ann Bb.", "Ann", 5])
def test_player_name_must_be_first_l(sports_root, tmp_path, name):
    f = player_errors(sports_root, tmp_path, f"- {{id: ann-b, name: {name!r}, team: otters}}\n")
    assert set(f) == {(f"{S1}/players.yml", "0.name")}
    assert "'First L.'" in f[(f"{S1}/players.yml", "0.name")]


def test_player_name_accepts_first_l_and_the_placeholder(sports_root, tmp_path):
    text = ("- {id: a, name: Ann B., team: otters}\n- {id: b, name: \"Mary-Jo D'Arcy B.\", team: otters}\n"
            "- {id: c, name: '[placeholder]', team: otters}\n- {id: d, name: '[placeholder]', team: otters}\n")
    assert player_errors(sports_root, tmp_path, text) == {}


def test_player_numbers_are_text_and_zero_zero_survives(sports_root, tmp_path):
    p = players_of(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters, number: 7}\n"
                                         "- {id: b, name: Bo C., team: otters, number: 00}\n"
                                         "- {id: c, name: Cy D., team: otters, number: '0'}\n"
                                         "- {id: d, name: Di E., team: otters, number: 99}\n"
                                         "- {id: e, name: Ed F., team: otters}\n")
    assert [x.number for x in p.values()] == ["7", "00", "0", "99", None]
    assert p["b"].label == "#00 Bo C." and p["e"].label == "Ed F."


@pytest.mark.parametrize("number", ["100", "-1", "007", "7.5", "abc", "true", "[1]"])
def test_player_number_must_be_zero_to_ninety_nine(sports_root, tmp_path, number):
    f = player_errors(sports_root, tmp_path, f"- {{id: a, name: Ann B., team: otters, number: {number}}}\n")
    assert set(f) == {(f"{S1}/players.yml", "0.number")}


def test_same_first_l_on_a_team_needs_numbers_on_both(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: ann-b, name: Ann B., team: otters, number: 7}\n"
                                             "- {id: ann-b2, name: Ann B., team: otters}\n"
                                             "- {id: ann-b3, name: Ann B., team: ravens}\n")
    assert set(f) == {(f"{S1}/players.yml", "1.number")}
    assert "ann-b" in f[(f"{S1}/players.yml", "1.number")] and "otters" in f[(f"{S1}/players.yml", "1.number")]
    # with numbers on both, it is fine; the same name on different teams never needed numbers
    assert player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters, number: 7}\n"
                                                "- {id: b, name: Ann B., team: otters, number: 8}\n") == {}


def test_both_missing_numbers_are_each_reported(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters}\n- {id: b, name: Ann B., team: otters}\n")
    assert set(f) == {(f"{S1}/players.yml", "0.number"), (f"{S1}/players.yml", "1.number")}


def test_two_regulars_cannot_share_a_number_but_a_spare_may(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters, number: 7}\n"
                                             "- {id: b, name: Bo C., team: otters, number: 7}\n")
    assert set(f) == {(f"{S1}/players.yml", "1.number")} and "Ann B.'s number" in f[(f"{S1}/players.yml", "1.number")]
    assert player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters, number: 7}\n"
                                                "- {id: b, name: Bo C., team: otters, number: 7, sub: true}\n"
                                                "- {id: c, name: Cy D., team: ravens, number: 7}\n") == {}


def test_a_spare_may_have_no_team_only_with_sub_true(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: null, sub: true}\n"
                                             "- {id: b, name: Bo C., team: null}\n- {id: c, name: Cy D.}\n"
                                             "- {id: d, name: Di E., team: null, sub: false}\n")
    assert set(f) == {(f"{S1}/players.yml", p) for p in ("1.team", "2.team", "3.team")}
    assert players_of(sports_root, tmp_path, "- {id: a, name: Ann B., team: null, sub: true}\n")["a"].team is None


def test_player_team_must_exist(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otter}\n")
    assert set(f) == {(f"{S1}/players.yml", "0.team")} and "Did you mean 'otters'" in f[(f"{S1}/players.yml", "0.team")]


def test_player_ids_and_keys(sports_root, tmp_path):
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters}\n- {id: a, name: Bo C., team: otters}\n"
                                             "- {id: c, name: Cy D., team: otters, nick: x, sub: maybe}\n- {name: No I., team: otters}\n")
    assert set(f) == {(f"{S1}/players.yml", p) for p in ("1.id", "2.nick", "2.sub", "3.id")}


def test_position_only_when_the_sport_lists_positions(sports_root, tmp_path):
    text = "- {id: a, name: Ann B., team: otters, position: skip}\n"
    f = player_errors(sports_root, tmp_path, text)
    assert set(f) == {(f"{S1}/players.yml", "0.position")} and "no positions" in f[(f"{S1}/players.yml", "0.position")]
    spec = {"positions": ["lead", "skip"]}
    assert player_errors(sports_root, tmp_path, text, spec=spec) == {}
    assert players_of(sports_root, tmp_path, text, spec=spec)["a"].position == "skip"
    f = player_errors(sports_root, tmp_path, "- {id: a, name: Ann B., team: otters, position: goalie}\n", spec=spec)
    assert set(f) == {(f"{S1}/players.yml", "0.position")}


# ------------------------------------------------------------------ schedule.csv

def sched(sports_root, tmp_path, text, **kw):
    return load(Data(tmp_path, schedule=text), sports_root, **kw)


def sched_errors(sports_root, tmp_path, text, **kw):
    return errs(sched(sports_root, tmp_path, text, **kw))


CSV = f"{S1}/schedule.csv"
HEAD = "game_id,date,time,home,away\n"


def test_the_header_names_the_columns_in_any_order(sports_root, tmp_path):
    text = ("away,home,week,status,time,date,game_id,venue,surface,type,round,moved_from\n"
            "ravens,otters,3,,19:30,2026-11-05,g1,Annex,A,playoff,Semi,2026-11-04\n")
    rows = season(sched(sports_root, tmp_path, text)).schedule
    r = rows[0]
    assert (r.game_id, r.date, r.time, r.home, r.away) == ("g1", dt.date(2026, 11, 5), dt.time(19, 30), "otters", "ravens")
    assert (r.venue, r.surface, r.type, r.round, r.week, r.moved_from) == ("Annex", "A", "playoff", "Semi", 3, dt.date(2026, 11, 4))
    assert (r.status, r.cancelled, r.teams_known, r.row, r.line) == ("", False, True, 0, 2)


def test_only_the_first_five_columns_are_required(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, "game_id,date,home\ng1,2026-11-05,otters\n")
    assert set(f) == {(CSV, "header.time"), (CSV, "header.away")}
    r = season(sched(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otters,ravens\n")).schedule[0]
    assert (r.venue, r.surface, r.type, r.round, r.status, r.moved_from) == (None, None, "regular", None, "", None)


def test_unknown_and_repeated_columns_are_errors(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD.strip() + ",wekk,date\ng1,2026-11-05,19:00,otters,ravens,1,2026-11-05\n")
    assert set(f) == {(CSV, "header.wekk"), (CSV, "header.date")}
    assert "Did you mean 'week'" in f[(CSV, "header.wekk")]


def test_dates_and_times_must_parse_and_messages_carry_the_spreadsheet_line(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otters,ravens\n"
                                                  "g2,5/11/2026,25:00,otters,moose\n")
    assert set(f) == {(CSV, "1.date"), (CSV, "1.time")}
    assert "(spreadsheet line 3)" in f[(CSV, "1.date")] and "YYYY-MM-DD" in f[(CSV, "1.date")]
    assert "like 19:00" in f[(CSV, "1.time")]
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-02-30,19:00,otters,ravens\n")
    assert set(f) == {(CSV, "0.date")}


def test_required_cells_may_not_be_empty(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + ",2026-11-05,,otters,\n")
    assert set(f) == {(CSV, "0.game_id"), (CSV, "0.time"), (CSV, "0.away")}


def test_game_ids_are_unique_and_ids(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otters,ravens\ng1,2026-11-12,19:00,otters,moose\n"
                                                  "Bad Id,2026-11-19,19:00,otters,moose\n")
    assert set(f) == {(CSV, "1.game_id"), (CSV, "2.game_id")}
    assert "already used on row 0" in f[(CSV, "1.game_id")]


def test_teams_must_exist_on_regular_rows(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otter,TBD\n")
    assert set(f) == {(CSV, "0.home"), (CSV, "0.away")}
    assert "'otter' is not a team id in teams.yml. Did you mean 'otters'" in f[(CSV, "0.home")]
    assert "Only a playoff game may" in f[(CSV, "0.away")]


def test_playoff_rows_may_have_placeholder_teams(sports_root, tmp_path):
    text = (HEAD.strip() + ",type,round\ng1,2027-04-08,19:00,1st,Winner SF1,playoff,Final\n"
            "g2,2027-04-08,20:00,otters,TBD,playoff,Final\ng3,2027-04-09,19:00,TBD,TBD,playoff,Final\n")
    result = sched(sports_root, tmp_path, text)
    assert result.problems == []
    rows = season(result).schedule
    assert [r.teams_known for r in rows] == [False, False, False]
    assert (rows[0].home, rows[0].away, rows[1].home) == ("1st", "Winner SF1", "otters")


def test_a_team_cannot_play_itself(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otters,otters\n")
    assert set(f) == {(CSV, "0.away")}


def test_type_status_week_and_moved_from_values(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD.strip() + ",type,status,week,moved_from\n"
                                            "g1,2026-11-05,19:00,otters,ravens,exhibition,done,0,sometime\n"
                                            "g2,2026-11-12,19:00,otters,ravens,,,two,\n")
    assert set(f) == {(CSV, "0.type"), (CSV, "0.status"), (CSV, "0.week"), (CSV, "0.moved_from"), (CSV, "1.week")}


def test_a_team_plays_at_most_once_a_day(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD + "g1,2026-11-05,19:00,otters,ravens\ng2,2026-11-05,20:00,moose,otters\n")
    assert set(f) == {(CSV, "1.away")}
    assert "'otters' already plays 1 game on 2026-11-05 (g1)" in f[(CSV, "1.away")] and "(spreadsheet line 3)" in f[(CSV, "1.away")]


def test_the_sport_can_allow_more_games_a_day(sports_root, tmp_path):
    text = HEAD + "g1,2026-11-05,19:00,otters,ravens\ng2,2026-11-05,20:00,moose,otters\n"
    assert sched(sports_root, tmp_path, text, spec={"games_per_day": 2}).ok
    text += "g3,2026-11-05,21:00,otters,ravens\n"
    f = sched_errors(sports_root, tmp_path, text, spec={"games_per_day": 2})
    assert set(f) == {(CSV, "2.home")} and "allows 2 a day" in f[(CSV, "2.home")]


def test_a_cancelled_game_does_not_use_up_the_day(sports_root, tmp_path):
    text = HEAD.strip() + ",status\ng1,2026-11-05,19:00,otters,ravens,cancelled\ng2,2026-11-05,20:00,otters,moose,\n"
    result = sched(sports_root, tmp_path, text)
    assert result.problems == [] and season(result).schedule[0].cancelled


def test_rows_that_are_too_long_blank_lines_and_the_row_numbering(sports_root, tmp_path):
    text = HEAD + "g1,2026-11-05,19:00,otters,ravens,extra\n\n,,,,\ng2,bad,19:00,otters,moose\n"
    f = sched_errors(sports_root, tmp_path, text)
    assert set(f) == {(CSV, "0"), (CSV, "3.date")}
    assert "(spreadsheet line 5)" in f[(CSV, "3.date")]


def test_a_utf8_bom_quoted_cells_and_a_bad_encoding(sports_root, tmp_path):
    text = "﻿" + HEAD.strip() + ",round\ng1,2026-11-05,19:00,otters,ravens,\"Semi, game 1\"\n"
    result = sched(sports_root, tmp_path, text)
    assert result.problems == [] and season(result).schedule[0].round == "Semi, game 1"
    d = Data(tmp_path)
    d.put("s1/schedule.csv", b"game_id,date,time,home,away\n\xff\xfe\n")
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == (CSV, "") and "UTF-8" in msg


def test_blank_week_is_counted_from_the_regular_season_dates(sports_root, tmp_path):
    text = (HEAD.strip() + ",type,week,status\n"
            "a,2026-11-12,19:00,otters,ravens,regular,,\n"
            "b,2026-11-05,19:00,otters,moose,regular,,\n"
            "c,2026-11-12,20:00,moose,,regular,,\n".replace("moose,,", "moose,ravens,")
            + "d,2026-11-19,19:00,otters,ravens,regular,9,\n"
            "e,2026-11-26,19:00,otters,ravens,regular,,cancelled\n"
            "f,2027-04-08,19:00,1st,2nd,playoff,,\n")
    weeks = {r.game_id: r.week for r in season(sched(sports_root, tmp_path, text)).schedule}
    assert weeks == {"a": 2, "b": 1, "c": 2, "d": 9, "e": 4, "f": None}


def test_byes_are_worked_out_never_read(sports_root, tmp_path):
    text = (HEAD.strip() + ",status,type\n"
            "a,2026-11-05,19:00,otters,ravens,,\n"
            "b,2026-11-12,19:00,otters,ravens,cancelled,\n"
            "c,2026-11-19,19:00,moose,otters,,\n"
            "d,2027-04-08,19:00,otters,ravens,,playoff\n")
    s = season(sched(sports_root, tmp_path, text))
    assert s.byes == {dt.date(2026, 11, 5): ("moose",), dt.date(2026, 11, 19): ("ravens",)}
    assert work_out_byes([], s.teams) == {}


def test_a_bye_column_is_not_accepted(sports_root, tmp_path):
    f = sched_errors(sports_root, tmp_path, HEAD.strip() + ",bye\ng1,2026-11-05,19:00,otters,ravens,moose\n")
    assert set(f) == {(CSV, "header.bye")}


# ------------------------------------------------------------------ game files: the envelope

def game_errors(sports_root, tmp_path, text=GAME, **kw):
    d = Data(tmp_path)
    d.game("2026-11-05-1", text)
    return errs(load(d, sports_root, **kw))


GF = f"{S1}/games/2026-11-05-1.yml"


def game_result(sports_root, tmp_path, text=GAME, **kw):
    d = Data(tmp_path)
    d.game("2026-11-05-1", text)
    return load(d, sports_root, **kw)


def edit(**changes):
    """GAME with some top-level lines replaced; a value of None removes the line."""
    lines = []
    for line in GAME.splitlines(keepends=True):
        key = line.split(":")[0]
        if key in changes:
            if changes[key] is not None:
                lines.append(f"{key}: {changes[key]}\n")
            continue
        lines.append(line)
    return "".join(lines)


def test_a_valid_game_file_loads_with_its_row_and_context(sports_root, tmp_path):
    result = game_result(sports_root, tmp_path)
    assert result.problems == []
    g = season(result).games["2026-11-05-1"]
    assert (g.home, g.away, g.checked_by, g.scorekeeper, g.forfeit, g.photo) == ("otters", "ravens", "Lee M.", None, None, None)
    assert g.file == GF and g.row.game_id == "2026-11-05-1" and g.season == "s1"
    assert g.sheet == {"final": {"home": 21, "away": 20}} and isinstance(g.reading, Reading)
    ctx = g.context
    assert ctx.sides == {"home": "otters", "away": "ravens"} and (ctx.game_type, ctx.folder) == ("regular", "games")
    assert ctx.options == season(result).settings.rules and set(ctx.teams) == {"otters", "ravens", "moose"}
    assert "ann-b" in ctx.players and ctx.sport["name"] == "Tiny"


def test_unknown_envelope_keys_are_errors(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, GAME + "chekced_by: x\n")
    assert set(f) == {(GF, "chekced_by")} and "Did you mean 'checked_by'" in f[(GF, "chekced_by")]


@pytest.mark.parametrize("key", ["game_id", "status", "home", "away", "checked_by"])
def test_required_envelope_keys(sports_root, tmp_path, key):
    f = game_errors(sports_root, tmp_path, edit(**{key: None}))
    assert (GF, key) in f and f[(GF, key)] == f"is required. Add a '{key}:' line."


def test_the_file_must_be_a_mapping_and_not_empty(sports_root, tmp_path):
    assert set(game_errors(sports_root, tmp_path, "- a\n- b\n")) == {(GF, "")}
    assert set(game_errors(sports_root, tmp_path, "")) == {(GF, "")}
    f = game_errors(sports_root, tmp_path, "game_id: [oops\n")
    assert set(f) == {(GF, "")} and "not valid YAML" in f[(GF, "")]


def test_game_id_must_match_the_file_name_and_the_schedule(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, edit(game_id="2026-11-12-1"))
    assert set(f) == {(GF, "game_id")}
    assert "does not match the file name 2026-11-05-1.yml" in f[(GF, "game_id")]
    d = Data(tmp_path / "second")
    d.game("2026-11-06-9", GAME.replace("2026-11-05-1", "2026-11-06-9"))
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == (f"{S1}/games/2026-11-06-9.yml", "game_id") and "not a game in schedule.csv" in msg


def test_a_cancelled_game_has_no_game_file(sports_root, tmp_path):
    d = Data(tmp_path, schedule=HEAD.strip() + ",status\n2026-11-05-1,2026-11-05,19:00,otters,ravens,cancelled\n")
    d.game("2026-11-05-1")
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == (GF, "game_id") and "marked cancelled in schedule.csv" in msg


def test_status_must_be_final(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, edit(status="draft"))
    assert set(f) == {(GF, "status")} and "drafts/" in f[(GF, "status")]
    f = game_errors(sports_root, tmp_path, edit(status="done"))
    assert set(f) == {(GF, "status")} and "Use one of: final" in f[(GF, "status")]


def test_home_and_away_must_match_the_schedule(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, edit(home="ravens", away="otters"))
    assert set(f) == {(GF, "home")}
    assert f[(GF, "home")].startswith("ravens/otters doesn't match schedule.csv (otters/ravens)")
    f = game_errors(sports_root, tmp_path, edit(home="Bad Id"))
    assert set(f) == {(GF, "home")}


def test_a_playoff_row_with_placeholder_teams_cannot_have_a_game_file_yet(sports_root, tmp_path):
    d = Data(tmp_path, schedule=HEAD.strip() + ",type\n2026-11-05-1,2026-11-05,19:00,1st,2nd,playoff\n")
    d.game("2026-11-05-1")
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == (GF, "home") and "1st/2nd" in msg


def test_checked_by_and_scorekeeper_are_first_l(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, edit(checked_by="'Lee Murphy'") + "scorekeeper: pat\n")
    assert set(f) == {(GF, "checked_by"), (GF, "scorekeeper")}
    assert game_errors(sports_root, tmp_path, GAME + "scorekeeper: Pat S.\n") == {}


def test_notes_shape(sports_root, tmp_path):
    ok = GAME + "notes:\n  - {text: Running time.}\n  - {text: Late start.}\n"
    result = game_result(sports_root, tmp_path, ok)
    assert season(result).games["2026-11-05-1"].notes == ("Running time.", "Late start.")
    f = game_errors(sports_root, tmp_path, GAME + "notes:\n  - {text: ''}\n  - {txt: x}\n  - plain\n")
    assert set(f) == {(GF, "notes.0.text"), (GF, "notes.1.txt"), (GF, "notes.1.text"), (GF, "notes.2")}
    assert set(game_errors(sports_root, tmp_path, GAME + "notes: hello\n")) == {(GF, "notes")}


def test_review_shape_and_a_warning_for_leftovers(sports_root, tmp_path):
    assert game_result(sports_root, tmp_path, GAME + "review: []\n").problems == []
    result = game_result(sports_root, tmp_path, GAME + "review:\n  - {at: sheet.final.home, note: Check it.}\n")
    assert errs(result) == {} and set(warns(result)) == {(GF, "review")}
    assert set(game_errors(sports_root, tmp_path, GAME + "review:\n  - {at: x}\n")) == {(GF, "review.0.note")}


def test_photo_by_convention_and_by_key(sports_root, tmp_path):
    d = Data(tmp_path)
    d.game("2026-11-05-1")
    assert season(load(d, sports_root)).games["2026-11-05-1"].photo is None
    d.put("s1/sheets/2026-11-05-1.png", b"x")
    assert season(load(d, sports_root)).games["2026-11-05-1"].photo == "sheets/2026-11-05-1.png"
    d.put("s1/other/pic.jpg", b"x")
    d.game("2026-11-05-1", GAME + "photo: other/pic.jpg\n")
    assert season(load(d, sports_root)).games["2026-11-05-1"].photo == "other/pic.jpg"


def test_a_photo_key_must_point_inside_the_season_folder_and_exist(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, GAME + "photo: ../../secret.jpg\n")
    assert set(f) == {(GF, "photo")}
    f = game_errors(sports_root, tmp_path, GAME + "photo: /etc/passwd\n")
    assert set(f) == {(GF, "photo")}
    result = game_result(sports_root, tmp_path, GAME + "photo: sheets/missing.jpg\n")
    assert errs(result) == {} and set(warns(result)) == {(GF, "photo")}
    assert season(result).games["2026-11-05-1"].photo is None


def test_a_forfeit_replaces_the_sheet(sports_root, tmp_path):
    text = edit(**{"sheet": None}).replace("  final: {home: 21, away: 20}\n", "") + "forfeit: ravens\n"
    result = game_result(sports_root, tmp_path, text)
    assert result.problems == []
    g = season(result).games["2026-11-05-1"]
    assert (g.forfeit, g.sheet, g.reading) == ("ravens", None, None)


def test_a_sheet_beside_a_forfeit_is_an_error(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, GAME + "forfeit: ravens\n")
    assert set(f) == {(GF, "sheet")} and "no sheet" in f[(GF, "sheet")]


def test_a_forfeit_names_one_of_the_two_teams(sports_root, tmp_path):
    base = GAME.replace("sheet:\n  final: {home: 21, away: 20}\n", "")
    f = game_errors(sports_root, tmp_path, base + "forfeit: moose\n")
    assert set(f) == {(GF, "forfeit")} and "otters, ravens" in f[(GF, "forfeit")]
    assert set(game_errors(sports_root, tmp_path, base + "forfeit: Not Id\n")) == {(GF, "forfeit")}


def test_neither_sheet_nor_forfeit_is_an_error(sports_root, tmp_path):
    f = game_errors(sports_root, tmp_path, GAME.replace("sheet:\n  final: {home: 21, away: 20}\n", ""))
    assert set(f) == {(GF, "sheet")} and "is required" in f[(GF, "sheet")]


def test_the_sheet_must_be_a_mapping(sports_root, tmp_path):
    assert set(game_errors(sports_root, tmp_path, GAME.replace("sheet:\n  final: {home: 21, away: 20}\n", "sheet: [1, 2]\n"))) == {(GF, "sheet")}


def test_game_files_that_are_not_yml_are_noted(sports_root, tmp_path):
    d = Data(tmp_path)
    d.put("s1/games/2026-11-05-1.yaml", GAME)
    d.put("s1/games/notes.txt", "hi")
    result = load(d, sports_root)
    assert errs(result) == {} and set(warns(result)) == {(f"{S1}/games/2026-11-05-1.yaml", ""), (f"{S1}/games/notes.txt", "")}
    assert season(result).games == {}


def test_all_problems_in_a_file_are_reported_and_the_bad_game_is_left_out(sports_root, tmp_path):
    text = edit(status="draft", checked_by="x", home="ravens", away="otters") + "bogus: 1\n"
    result = game_result(sports_root, tmp_path, text)
    assert {at for (_, at) in errs(result)} == {"status", "checked_by", "home", "bogus"}
    assert season(result).games == {} and not result.ok


# ------------------------------------------------------------------ game files: the sport's check and read

def test_sport_problems_gain_the_file_and_the_sheet_prefix(sports_root, tmp_path):
    def check(sheet, ctx):
        return [Problem("error", "final.home", "the Final box is wrong"), Problem("error", "", "the sheet is wrong"),
                Problem("warning", "players.home.0.player", "who is that?")]
    result = game_result(sports_root, tmp_path, rules=fake_rules(check=check))
    assert errs(result) == {(GF, "sheet.final.home"): "the Final box is wrong", (GF, "sheet"): "the sheet is wrong"}
    assert warns(result) == {(GF, "sheet.players.home.0.player"): "who is that?"}
    assert season(result).games == {}


def test_check_gets_the_sheet_and_a_context_and_read_runs_after_a_clean_check(sports_root, tmp_path):
    calls = []

    def check(sheet, ctx):
        calls.append(("check", sheet, ctx.sides, ctx.folder))
        return [Problem("warning", "", "just a warning")]

    def read(sheet, ctx):
        calls.append(("read", ctx.game_type))
        return Reading(score=Score(final={"home": 21, "away": 20}, periods={"home": [], "away": []},
                                   final_at={"home": "sheet.final.home", "away": "sheet.final.away"}),
                       lines=[Line("home", "ann-b", counts={"pts": 9})])
    result = game_result(sports_root, tmp_path, rules=fake_rules(check, read))
    assert [c[0] for c in calls] == ["check", "read"]
    assert calls[0][1:] == ({"final": {"home": 21, "away": 20}}, {"home": "otters", "away": "ravens"}, "games")
    g = season(result).games["2026-11-05-1"]
    assert g.reading.lines[0].player == "ann-b" and g.reading.score.final == {"home": 21, "away": 20}
    assert result.ok and len(warns(result)) == 1


def test_read_is_not_called_when_check_found_an_error(sports_root, tmp_path):
    calls = []
    read = lambda sheet, ctx: calls.append("read")
    check = lambda sheet, ctx: [Problem("error", "final", "bad")]
    game_result(sports_root, tmp_path, rules=fake_rules(check, read))
    assert calls == []


def test_the_context_carries_the_game_type_and_the_seasons_rules(sports_root, tmp_path):
    seen = []

    def check(sheet, ctx):
        seen.append((ctx.game_type, ctx.options["overtime"], ctx.sides))
        return []
    text = HEAD.strip() + ",type\ng1,2026-11-05,19:00,otters,ravens,playoff\n"
    d = Data(tmp_path, schedule=text, seasons="- {id: s1, current: true, overrides: {rules: {overtime: overtime}}}\n")
    d.game("g1", GAME.replace("2026-11-05-1", "g1"))
    assert load(d, sports_root, rules=fake_rules(check=check)).ok
    assert seen == [("playoff", "overtime", {"home": "otters", "away": "ravens"})]


def test_a_forfeit_is_not_sent_to_the_sport(sports_root, tmp_path):
    def boom(sheet, ctx):
        raise AssertionError("must not be called")
    text = GAME.replace("sheet:\n  final: {home: 21, away: 20}\n", "") + "forfeit: otters\n"
    assert game_result(sports_root, tmp_path, text, rules=fake_rules(check=boom, read=boom)).ok


def test_a_sport_function_that_raises_is_an_internal_error(sports_root, tmp_path):
    def check(sheet, ctx):
        raise KeyError("periods")
    with pytest.raises(InternalError, match=r"check\(\).*KeyError"):
        game_result(sports_root, tmp_path, rules=fake_rules(check=check))

    def read(sheet, ctx):
        raise ZeroDivisionError("oops")
    with pytest.raises(InternalError, match=r"read\(\).*ZeroDivisionError"):
        game_result(sports_root, tmp_path, rules=fake_rules(read=read))


def test_a_sport_function_with_the_wrong_shape_is_an_internal_error(sports_root, tmp_path):
    with pytest.raises(InternalError, match="check\\(\\) must return a list"):
        game_result(sports_root, tmp_path, rules=fake_rules(check=lambda s, c: "fine"))
    with pytest.raises(InternalError, match="read\\(\\) must return a Reading"):
        game_result(sports_root, tmp_path, rules=fake_rules(read=lambda s, c: {"final": 1}))


# ------------------------------------------------------------------ drafts are never opened

def test_drafts_are_never_opened(sports_root, tmp_path, monkeypatch):
    d = Data(tmp_path)
    d.game("2026-11-05-1")
    d.put("s1/drafts/2026-11-05-1.yml", "{{{ garbage: [unclosed\n\t- \x00\n")
    d.put("s1/drafts/not-in-schedule.yml", "status: draft\nnonsense: true\n")
    d.put("s1/drafts/binary.yml", b"\xff\xfe\x00\x01")
    opened = []
    real_read_bytes, real_read_text, real_open = Path.read_bytes, Path.read_text, Path.open
    monkeypatch.setattr(Path, "read_bytes", lambda self: (opened.append(str(self)), real_read_bytes(self))[1])
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (opened.append(str(self)), real_read_text(self, *a, **k))[1])
    monkeypatch.setattr(Path, "open", lambda self, *a, **k: (opened.append(str(self)), real_open(self, *a, **k))[1])
    result = load(d, sports_root)
    assert result.problems == [] and list(season(result).games) == ["2026-11-05-1"]
    assert opened and not [p for p in opened if "/drafts/" in p or p.endswith("/drafts")]


def test_the_fixture_drafts_file_is_garbage_and_never_read(sports_root):
    garbage = FIXTURE_ROOT / "data/sample-2026-27/drafts/2026-11-19-1.yml"
    assert garbage.is_file()
    with pytest.raises(Exception):
        __import__("yaml").safe_load(garbage.read_text())
    league = league_for(sports_root, sample_data=True)
    assert load_data(FIXTURE_ROOT, league, league.sport_def, today=TODAY).problems == []


# ------------------------------------------------------------------ across seasons

def test_game_ids_must_be_unique_across_the_seasons_shown(sports_root, tmp_path):
    d = Data(tmp_path, seasons="- {id: s1, current: true}\n- {id: s0}\n")
    d.put("s0/teams.yml", TEAMS)
    d.put("s0/schedule.csv", HEAD + "x,2025-11-05,19:00,otters,ravens\n2026-11-05-1,2025-11-12,19:00,otters,ravens\n")
    (file, at), msg = only_error(load(d, sports_root))
    assert (file, at) == ("data/s0/schedule.csv", "1.game_id") and "also a game in season 's1'" in msg
    assert "(spreadsheet line 3)" in msg


def test_a_real_season_and_its_sample_may_reuse_game_ids(sports_root, tmp_path):
    d = Data(tmp_path, seasons="- {id: s1, current: true}\n- {id: x1, sample: true, stands_in_for: s1}\n")
    d.put("x1/teams.yml", TEAMS)
    d.put("x1/schedule.csv", SCHEDULE)
    assert load(d, sports_root).problems == []
    assert load(d, sports_root, sample_data=True).problems == []


def test_two_shown_sample_seasons_cannot_share_ids_but_hidden_ones_may(sports_root, tmp_path):
    seasons = ("- {id: s1, current: true}\n- {id: x1, sample: true, stands_in_for: s1}\n- {id: x0, sample: true}\n")
    d = Data(tmp_path, seasons=seasons)
    for sid in ("x1", "x0"):
        d.put(f"{sid}/teams.yml", TEAMS)
        d.put(f"{sid}/schedule.csv", SCHEDULE)
    assert load(d, sports_root).problems == []            # x0 is a sample season: hidden in real mode
    (file, at), _ = next(iter(errs(load(d, sports_root, sample_data=True)).items()))
    assert file == "data/x0/schedule.csv" and at.endswith(".game_id")


def test_every_season_is_loaded_and_checked_even_when_hidden(sports_root, tmp_path):
    d = Data(tmp_path, seasons="- {id: s1, current: true}\n- {id: x0, sample: true}\n")
    d.put("x0/teams.yml", "- {id: bad id, name: A, code: AA}\n")
    assert set(errs(load(d, sports_root))) == {("data/x0/teams.yml", "0.id")}


def test_problems_from_every_file_are_collected_together(sports_root, tmp_path):
    d = Data(tmp_path, teams="- {id: a1, name: A}\n", players="- {id: p, name: Full Name, team: nope}\n",
             schedule=HEAD + "g1,bad,19:00,a1,a1\n")
    d.game("zzz", "status: final\n")
    files = {f for (f, _) in errs(load(d, sports_root))}
    assert files == {f"{S1}/teams.yml", f"{S1}/players.yml", CSV, f"{S1}/games/zzz.yml"}
