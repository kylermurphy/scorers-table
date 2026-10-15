"""Tests for scripts/core/config.py: league.yml required keys, defaults, unknown keys with paths, layout ids,
sport discovery, option types, placeholders, season overrides, the league-colour gate (real Gold and Navy)
and the logo check. They use the fake sports in tests/fixtures/sports/ (`tiny`, `other`)."""
from pathlib import Path

import pytest
import yaml

from scripts.core.config import (
    FALLBACK_STANDINGS, LEAGUE_KEYS, REQUIRED_KEYS, build_league, deep_merge, default_code, effective_settings,
    load_league,
)
from scripts.core.model import LAYOUTS, League

ROOT = Path(__file__).resolve().parent.parent
GOLD, NAVY = "#C98A12", "#1D3A6E"


def make(sports_root, root=None, **extra):
    """build_league on the smallest valid league.yml plus `extra` keys; returns (League | None, problems)."""
    raw = {"name": "Example Valley Stub League", "sport": "tiny", "timezone": "America/Toronto", **extra}
    return build_league(raw, sports_root=sports_root, root=root or ROOT)


def errors(problems):
    """{path: message} for the errors; fails the test if two errors share a path."""
    found = {p.at: p.message for p in problems if p.level == "error"}
    assert len(found) == sum(p.level == "error" for p in problems)
    return found


def ok(sports_root, root=None, **extra) -> League:
    league, problems = make(sports_root, root, **extra)
    assert not errors(problems), problems
    assert league is not None
    return league


# ------------------------------------------------------------------ required keys and defaults

def test_the_smallest_league_gets_every_default(sports_root):
    lg = ok(sports_root)
    assert (lg.name, lg.short_name, lg.sport, lg.timezone) == ("Example Valley Stub League",) * 2 + ("tiny", "America/Toronto")
    assert lg.code == "EVSL"                              # initials of the name
    assert lg.layout == "classic"                         # the sport's default_layout
    assert lg.tagline == "Tiny"                           # the sport's name
    assert lg.footer_line is None                         # the season's venue is used later
    assert (lg.time_format, lg.lang) == ("12h", "en")
    assert (lg.search_engines, lg.sample_data, lg.preview, lg.photos) == (False, False, True, False)
    assert (lg.colour, lg.colour_dark, lg.logo, lg.contact, lg.contact_href, lg.github) == (None,) * 6
    assert lg.game_minutes == 45                          # the sport's game_minutes
    assert lg.rules == {"periods": 2, "overtime": "none", "mercy": False, "venue_note": ""}
    assert lg.minimums == {"ppg_min_games": 0}
    assert lg.sport_def.id == "tiny" and lg.sport_def.name == "Tiny"


def test_league_is_frozen(sports_root):
    with pytest.raises(Exception):
        ok(sports_root).name = "x"


@pytest.mark.parametrize("missing", REQUIRED_KEYS)
def test_each_required_key_is_named(sports_root, missing):
    raw = {"name": "A League", "sport": "tiny", "timezone": "UTC"}
    del raw[missing]
    league, problems = build_league(raw, sports_root=sports_root, root=ROOT)
    assert league is None
    assert errors(problems)[missing] == f"is required. Add a '{missing}:' line."
    assert all(p.file == "league.yml" for p in problems)


def test_an_empty_file_and_a_non_mapping_are_errors(sports_root):
    assert build_league(None, sports_root=sports_root, root=ROOT)[0] is None
    league, problems = build_league(["a"], sports_root=sports_root, root=ROOT)
    assert league is None and problems[0].level == "error"


def test_short_name_code_tagline_footer_and_contact(sports_root):
    lg = ok(sports_root, short_name="Valley Stub", code="evs", tagline="Thursday stub", footer_line="Main St Gym",
            contact="league@example.com")
    assert (lg.short_name, lg.code, lg.tagline, lg.footer_line) == ("Valley Stub", "EVS", "Thursday stub", "Main St Gym")
    assert (lg.contact, lg.contact_href) == ("league@example.com", "mailto:league@example.com")
    assert ok(sports_root, contact="https://example.com/contact").contact_href == "https://example.com/contact"


