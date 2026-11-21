"""Tests for scripts/core/sports.py: discovery, the sport.yml schema (every key with its path), loading
rules.py and sample.py, and arity checks. They use the fake sports in tests/fixtures/sports/."""
import pytest

from scripts.core.sports import (
    SITE_PATHS, SPORTS_ROOT, check_sport_spec, demo_sports, discover_sports, is_wrapped, load_all_sports, load_sport,
    normalise_spec, preview_entries, unwrap,
)
from scripts.core.model import SportDef
from scripts.core.problems import InternalError
import shutil
import yaml


def errors(problems):
    """{(file name, path): message}; two errors on one path overwrite each other, so use `messages` for those."""
    return {(p.file.rsplit("/", 1)[-1], p.at): p.message for p in problems if p.level == "error"}


def messages(problems):
    return [p.message for p in problems if p.level == "error"]


def spec_of(sports_root, sport="tiny"):
    return yaml.safe_load((sports_root / sport / "sport.yml").read_text(encoding="utf-8"))


def test_discovery_lists_folders_that_have_a_sport_yml(sports_root, tmp_path):
    assert discover_sports(sports_root) == ["bare", "broken", "other", "tiny", "twogroup", "typo"]
    (tmp_path / "empty").mkdir()
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "sport.yml").write_text("name: x\n", encoding="utf-8")
    assert discover_sports(tmp_path) == ["real"]
    assert discover_sports(tmp_path / "missing") == []


def test_a_valid_sport_loads_with_both_files(sports_root):
    sport, problems = load_sport("tiny", sports_root, with_sample=True)
    assert problems == [] and isinstance(sport, SportDef)
    assert sport.sample.LEAGUE_NAME == "Example Tiny League"
    assert callable(sport.rules.check) and callable(sport.rules.derive)
    assert sport.spec["games_per_day"] == 1 and sport.folder == sports_root / "tiny"


def test_the_smallest_valid_sport_gets_its_optional_keys_filled_in(sports_root):
    sport, problems = load_sport("other", sports_root, with_sample=True)
    assert problems == []
    s = sport.spec
    assert (s["games_per_day"], s["game_minutes"], s["options"], s["minimums"], s["leaderboards"]) == (1, 60, {}, {}, [])
    assert s["display"] == {"card": "rows", "card_foot": "note", "surface": "label", "card_head": "", "matchup": "vs"}
    assert s["words"]["surface"] == "" and s["stats"]["derived"] == [] and s["stats"]["team"] == []


def test_sample_py_is_only_loaded_when_asked(sports_root):
    assert load_sport("tiny", sports_root)[0].sample is None


def test_a_missing_readme_is_a_warning_and_a_missing_sample_is_an_error(sports_root):
    sport, problems = load_sport("bare", sports_root)
    assert sport is not None
    assert [(p.level, p.file.rsplit("/", 1)[-1]) for p in problems] == [("warning", "README.md")]
    sport, problems = load_sport("bare", sports_root, with_sample=True)
    assert sport is None and ("sample.py", "") in errors(problems)


def test_wrong_function_shapes_are_reported_with_the_signature_wanted(sports_root):
    sport, problems = load_sport("broken", sports_root, with_sample=True)
    assert sport is None
    msgs = " | ".join(messages(problems))
    assert "check() must take exactly 2 arguments: check(sheet, ctx)" in msgs
    assert "missing the function derive(counts, group)" in msgs
    assert "missing TEAMS" in msgs and "sheet() must take exactly 3 arguments" in msgs


def test_unknown_sport_folder(sports_root):
    sport, problems = load_sport("nope", sports_root)
    assert sport is None and "Available: bare, broken, other, tiny, twogroup, typo." in problems[0].message


def test_the_schema_reports_every_mistake_with_its_path(sports_root):
    sport, problems = load_sport("typo", sports_root)
    assert sport is None
    got = {at for (_, at) in errors(problems)}
    assert got >= {"default_layout", "gamez_per_day", "words.period.short", "line_score.shape", "options.periods.type",
                   "options.overtime.default", "standings.points.tie", "standings.tiebreakers.0",
                   "standings.forfeit.value.score", "stats.player.0.title", "leaderboards.0.stat",
                   "leaderboards.0.min.setting"}


