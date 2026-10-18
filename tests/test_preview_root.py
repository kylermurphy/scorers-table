"""Tests for scripts/preview_root.py and `build.py --sport-preview` (docs/stage-5-basketball-spec.md, section 7).

The temporary root a sport's demo copy is built from: the same on two runs, a league.yml that loads with no
problem and carries nothing of the real league but its time zone and time format, and sample data equal to what the
golden test builds from. Then the build itself: `--sport-preview` marks the data as a sport preview, writes no
calendar files and refuses a root of another sport. The Jekyll side (base paths, banner, noindex) is in
test_jekyll.py."""
import json
import shutil
from pathlib import Path

import pytest
import yaml

from scripts import build, preview_root
from scripts.core.config import load_league
from scripts.core.sports import SPORTS_ROOT, load_sport
from tests.test_golden import sample_root

ROOT = Path(__file__).resolve().parent.parent


def tree(folder: Path) -> dict[str, str]:
    """{relative path: text} of the files a root holds, following the `sports` link no further."""
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(folder.rglob("*"))
            if p.is_file() and p.relative_to(folder).parts[0] != "sports"}


@pytest.fixture(scope="module")
def root(tmp_path_factory) -> Path:
    return preview_root.write_root("basketball", tmp_path_factory.mktemp("preview") / "root")


# ------------------------------------------------------------------ the temporary root

def test_the_root_is_the_same_on_two_runs(root, tmp_path):
    again = preview_root.write_root("basketball", tmp_path / "again")
    assert tree(root) == tree(again)
    assert preview_root.league_text("basketball") == preview_root.league_text("basketball")
    assert (root / "sports").resolve() == (ROOT / "sports").resolve()          # a link, not a copy


def test_its_league_yml_loads_with_no_problem(root):
    league, problems = load_league(root / "league.yml", sports_root=root / "sports", root=root)
    assert league is not None and not [p for p in problems if p.level == "error"]
    sport, _ = load_sport("basketball", SPORTS_ROOT, with_sample=True)
    assert league.name == sport.sample.LEAGUE_NAME
    assert (league.sport, league.layout) == ("basketball", sport.spec["default_layout"])
    assert (league.sample_data, league.preview, league.sport_previews, league.search_engines) == (True, False, (), False)
    assert league.landing_page is False                      # a demo copy never builds the landing page itself
    assert (league.colour, league.logo, league.contact, league.github, league.footer_line) == (None,) * 5
    assert league.rules == {k: o["default"] for k, o in sport.spec["options"].items()}      # the sport's own defaults
    assert [p.setting for p in league.placeholders] == [p.setting for p in load_league(ROOT / "league.yml")[0].placeholders]


def test_only_the_time_zone_and_time_format_come_from_the_real_league(tmp_path):
    repo = tmp_path / "repo"
    (repo / "sports").mkdir(parents=True)
    shutil.copytree(ROOT / "sports" / "basketball", repo / "sports" / "basketball", ignore=shutil.ignore_patterns("__pycache__"))
    (repo / "league.yml").write_text(
        'name: "The Real League"\nsport: basketball\ntimezone: America/Toronto\ntime_format: 24h\n'
        'colour: "#1D3A6E"\ncontact: me@example.com\nrules: {overtime: none}\nstandings: {ties: true}\n'
        'search_engines: true\nsport_previews: true\ntagline: Real\n', encoding="utf-8")
    made = yaml.safe_load(preview_root.league_text("basketball", repo))
    assert made == {"name": "Riverside Masters Basketball", "sport": "basketball", "layout": "basketball",
                    "timezone": "America/Toronto", "time_format": "24h", "sample_data": True, "preview": False,
                    "sport_previews": False, "landing_page": False, "search_engines": False}


def test_its_seasons_are_the_templates_and_its_sample_data_is_what_the_golden_test_builds_from(root, tmp_path):
    made = yaml.safe_load((root / "data" / "seasons.yml").read_text(encoding="utf-8"))
    assert made == yaml.safe_load((ROOT / "data" / "seasons.yml").read_text(encoding="utf-8"))
    golden = sample_root(tmp_path, "basketball")
    mine, theirs = tree(root), tree(golden)
    assert {k: v for k, v in mine.items() if k.startswith("data/sample-")} \
        == {k: v for k, v in theirs.items() if k.startswith("data/sample-")}
    assert any(k.startswith("data/sample-2026-27/games/") for k in mine)
    assert not [k for k in mine if k.startswith("data/2026-27/") and mine[k].strip() not in ("[]", "") and k.endswith(".yml")]


def test_the_current_season_is_empty(root):
    for name in ("teams.yml", "players.yml"):
        assert yaml.safe_load((root / "data" / "2026-27" / name).read_text(encoding="utf-8")) == []
    assert (root / "data" / "2026-27" / "schedule.csv").read_text(encoding="utf-8").count("\n") == 1
    assert list((root / "data" / "2026-27" / "games").iterdir()) == []