def test_default_code_is_initials_up_to_four_letters():
    assert default_code("Example Valley Stub League") == "EVSL"
    assert default_code("Thunder Bay Masters Basketball League") == "TBMB"
    assert default_code("Otters") == "O"
    assert default_code("1234") == "L"


# ------------------------------------------------------------------ unknown keys and bad values

def test_unknown_top_level_key_is_an_error_with_a_suggestion(sports_root):
    _, problems = make(sports_root, colur="#1D3A6E", search_engine=True)
    e = errors(problems)
    assert "Did you mean 'colour'?" in e["colur"]
    assert "Did you mean 'search_engines'?" in e["search_engine"]


def test_unknown_nested_keys_name_their_path(sports_root):
    _, problems = make(sports_root, rules={"perods": 3}, standings={"point": {}}, stats={"minimum": {}},
                       calendar={"minutes": 1}, github={"repo": "a/b", "brach": "x"}, labels={"nope": "x"})
    e = errors(problems)
    assert "Did you mean 'periods'?" in e["rules.perods"]
    assert "Did you mean 'points'?" in e["standings.point"]
    assert "Did you mean 'minimums'?" in e["stats.minimum"]
    assert "calendar.minutes" in e and "github.brach" in e and "labels.nope" in e


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_id_is_accepted(sports_root, layout):
    assert ok(sports_root, layout=layout).layout == layout


def test_unknown_layout_lists_the_ids(sports_root):
    league, problems = make(sports_root, layout="clasic")
    assert league is None
    assert "Did you mean 'classic'?" in errors(problems)["layout"]
    assert "basketball, curling, hockey, slopitch, classic, scoreboard" in errors(problems)["layout"]


def test_layout_default_comes_from_the_sport(sports_root):
    assert ok(sports_root, sport="other").layout == "curling"


@pytest.mark.parametrize("key, value", [
    ("name", ""), ("name", 5), ("short_name", ""), ("timezone", 5), ("time_format", "13h"), ("lang", "english!"),
    ("search_engines", "no"), ("sample_data", 1), ("preview", None), ("photos", "yes"), ("code", "TOOLONG"),
    ("code", "A1"), ("tagline", ""), ("contact", "not a contact"), ("calendar", {"game_minutes": 0}),
])
def test_bad_values_are_errors_at_their_key(sports_root, key, value):
    league, problems = make(sports_root, **{key: value})
    assert league is None
    assert any(p.level == "error" and p.at.split(".")[0] == key for p in problems), problems


def test_timezone_must_be_an_iana_name(sports_root):
    assert ok(sports_root, timezone="Europe/London").timezone == "Europe/London"
    _, problems = make(sports_root, timezone="Toronto")
    assert "'Toronto' is not a time zone name" in errors(problems)["timezone"]


def test_github_passes_through_with_a_default_branch(sports_root):
    assert ok(sports_root, github={"repo": "my-league/website"}).github == {"repo": "my-league/website", "branch": "main"}
    _, problems = make(sports_root, github={"repo": "nope"})
    assert "github.repo" in errors(problems)
    _, problems = make(sports_root, github={"branch": "main"})
    assert errors(problems)["github.repo"].startswith("is required")


# ------------------------------------------------------------------ sports

def test_unknown_sport_lists_the_available_folders(sports_root):
    league, problems = make(sports_root, sport="tinny")
    assert league is None
    msg = errors(problems)["sport"]
    assert "'tinny' is not a sport folder" in msg and "Did you mean 'tiny'?" in msg
    assert "Available: bare, broken, other, tiny, typo." in msg