def test_the_schema_checks_the_pieces_unit_by_unit(sports_root):
    base = spec_of(sports_root)

    def broken(**changes):
        return {p.at for p in check_sport_spec({**base, **changes}, "sport.yml") if p.level == "error"}

    assert broken() == set()
    assert "options.periods.min" in broken(options={"periods": {"type": "int", "default": 2, "min": "one"}})
    assert "options.p.values" in broken(options={"p": {"type": "int", "default": 1, "values": [1]}})
    assert "options.p.default" in broken(options={"p": {"type": "int", "default": 99, "max": 9}})
    assert "options.p.values" in broken(options={"p": {"type": "choice", "default": "a", "values": []}})
    assert "minimums.m.default" in broken(minimums={"m": {"default": "x"}})
    assert "display.card" in broken(display={"card": "grid"})
    assert "labels_by_layout.hockyy" in broken(labels_by_layout={"hockyy": {}})
    assert "positions.0" in broken(positions=["Skip"])
    assert "games_per_day" in broken(games_per_day=0)
    assert "stats" in broken(stats={"derived": []})                      # needs a counting group
    assert "leaderboards.0.group" in broken(leaderboards=[{"id": "a", "of": "player", "group": "nope", "stat": "pts", "label": "A"}])
    assert "leaderboards.1.id" in broken(leaderboards=[
        {"id": "a", "of": "player", "stat": "pts", "label": "A"}, {"id": "a", "of": "player", "stat": "pts", "label": "B"}])
    assert "standings.columns.0" in broken(standings={"columns": ["nope"]})


def test_team_stat_keys_are_allowed_as_standings_columns(sports_root):
    spec = spec_of(sports_root)
    assert check_sport_spec(spec, "sport.yml") == []
    spec["standings"]["columns"] = ["gp", "ends"]
    assert check_sport_spec(spec, "sport.yml") == []
    spec["stats"]["team"] = []
    assert [p.at for p in check_sport_spec(spec, "sport.yml")] == ["standings.columns.1"]


def test_an_empty_or_non_mapping_sport_yml(sports_root):
    assert check_sport_spec(None, "sport.yml")[0].message.startswith("This file is empty")
    assert check_sport_spec([1], "sport.yml")[0].at == ""
    required = {p.at for p in check_sport_spec({}, "sport.yml")}
    assert required == {"name", "default_layout", "words", "line_score", "standings", "stats"}


def test_decide_wrappers():
    assert is_wrapped({"value": 1, "decide": True}) and not is_wrapped({"value": 1, "other": 2})
    assert unwrap({"value": [1, 0], "decide": True}) == ([1, 0], True)
    assert unwrap({"score": [1, 0]}) == ({"score": [1, 0]}, False)


def test_load_all_sports_loads_every_folder_it_can(sports_root):
    sports, problems = load_all_sports(sports_root)
    assert sorted(s.id for s in sports) == ["other", "tiny", "twogroup"]
    assert {p.file.split("/")[-2] for p in problems if p.level == "error"} == {"bare", "broken", "typo"}


def test_normalise_spec_does_not_change_its_input(sports_root):
    spec = spec_of(sports_root, "other")
    before = yaml.safe_dump(spec)
    normalise_spec(spec)
    assert yaml.safe_dump(spec) == before


def test_gp_is_the_cores_and_cannot_be_a_sport_stat(sports_root):
    spec = spec_of(sports_root)
    spec["stats"]["player"].append({"key": "gp", "label": "GP", "title": "Games played"})
    [p] = check_sport_spec(spec, "sport.yml")
    assert p.at == "stats.player.1.key" and "worked out by the core" in p.message


def test_detail_and_note_templates_may_only_name_known_values(sports_root):
    spec = spec_of(sports_root)
    assert check_sport_spec(spec, "sport.yml") == []          # {gp}, {pts} and {value} are all known
    spec["leaderboards"][0]["detail"] = "{gp} GP, {pst} pts"
    spec["leaderboards"][1]["detail"] = "{pts"
    spec["leaderboards"][1]["min"]["stat"] = "games"
    spec["minimums"]["ppg_min_games"]["note"] = "Minimum {games} games."
    found = {p.at: p.message for p in check_sport_spec(spec, "sport.yml")}
    assert set(found) == {"leaderboards.0.detail", "leaderboards.1.detail", "leaderboards.1.min.stat",
                          "minimums.ppg_min_games.note"}
    assert "{pst} is not a value" in found["leaderboards.0.detail"] and "{pts}" in found["leaderboards.0.detail"]
    assert "not a valid template" in found["leaderboards.1.detail"]
    assert "{value}" in found["minimums.ppg_min_games.note"]