def test_a_sport_without_a_demo_or_a_folder_with_files_in_it_is_refused(tmp_path, capsys):
    with pytest.raises(ValueError, match="not a sport with a preview"):
        preview_root.write_root("stub", tmp_path / "a")
    with pytest.raises(ValueError, match="not a sport with a preview"):
        preview_root.write_root("nothing", tmp_path / "b")
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(ValueError, match="not empty"):
        preview_root.write_root("basketball", tmp_path / "full")
    assert preview_root.main(["stub", str(tmp_path / "c")]) == 1
    assert "not a sport with a preview" in capsys.readouterr().err
    assert not (tmp_path / "c").exists()


def test_list_prints_the_ids_league_yml_asks_for(capsys):
    assert preview_root.main(["--list"]) == 0
    assert capsys.readouterr().out == "basketball\ncurling\n"
    ids, problems = preview_root.preview_ids()
    assert ids == ["basketball", "curling"] and not problems


def test_list_stops_with_the_problem_when_league_yml_is_wrong(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "sports", repo / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    text = (ROOT / "league.yml").read_text(encoding="utf-8").replace("sport_previews: true", "sport_previews: [stub]")
    (repo / "league.yml").write_text(text, encoding="utf-8")
    ids, problems = preview_root.preview_ids(repo)
    assert ids == [] and [(p.at, p.level) for p in problems if p.level == "error"] == [("sport_previews.0", "error")]


# ------------------------------------------------------------------ build.py --sport-preview

def test_a_sport_preview_build_is_marked_lists_the_other_demos_and_writes_no_calendars(root, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    # --out holds the live site's league.yml: its sport_previews decide which demos the banner links to
    live = tmp_path / "live"
    shutil.copytree(ROOT / "sports", live / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("basketball", "stub"):
        shutil.copytree(live / "sports" / name, live / "sports" / (name + "2"))
    for name in ("basketball2", "stub2"):
        spec = live / "sports" / name / "sport.yml"
        spec.write_text(spec.read_text(encoding="utf-8").replace("demo: false", "demo: true"), encoding="utf-8")
    (live / "league.yml").write_text(
        (ROOT / "league.yml").read_text(encoding="utf-8").replace("sport_previews: true", "sport_previews: [stub2, basketball, basketball2]"),
        encoding="utf-8")
    assert build.main(["--root", str(root), "--out", str(live), "--sport-preview", "basketball"]) == 0
    capsys.readouterr()
    active = json.loads((live / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))
    assert (active["preview"], active["preview_kind"], active["sample_mode"], active["season"]) == (
        True, "sport", True, "sample-2026-27")
    assert active["preview_sport"] == "Basketball"
    assert active["sport_previews"] == [{"id": "stub2", "name": "Stub", "url": "/stub2/"},          # the others, not itself
                                        {"id": "basketball2", "name": "Basketball", "url": "/basketball2/"}]
    assert list((live / "calendar").iterdir()) == []
    assert json.loads((live / "_data" / "computed" / "calendars.json").read_text(encoding="utf-8")) == {"season": None, "files": []}
    league = json.loads((live / "_data" / "computed" / "league.json").read_text(encoding="utf-8"))
    assert league["name"] == "Riverside Masters Basketball" and league["search_engines"] is False
    assert (live / "_games").is_dir() and any((live / "_games").iterdir())


def test_a_sport_preview_without_a_live_league_yml_lists_no_other_sports(root, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert build.main(["--root", str(root), "--out", str(out), "--sport-preview", "basketball"]) == 0
    active = json.loads((out / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))
    assert active["sport_previews"] == [] and active["preview_kind"] == "sport"


def test_a_sport_preview_refuses_a_root_of_another_sport_and_a_site_path(root, tmp_path, capsys):
    assert build.main(["--root", str(root), "--out", str(tmp_path / "o1"), "--sport-preview", "hockey"]) == 2
    assert "is for the sport 'basketball'" in capsys.readouterr().err
    assert not (tmp_path / "o1").exists()
    other = tmp_path / "other"
    shutil.copytree(root, other, symlinks=True)
    text = (other / "league.yml").read_text(encoding="utf-8").replace("sport: basketball", "sport: stub")
    (other / "league.yml").write_text(text, encoding="utf-8")
    assert build.main(["--root", str(other), "--out", str(tmp_path / "o2"), "--sport-preview", "stats"]) == 2
    assert "is for the sport 'stub'" in capsys.readouterr().err


def test_the_league_preview_banner_links_to_the_sport_previews(tmp_path, capsys):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "sports", repo / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data", repo / "data")
    text = (ROOT / "league.yml").read_text(encoding="utf-8").replace("sample_data: true", "sample_data: false")
    (repo / "league.yml").write_text(text, encoding="utf-8")
    assert build.main(["--root", str(repo), "--out", str(tmp_path / "out"), "--sample"]) == 0
    capsys.readouterr()
    active = json.loads((tmp_path / "out" / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))
    assert (active["preview_kind"], active["sport_previews"]) == (
        "league", [{"id": "basketball", "name": "Basketball", "url": "/basketball/"},
                   {"id": "curling", "name": "Curling", "url": "/curling/"}])