def test_a_sport_with_a_bad_sport_yml_stops_the_league_and_names_that_file(sports_root):
    league, problems = make(sports_root, sport="typo")
    assert league is None
    assert any(p.file.endswith("typo/sport.yml") and p.at == "line_score.shape" for p in problems)


def test_other_problems_are_still_found_when_the_sport_is_unknown(sports_root):
    _, problems = make(sports_root, sport="nope", timezone="Nowhere/Land", layout="x")
    assert {"sport", "timezone", "layout"} <= set(errors(problems))


# ------------------------------------------------------------------ rules, standings, minimums, labels

def test_rules_are_checked_against_the_sports_options(sports_root):
    lg = ok(sports_root, rules={"periods": 4, "overtime": "overtime", "mercy": True})
    assert lg.rules == {"periods": 4, "overtime": "overtime", "mercy": True, "venue_note": ""}
    _, problems = make(sports_root, rules={"periods": "four", "overtime": "sudden", "mercy": "no"})
    e = errors(problems)
    assert "whole number from 1 to 9" in e["rules.periods"]
    assert "Use one of: none, overtime." in e["rules.overtime"]
    assert "true or false" in e["rules.mercy"]
    assert "from 1 to 9" in errors(make(sports_root, rules={"periods": 12})[1])["rules.periods"]


def test_standings_merge_over_the_sports_defaults(sports_root):
    lg = ok(sports_root, standings={"points": {"win": 3}, "period_points": 1, "tiebreakers": ["wins"]})
    s = lg.standings
    assert s["points"] == {"win": 3, "tie": 1, "loss": 0, "ot_win": 3, "ot_loss": 0}   # tie and loss kept
    assert (s["period_points"], s["rank_by"], s["ties"]) == (1, "points", True)
    assert s["tiebreakers"] == ["wins"]
    assert s["forfeit"] == {"score": [1, 0]}                                           # the sport's, unwrapped
    assert s["columns"][-1] == "ends"                                                  # the sport's team stat


def test_ot_points_default_to_win_and_loss_unless_set(sports_root):
    assert ok(sports_root, standings={"points": {"win": 3, "loss": 1}}).standings["points"]["ot_win"] == 3
    pts = ok(sports_root, standings={"points": {"ot_win": 2, "ot_loss": 1}}).standings["points"]
    assert (pts["ot_win"], pts["ot_loss"]) == (2, 1)


def test_standings_checks_every_key(sports_root):
    _, problems = make(sports_root, standings={
        "rank_by": "rank", "points": {"win": "three", "draw": 1}, "period_points": -1, "ties": "no",
        "forfeit": {"score": [7]}, "tiebreakers": ["head2head", {"diff": {"cap": 0}}, {"wins": {"cap": 1}}],
        "columns": ["gp", "xx", "gp"], "playoffs": ""})
    e = errors(problems)
    for path in ("standings.rank_by", "standings.points.win", "standings.points.draw", "standings.period_points",
                 "standings.ties", "standings.forfeit.score", "standings.tiebreakers.0",
                 "standings.tiebreakers.1.diff.cap", "standings.tiebreakers.2.wins", "standings.columns.1",
                 "standings.columns.2", "standings.playoffs"):
        assert path in e, (path, sorted(e))
    assert "Did you mean 'head_to_head'?" in e["standings.tiebreakers.0"]


def test_standings_accepts_the_documented_forms(sports_root):
    lg = ok(sports_root, standings={"forfeit": {"score": "per_period"}, "rank_by": "win_pct",
                                    "tiebreakers": ["head_to_head", {"diff": {"cap": 7}}, "points_for"],
                                    "columns": ["gp", "w", "ends"], "playoffs": "Top four."})
    assert lg.standings["forfeit"] == {"score": "per_period"} and lg.standings["playoffs"] == "Top four."
    assert lg.standings["tiebreakers"][1] == {"diff": {"cap": 7}}


def test_a_decide_wrapper_is_not_allowed_in_league_yml(sports_root):
    _, problems = make(sports_root, standings={"forfeit": {"value": {"score": [1, 0]}, "decide": True}})
    assert "standings.forfeit.value" in errors(problems)