def test_a_sport_file_that_fails_to_import_is_an_internal_error_naming_it(sports_root, tmp_path):
    shutil.copytree(sports_root / "tiny", tmp_path / "crash", ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "crash" / "rules.py").write_text("import nothing_called_this\n", encoding="utf-8")
    with pytest.raises(InternalError) as info:
        load_sport("crash", tmp_path, root=tmp_path)
    assert "crash/rules.py" in str(info.value) and "ModuleNotFoundError" in str(info.value)
    assert isinstance(info.value.__cause__, ModuleNotFoundError)


# ---- line_score.periods: how many regulation periods (needed for forfeits scored 1-0 in every period)

def test_regulation_periods_reads_a_number_or_an_int_option():
    from scripts.core.sports import regulation_periods
    options = {"periods": {"type": "int", "default": 2}}
    assert regulation_periods({"line_score": {"periods": 4}}, {}) == 4
    spec = {"line_score": {"periods": "periods"}, "options": options}
    assert regulation_periods(spec, {}) == 2                      # the option's default
    assert regulation_periods(spec, {"periods": 3}) == 3          # the league's own setting
    assert regulation_periods({"line_score": {}}, {}) is None    # the sport does not say


def test_line_score_periods_must_be_a_number_or_name_an_int_option():
    from scripts.core.problems import Checker
    from scripts.core.sports import _check_line_score
    base = {"shape": "periods", "total_label": "Final", "corner": "Team"}
    opts = {"periods": {"type": "int", "default": 2}, "mode": {"type": "choice", "default": "a", "values": ["a"]}}
    def problems(value):
        c = Checker("sport.yml")
        _check_line_score(c, {**base, "periods": value}, opts)
        return {(p.at, p.message) for p in c.problems}
    assert problems(4) == set() and problems("periods") == set()
    assert any(at == "line_score.periods" for at, _ in problems(0))
    assert any("not an int option" in m for _, m in problems("mode"))
    assert any("not an int option" in m for _, m in problems("nope"))
    assert any(at == "line_score.periods" for at, _ in problems(True))
    assert any(at == "line_score.periods" for at, _ in problems([4]))


def test_forfeit_score_winner_must_be_higher():
    from scripts.core.problems import Checker
    from scripts.core.sports import _check_forfeit
    def problems(score):
        c = Checker("sport.yml")
        _check_forfeit(c, {"score": score}, "standings.forfeit")
        return [p.at for p in c.problems]
    assert problems([7, 0]) == [] and problems("per_period") == []
    assert problems([0, 7]) == ["standings.forfeit.score"]
    assert problems([3, 3]) == ["standings.forfeit.score"]


# ------------------------------------------------------------------ core extensions E3 and E4 (stage 5 spec, section 5)

def test_leaderboard_switches_are_booleans_and_a_typo_is_named(sports_root):
    spec = spec_of(sports_root)
    board = spec["leaderboards"][1]
    board.update({"zero": True, "playoffs": True, "home": False, "player_rank": False})
    assert check_sport_spec(spec, "sport.yml") == []
    for key in ("zero", "playoffs", "home", "player_rank"):
        spec["leaderboards"][1][key] = "yes"
        assert [p.at for p in check_sport_spec(spec, "sport.yml")] == [f"leaderboards.1.{key}"]
        spec["leaderboards"][1][key] = True
    spec["leaderboards"][1]["playoff"] = True                       # a typo is an unknown key, with its path
    [problem] = check_sport_spec(spec, "sport.yml")
    assert problem.at == "leaderboards.1.playoff" and "playoffs" in problem.message


def test_column_lists_are_checked_against_the_groups_and_their_stats(sports_root):
    spec = spec_of(sports_root)
    spec["stats"]["columns"] = {"player": {"table": ["ppg", "pts", "gp"], "totals": ["gp", "pts"], "log": ["pts"]}}
    assert check_sport_spec(spec, "sport.yml") == []
    spec["stats"]["columns"] = {"player": {"table": ["ppg"]}}                       # one list is enough
    assert check_sport_spec(spec, "sport.yml") == []

    def found(columns):
        spec["stats"]["columns"] = columns
        return {p.at: p.message for p in check_sport_spec(spec, "sport.yml") if p.level == "error"}

    got = found({"player": {"tabel": ["pts"], "table": ["pts", "nope", "pts", "ends"], "log": []}, "goalie": {"table": ["pts"]}})
    assert set(got) == {"stats.columns.player.tabel", "stats.columns.player.table.1", "stats.columns.player.table.2",
                        "stats.columns.player.table.3", "stats.columns.player.log", "stats.columns.goalie"}
    assert "'pts' is listed twice" in got["stats.columns.player.table.2"]      # team stats are not player columns
    assert "Use one of: player" in got["stats.columns.goalie"]
    assert set(found({"player": ["pts"]})) == {"stats.columns.player"}
    assert set(found(["pts"])) == {"stats.columns"}


def test_columns_is_not_a_stat_group(sports_root):
    spec = spec_of(sports_root)
    spec["stats"]["columns"] = {"player": {"table": ["pts"]}}
    spec["leaderboards"][0]["group"] = "columns"
    [problem] = check_sport_spec(spec, "sport.yml")
    assert problem.at == "leaderboards.0.group" and "Use one of: player" in problem.message
    assert normalise_spec(spec_of(sports_root))["stats"]["columns"] == {}


def test_player_only_switches_on_a_team_board_are_named(sports_root):
    """zero, playoffs and player_rank change how players are ranked; a team board would ignore them silently."""
    spec = spec_of(sports_root)
    spec["leaderboards"].append({"id": "ends", "of": "team", "stat": "ends", "label": "Ends won", "home": False})
    assert check_sport_spec(spec, "sport.yml") == []                 # home works on any board
    spec["leaderboards"][-1].update({"zero": True, "playoffs": True, "player_rank": False})
    found = {p.at: p.message for p in check_sport_spec(spec, "sport.yml")}
    assert set(found) == {"leaderboards.2.zero", "leaderboards.2.playoffs", "leaderboards.2.player_rank"}
    assert "of: player" in found["leaderboards.2.zero"]


# ------------------------------------------------------------------ `demo` (stage 5 spec, section 7.1)

def test_demo_is_an_optional_boolean_that_defaults_to_true(sports_root):
    sport, problems = load_sport("tiny", sports_root)
    assert problems == [] and sport.spec["demo"] is True
    spec = spec_of(sports_root)
    spec["demo"] = False
    assert check_sport_spec(spec, "sport.yml") == []
    assert normalise_spec(spec)["demo"] is False
    for bad in ("no", 0, None):
        spec["demo"] = bad
        assert errors(check_sport_spec(spec, "sport.yml")).keys() == {("sport.yml", "demo")}, bad


def test_the_stub_is_a_test_sport_and_the_real_sports_are_demos():
    stub, problems = load_sport("stub", SPORTS_ROOT)
    assert stub is not None and stub.spec["demo"] is False, problems
    assert "demo: false" in (SPORTS_ROOT / "stub" / "sport.yml").read_text(encoding="utf-8")
    basketball, _ = load_sport("basketball", SPORTS_ROOT)
    assert basketball.spec["demo"] is True
    assert demo_sports(SPORTS_ROOT) == {"basketball": "Basketball", "curling": "Curling", "hockey": "Hockey"}


def test_demo_sports_needs_a_sample_and_a_demo_that_is_not_false(sports_root, tmp_path):
    found = demo_sports(sports_root)
    assert "bare" not in found                       # no sample.py
    assert found["tiny"] == "Tiny" and "typo" in found
    quiet = tmp_path / "quiet"
    quiet.mkdir()
    for name in ("sport.yml", "sample.py"):
        (quiet / name).write_text(("demo: false\n" if name == "sport.yml" else "") + "name: Quiet\n", encoding="utf-8")
    assert demo_sports(tmp_path) == {}
    assert demo_sports(tmp_path / "nowhere") == {}


def test_preview_entries_give_the_name_and_the_address_on_the_live_site():
    assert preview_entries(["basketball"], SPORTS_ROOT) == [{"id": "basketball", "name": "Basketball", "url": "/basketball/"}]
    assert preview_entries([], SPORTS_ROOT) == []