def test_minimums_labels_and_game_minutes(sports_root):
    lg = ok(sports_root, stats={"minimums": {"ppg_min_games": 3}}, calendar={"game_minutes": 90},
            labels={"next": "Next draw"}, layout="scoreboard")
    assert lg.minimums == {"ppg_min_games": 3} and lg.game_minutes == 90
    assert lg.labels == {"results": "Latest results", "next": "Next draw", "leaders": "Buckets"}   # layout label, then league
    e = errors(make(sports_root, stats={"minimums": {"ppg_min_games": -1, "other": 2}})[1])
    assert "stats.minimums.ppg_min_games" in e and "stats.minimums.other" in e


# ------------------------------------------------------------------ Unset means placeholder

def test_every_decide_setting_is_a_placeholder_until_set(sports_root):
    lg = ok(sports_root)
    assert [(p.setting, p.text) for p in lg.placeholders] == [
        ("rules.overtime", "Overtime"), ("standings.forfeit", "Forfeit"),
        ("standings.tiebreakers", "Tiebreakers"), ("stats.minimums.ppg_min_games", "Ppg min games")]


def test_setting_a_value_removes_its_placeholder_even_when_it_equals_the_default(sports_root):
    lg = ok(sports_root, rules={"overtime": "none"}, standings={"tiebreakers": ["head_to_head", "diff", "points_for"]},
            stats={"minimums": {"ppg_min_games": 0}})
    assert [p.setting for p in lg.placeholders] == ["standings.forfeit"]


def test_a_setting_that_is_not_decide_never_becomes_a_placeholder(sports_root):
    lg = ok(sports_root, sport="other")
    assert lg.placeholders == ()


def test_the_default_is_still_used_while_a_setting_is_a_placeholder(sports_root):
    lg = ok(sports_root)
    assert lg.rules["overtime"] == "none" and lg.standings["tiebreakers"] == ["head_to_head", "diff", "points_for"]


# ------------------------------------------------------------------ season overrides

def test_overrides_deep_merge_over_the_league(sports_root):
    lg = ok(sports_root, standings={"points": {"win": 2, "tie": 1}})
    settings, problems = effective_settings(lg, {"standings": {"points": {"win": 3, "tie": 1, "loss": 0}},
                                                 "rules": {"periods": 4}, "stats": {"minimums": {"ppg_min_games": 5}}})
    assert not problems
    assert settings.standings["points"] == {"win": 3, "tie": 1, "loss": 0, "ot_win": 3, "ot_loss": 0}   # ot_win follows win
    assert settings.rules["periods"] == 4 and settings.rules["overtime"] == "none"
    assert settings.minimums == {"ppg_min_games": 5}
    assert lg.standings["points"]["win"] == 2 and lg.rules["periods"] == 2                           # the league is unchanged


def test_no_overrides_gives_the_leagues_own_settings(sports_root):
    lg = ok(sports_root)
    settings, problems = effective_settings(lg, None)
    assert not problems and settings.standings == lg.standings and settings.rules == lg.rules


def test_bad_overrides_are_named_with_the_callers_path_and_file(sports_root):
    lg = ok(sports_root)
    _, problems = effective_settings(lg, {"standings": {"points": {"win": "x"}}, "rules": {"periodz": 1}, "colour": "#fff"},
                                     file="data/seasons.yml", at="2.overrides")
    assert {p.file for p in problems} == {"data/seasons.yml"}
    assert set(errors(problems)) == {"2.overrides.standings.points.win", "2.overrides.rules.periodz", "2.overrides.colour"}
    _, problems = effective_settings(lg, "nonsense", at="0.overrides")
    assert errors(problems)["0.overrides"].startswith("must be a block")