def test_the_site_paths_are_the_ones_the_site_builds():
    assert SITE_PATHS == ("archive", "assets", "calendar", "games", "landing", "players", "preview", "rules", "schedule",
                          "sheets", "stats", "teams")
    assert not set(SITE_PATHS) & set(discover_sports(SPORTS_ROOT))


# ------------------------------------------------------------------ `blurb` (landing page plan, section 5)

def test_blurb_is_an_optional_one_line_text_of_at_most_100_characters(sports_root):
    spec = spec_of(sports_root)
    assert "blurb" not in spec and check_sport_spec(spec, "sport.yml") == []          # optional in the schema
    assert normalise_spec(spec).get("blurb") is None
    assert check_sport_spec({**spec, "blurb": "Two halves, a clock and a horn."}, "sport.yml") == []
    assert check_sport_spec({**spec, "blurb": "x" * 100}, "sport.yml") == []
    found = _problems_at({**spec, "blurb": "x" * 101})
    assert set(found) == {"blurb"} and "101 characters" in found["blurb"] and "at most 100" in found["blurb"]
    assert "one line" in _problems_at({**spec, "blurb": "Two halves.\nA clock."})["blurb"]
    for bad in ("", "  ", 5, ["a"], None):
        assert set(_problems_at({**spec, "blurb": bad})) == {"blurb"}, bad


def test_the_real_sports_have_a_blurb_the_landing_page_can_show():
    for sport_id in demo_sports(SPORTS_ROOT):
        sport, problems = load_sport(sport_id, SPORTS_ROOT)
        assert sport is not None and problems == [], problems
        assert 0 < len(sport.spec["blurb"]) <= 100 and "\n" not in sport.spec["blurb"].strip(), sport_id


# ------------------------------------------------------------------ core extensions E8, E9 and E10 (curling spec, section 6)

def _problems_at(spec):
    return {p.at: p.message for p in check_sport_spec(spec, "sport.yml") if p.level == "error"}


def test_words_extra_is_optional_and_needs_one_and_short(sports_root):
    base = spec_of(sports_root)
    assert _problems_at({**base, "words": {**base["words"], "extra": {"one": "Extra end", "short": "EE"}}}) == {}
    assert "extra" not in base["words"] and _problems_at(base) == {}
    words = lambda extra: _problems_at({**base, "words": {**base["words"], "extra": extra}})   # noqa: E731
    assert set(words({"one": "Extra end"})) == {"words.extra.short"}
    assert set(words({"one": "Extra end", "short": ""})) == {"words.extra.short"}
    assert set(words({"one": "x", "short": "X", "many": "xs"})) == {"words.extra.many"}
    assert set(words("EE")) == {"words.extra"}


def test_display_results_legend_is_a_list_of_kind_and_text(sports_root):
    base = spec_of(sports_root)
    display = lambda legend: _problems_at({**base, "display": {**base["display"], "results_legend": legend}})   # noqa: E731
    assert display([{"kind": "hammer", "text": "Hammer in end 1"}, {"kind": "x", "text": "Not played"}]) == {}
    assert display([]) == {}
    assert set(display([{"kind": "star", "text": "x"}])) == {"display.results_legend.0.kind"}
    assert set(display([{"kind": "mark"}])) == {"display.results_legend.0.text"}
    assert display([{"kind": "limit", "text": "At the limit", "mark": "5"}]) == {}
    assert set(display("Hammer")) == {"display.results_legend"}


def test_display_team_sub_must_be_one_of_the_positions(sports_root):
    base = spec_of(sports_root)

    def sub(value, positions):
        return _problems_at({**base, "positions": positions, "display": {**base["display"], "team_sub": value}})

    assert sub("skip", ["lead", "skip"]) == {}
    assert set(sub("coach", ["lead", "skip"])) == {"display.team_sub"}
    assert set(sub("skip", [])) == {"display.team_sub"}           # the sport lists no positions
    assert "display.team_sub" in _problems_at({**base, "display": {**base["display"], "team_sub": "skip"}})
    assert "positions" not in _problems_at({**base, "positions": ["skip"], "display": {"team_sub": "skip"}})


def test_the_shipped_keys_do_not_change_what_a_sport_without_them_gets(sports_root):
    sport, _ = load_sport("other", sports_root)
    assert "results_legend" not in sport.spec["display"] and "team_sub" not in sport.spec["display"]
    assert "extra" not in sport.spec["words"]


# ------------------------------------------------------------------ hockey's core extensions (E12-E15)

def _two_groups(sports_root):
    spec = spec_of(sports_root)
    spec["stats"] = {"skater": [{"key": "g", "label": "G", "title": "Goals"}],
                     "goalie": [{"key": "ga", "label": "GA", "title": "Goals against"},
                                {"key": "sa", "label": "SA", "title": "Shots against"}],
                     "derived": [{"key": "gaa", "label": "GAA", "title": "Goals against average", "places": 2, "group": "goalie"},
                                 {"key": "sv", "label": "SV%", "title": "Save percentage", "places": 3, "format": "dot",
                                  "group": "goalie"}],
                     "team": spec["stats"]["team"],
                     "labels": {"skater": "Skaters", "goalie": "Goalies"}}
    spec["leaderboards"] = [
        {"id": "g", "of": "player", "group": "skater", "stat": "g", "label": "Goals", "columns": ["g", "gp"]},
        {"id": "gaa", "of": "player", "group": "goalie", "stat": "gaa", "label": "GAA", "order": "asc", "zero": True}]
    return spec


def test_order_format_group_labels_and_board_columns_are_allowed(sports_root):
    spec = _two_groups(sports_root)
    assert check_sport_spec(spec, "sport.yml") == []
    assert normalise_spec(spec_of(sports_root))["stats"]["labels"] == {}


def test_order_must_be_asc_or_desc_and_is_for_player_boards(sports_root):
    spec = _two_groups(sports_root)
    spec["leaderboards"][1]["order"] = "up"
    spec["leaderboards"].append({"id": "ends", "of": "team", "stat": "ends", "label": "Ends", "order": "asc", "columns": ["ends"]})
    got = {p.at: p.message for p in check_sport_spec(spec, "sport.yml") if p.level == "error"}
    assert set(got) == {"leaderboards.1.order", "leaderboards.2.order", "leaderboards.2.columns"}
    assert "asc" in got["leaderboards.1.order"] and "of: player" in got["leaderboards.2.order"]


def test_format_is_decimal_or_dot_and_only_for_a_derived_stat(sports_root):
    spec = _two_groups(sports_root)
    spec["stats"]["derived"][1]["format"] = "percent"
    spec["stats"]["skater"][0]["format"] = "dot"
    assert {p.at for p in check_sport_spec(spec, "sport.yml")} == {"stats.derived.1.format", "stats.skater.0.format"}


def test_a_derived_stat_group_must_be_a_group_and_limits_where_it_is_offered(sports_root):
    spec = _two_groups(sports_root)
    spec["leaderboards"][0]["stat"] = "sv"                         # a goalie rate on a skater board
    spec["stats"]["columns"] = {"skater": {"table": ["g", "gaa"]}}
    got = {p.at for p in check_sport_spec(spec, "sport.yml")}
    assert got == {"leaderboards.0.stat", "stats.columns.skater.table.1"}
    spec = _two_groups(sports_root)
    spec["stats"]["derived"][0]["group"] = "keeper"
    assert {p.at for p in check_sport_spec(spec, "sport.yml")} == {"stats.derived.0.group"}


def test_stats_labels_name_a_group_and_are_not_a_group_themselves(sports_root):
    spec = _two_groups(sports_root)
    spec["stats"]["labels"]["keeper"] = "Keepers"
    spec["stats"]["labels"]["skater"] = 4
    assert {p.at for p in check_sport_spec(spec, "sport.yml")} == {"stats.labels.keeper", "stats.labels.skater"}
    spec = _two_groups(sports_root)
    spec["leaderboards"][0]["group"] = "labels"
    assert {p.at for p in check_sport_spec(spec, "sport.yml")} == {"leaderboards.0.group"}


def test_board_columns_are_stats_of_the_boards_group(sports_root):
    spec = _two_groups(sports_root)
    spec["leaderboards"][0]["columns"] = ["g", "ga", "g", "nope"]
    spec["leaderboards"][1]["columns"] = []
    got = {p.at for p in check_sport_spec(spec, "sport.yml")}
    assert got == {"leaderboards.0.columns.1", "leaderboards.0.columns.2", "leaderboards.0.columns.3", "leaderboards.1.columns"}


# ------------------------------------------------------------------ slo-pitch core extensions (E23-E27)