def test_deep_merge_replaces_lists_and_leaves_its_inputs_alone():
    base = {"a": {"b": 1, "c": [1, 2]}, "d": 1}
    over = {"a": {"c": [9]}, "e": {"f": 1}}
    out = deep_merge(base, over)
    assert out == {"a": {"b": 1, "c": [9]}, "d": 1, "e": {"f": 1}}
    out["a"]["b"] = 99
    assert base["a"]["b"] == 1 and over["e"] == {"f": 1}


# ------------------------------------------------------------------ the league-colour gate (4.6)

def test_gold_stops_the_build_with_messages_that_name_colour(sports_root):
    league, problems = make(sports_root, colour=GOLD)
    assert league is None
    bad = [p for p in problems if p.level == "error"]
    assert bad and {p.at for p in bad} == {"colour"}                   # no colour_dark set: all point at colour
    assert all(p.file == "league.yml" for p in bad)
    assert all(p.message.startswith(f"league.yml colour {GOLD}: ") for p in bad)      # verbatim from the gate
    assert any("white text on it" in p.message and "2.9:1" in p.message for p in bad)


def test_navy_passes(sports_root):
    lg = ok(sports_root, colour=NAVY)
    assert lg.colour == NAVY and lg.colour_dark is None


def test_colour_is_stored_upper_case(sports_root):
    assert ok(sports_root, colour="#1d3a6e").colour == "#1D3A6E"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_gold_is_checked_against_the_chosen_layout(sports_root, layout):
    league, problems = make(sports_root, colour=GOLD, layout=layout)
    assert league is None and {p.at for p in problems if p.level == "error"} <= {"colour"}


def test_a_bad_dark_colour_is_named_colour_dark(sports_root):
    league, problems = make(sports_root, colour=NAVY, colour_dark=GOLD)
    assert league is None
    bad = [p for p in problems if p.level == "error"]
    assert bad and {p.at for p in bad} == {"colour_dark"}
    assert all(p.message.startswith(f"league.yml colour_dark {GOLD}: ") and "theme" in p.message for p in bad)


def test_navy_with_a_good_dark_colour_passes(sports_root):
    lg = ok(sports_root, colour=NAVY, colour_dark="#3b6fd0")
    assert lg.colour_dark == "#3B6FD0"


@pytest.mark.parametrize("key, value", [("colour", "navy"), ("colour", "#12345"), ("colour", "#GGGGGG"),
                                         ("colour", 5), ("colour_dark", "blue")])
def test_a_badly_formed_colour_is_reported_at_its_own_key(sports_root, key, value):
    extra = {key: value} if key == "colour" else {"colour": NAVY, key: value}
    league, problems = make(sports_root, **extra)
    assert league is None and key in errors(problems)
    assert "#RRGGBB" in errors(problems)[key] or "six hex digits" in errors(problems)[key]


def test_colour_dark_alone_is_an_error(sports_root):
    league, problems = make(sports_root, colour_dark=NAVY)
    assert league is None and "needs 'colour'" in errors(problems)["colour_dark"]


def test_no_colour_means_no_gate(sports_root):
    lg = ok(sports_root)
    assert lg.colour is None and lg.colour_dark is None


# ------------------------------------------------------------------ logo

def test_a_missing_logo_is_an_error(sports_root, repo):
    league, problems = make(sports_root, repo, logo="assets/league/logo.svg")
    assert league is None
    assert "'assets/league/logo.svg' does not exist" in errors(problems)["logo"]