def _with(sports_root, **changes):
    """tiny's sport.yml with some top-level keys replaced (a dict value is merged one level deep)."""
    base = spec_of(sports_root)
    return {**base, **{k: ({**base.get(k, {}), **v} if isinstance(v, dict) else v) for k, v in changes.items()}}


def test_when_names_an_option_and_values_it_allows_on_stats_and_boards(sports_root):
    base = spec_of(sports_root)
    stats = lambda when: _problems_at({**base, "stats": {**base["stats"], "player": [   # noqa: E731
        {"key": "pts", "label": "PTS", "title": "Points", "when": when}]}})
    assert stats({"overtime": ["overtime"]}) == {} and stats({"mercy": [True], "periods": [2, 3]}) == {}
    assert set(stats({"nope": ["x"]})) == {"stats.player.0.when.nope"}
    assert set(stats({"overtime": ["sudden"]})) == {"stats.player.0.when.overtime.0"}
    assert set(stats({"overtime": "overtime"})) == {"stats.player.0.when.overtime"}
    assert set(stats({"overtime": []})) == {"stats.player.0.when.overtime"}
    assert set(stats({})) == {"stats.player.0.when"}
    assert set(stats(["overtime"])) == {"stats.player.0.when"}
    derived = {**base["stats"]["derived"][0], "when": {"mercy": [True]}}
    assert _problems_at({**base, "stats": {**base["stats"], "derived": [derived]}}) == {}
    board = lambda when: _problems_at({**base, "leaderboards": [{**base["leaderboards"][0], "when": when}]})   # noqa: E731
    assert board({"mercy": [True]}) == {} and set(board({"mercy": ["yes"]})) == {"leaderboards.0.when.mercy.0"}
    team = [{"key": "ends", "label": "EW", "title": "Ends won", "when": {"mercy": [True]}}]
    assert set(_problems_at({**base, "stats": {**base["stats"], "team": team}})) == {"stats.team.0.when"}     # not for team stats


def test_when_matches_reads_the_effective_options():
    from scripts.core.sports import when_matches
    assert when_matches(None, {}) and when_matches({}, {})
    assert when_matches({"batting": ["optional", "every_game"]}, {"batting": "optional", "x": 1})
    assert not when_matches({"batting": ["optional"]}, {"batting": "none"})
    assert not when_matches({"a": [1], "b": [2]}, {"a": 1, "b": 3})


def test_a_board_minimum_may_be_per_team_game_but_not_with_the_cap(sports_root):
    base = spec_of(sports_root)
    minimum = lambda m: _problems_at({**base, "leaderboards": [{**base["leaderboards"][1], "min": m}]})   # noqa: E731
    assert minimum({"stat": "gp", "setting": "ppg_min_games", "per_team_game": True}) == {}
    assert set(minimum({"stat": "gp", "setting": "ppg_min_games", "per_team_game": "yes"})) == {"leaderboards.0.min.per_team_game"}
    both = {"stat": "gp", "setting": "ppg_min_games", "per_team_game": True, "cap_at_team_games": True}
    assert set(minimum(both)) == {"leaderboards.0.min.per_team_game"}


def test_display_card_head_and_matchup_are_closed_lists(sports_root):
    base = spec_of(sports_root)
    display = lambda **d: _problems_at({**base, "display": {**base["display"], **d}})   # noqa: E731
    assert display(card_head="status_surface", matchup="at") == {} and display(card_head="", matchup="vs") == {}
    assert set(display(card_head="eyebrow")) == {"display.card_head"}
    assert set(display(matchup="versus")) == {"display.matchup"}


def test_a_legend_mark_option_names_an_int_option(sports_root):
    base = spec_of(sports_root)
    legend = lambda item: _problems_at({**base, "display": {**base["display"], "results_legend": [   # noqa: E731
        {"kind": "limit", "text": "Limit", **item}]}})
    assert legend({"mark_option": "periods"}) == {} and legend({"mark": "5"}) == {}
    assert set(legend({"mark_option": "overtime"})) == {"display.results_legend.0.mark_option"}     # a choice, not an int
    assert set(legend({"mark_option": "missing"})) == {"display.results_legend.0.mark_option"}
    assert set(legend({"mark": "5", "mark_option": "periods"})) == {"display.results_legend.0.mark_option"}
    assert set(legend({"mark": 5})) == {"display.results_legend.0.mark"}