def test_an_existing_logo_is_accepted(sports_root, repo):
    (repo / "assets" / "league").mkdir(parents=True)
    (repo / "assets" / "league" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    assert ok(sports_root, repo, logo="assets/league/logo.svg").logo == "assets/league/logo.svg"


@pytest.mark.parametrize("logo", ["/assets/logo.svg", "../logo.svg", "assets/logo.jpg", "https://example.com/l.svg"])
def test_a_logo_must_be_a_repo_svg_or_png_path(sports_root, repo, logo):
    (repo / "assets").mkdir()
    (repo / "assets" / "logo.jpg").write_text("x", encoding="utf-8")
    league, problems = make(sports_root, repo, logo=logo)
    assert league is None and "logo" in errors(problems)


# ------------------------------------------------------------------ loading from a file

def write(root, text):
    path = root / "league.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_league_reads_the_file_and_names_it_relative_to_the_root(sports_root, repo):
    write(repo, "name: A Stub League\nsport: tiny\ntimezone: UTC\nbogus: 1\n")
    league, problems = load_league(sports_root=sports_root, root=repo)
    assert league is None
    assert [(p.file, p.at) for p in problems] == [("league.yml", "bogus")]


def test_load_league_success(sports_root, repo):
    write(repo, "name: A Stub League\nsport: tiny\ntimezone: UTC\n")
    league, problems = load_league(sports_root=sports_root, root=repo)
    assert problems == [] and league.code == "ASL"


def test_load_league_reports_broken_yaml_and_a_missing_file(sports_root, repo):
    write(repo, "name: [oops\n")
    assert load_league(sports_root=sports_root, root=repo)[0] is None
    assert "not valid YAML" in load_league(sports_root=sports_root, root=repo)[1][0].message
    (repo / "league.yml").unlink()
    league, problems = load_league(sports_root=sports_root, root=repo)
    assert league is None and problems[0].file == "league.yml"


# ------------------------------------------------------------------ the template that ships

def test_the_shipped_league_yml_parses_and_uses_only_known_keys():
    raw = yaml.safe_load((ROOT / "league.yml").read_text(encoding="utf-8"))
    assert set(raw) <= set(LEAGUE_KEYS) and set(REQUIRED_KEYS) <= set(raw)
    assert raw["sport"] == "stub" and raw["sample_data"] is True
    assert raw["timezone"] == "UTC" and raw["name"] == "Example Valley Stub League"


def test_every_shipped_key_is_described_in_a_comment():
    text = (ROOT / "league.yml").read_text(encoding="utf-8")
    for key in LEAGUE_KEYS:
        assert f"{key}:" in text, f"league.yml has no line for {key}"


@pytest.mark.skipif(not (ROOT / "sports" / "stub" / "sport.yml").is_file(), reason="sports/stub is another package's")
def test_the_shipped_league_loads_with_the_real_stub_sport():
    league, problems = load_league()
    assert league is not None and not [p for p in problems if p.level == "error"]
    assert league.sport == "stub" and league.sample_data is True


def test_fallback_standings_cover_every_key():
    assert set(FALLBACK_STANDINGS) == {"rank_by", "points", "period_points", "ties", "forfeit", "tiebreakers",
                                       "columns", "playoffs"}


def test_overrides_that_set_a_decide_setting_remove_its_placeholder_for_that_season(sports_root):
    lg = ok(sports_root)
    settings, _ = effective_settings(lg, {"standings": {"tiebreakers": ["wins"]}, "rules": {"overtime": "none"}})
    assert [p.setting for p in settings.placeholders] == ["standings.forfeit", "stats.minimums.ppg_min_games"]
    assert effective_settings(lg, None)[0].placeholders == lg.placeholders


def test_effective_settings_returns_copies(sports_root):
    lg = ok(sports_root)
    settings, _ = effective_settings(lg, None)
    settings.standings["points"]["win"] = 99
    settings.rules["periods"] = 99
    assert lg.standings["points"]["win"] == 2 and lg.rules["periods"] == 2


def test_a_malformed_colour_dark_does_not_run_the_gate_against_colour(sports_root):
    league, problems = make(sports_root, colour=GOLD, colour_dark="blue")
    assert league is None and set(errors(problems)) == {"colour_dark"}


def test_timezone_names_are_case_sensitive_like_on_the_linux_build(sports_root):
    _, problems = make(sports_root, timezone="america/toronto")
    assert "Did you mean 'America/Toronto'?" in errors(problems)["timezone"]
