"""Tests for scripts/landing.py and the landing page's part of scripts/build.py (docs/landing-page-plan.md, sections
1 to 3 and 5): the landing.yml checks with their paths, landing.json equal to the demos it previews (the numbers come
from the same computation as `/<sport>/`), the Jekyll overlay, and "off means unchanged" (no landing.json and an
overlay of one line). The Jekyll side (the page itself, the links, the banners) is in test_jekyll.py.

The golden file is tests/golden/landing/landing.json. When a change to the page's data is meant, rewrite it:

    UPDATE_GOLDEN=1 python -m pytest tests/test_landing.py

and read the diff of tests/golden/ before committing it."""
import difflib
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from scripts import build, landing, preview_root
from scripts.core.config import load_league
from scripts.core.problems import format_human
from tests.conftest import set_landing_page

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "landing" / "landing.json"
TODAY = "2026-11-20"
NOTE = ("The front page is the scorers-table landing page. For your league's own site, set landing_page: false in "
        "league.yml.")


# ------------------------------------------------------------------ a throwaway copy of the repository's inputs

def make_root(base: Path, name: str = "site", *, landing_page: bool | None = None, words: bool = True) -> Path:
    """A repository root with the shipped league.yml (plus `landing_page: ...` when given), data, sports, landing.yml
    and _config.yml: what `build.py --root` needs to build the front page."""
    root = base / name
    root.mkdir()
    text = set_landing_page((ROOT / "league.yml").read_text(encoding="utf-8"), landing_page)
    (root / "league.yml").write_text(text, encoding="utf-8")
    shutil.copytree(ROOT / "data", root / "data")
    os.symlink((ROOT / "sports").resolve(), root / "sports", target_is_directory=True)
    shutil.copy(ROOT / "_config.yml", root / "_config.yml")
    if words:
        shutil.copy(ROOT / "landing.yml", root / "landing.yml")
    return root


def run_build(root: Path, *flags: str) -> int:
    return build.main(["--root", str(root), "--out", str(root), "--today", TODAY, *flags])


@pytest.fixture(scope="module")
def on(tmp_path_factory):
    """The switch on: the root after a plain build (the golden file and the demos are compared against it)."""
    root = make_root(tmp_path_factory.mktemp("landing_on"), landing_page=True)
    assert run_build(root) == 0
    return root


@pytest.fixture(scope="module")
def page(on) -> dict:
    return json.loads((on / "_data" / "computed" / "landing.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demos(tmp_path_factory) -> dict[str, Path]:
    """Each demo built the way scripts/build_preview.sh builds `/<sport>/`: its temporary root, then build.py
    --sport-preview, written to its own output folder. {sport id: the folder under _data/computed/<season>/}."""
    out = {}
    for sport_id in ("basketball", "curling"):
        base = tmp_path_factory.mktemp(f"demo_{sport_id}")
        demo_root = preview_root.write_root(sport_id, base / "root")
        assert build.main(["--root", str(demo_root), "--out", str(base / "out"), "--sport-preview", sport_id]) == 0
        out[sport_id] = base / "out" / "_data" / "computed"
    return out


def load(folder: Path, *parts: str):
    return json.loads(folder.joinpath(*parts).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ landing.json is the demos' numbers

def test_the_page_has_one_card_per_demo_sport_in_the_order_of_sport_previews(page):
    assert list(page) == ["shell", "active", "intro", "links", "features_title", "features", "copy_note", "sports",
                          "coming_soon"]
    assert [s["id"] for s in page["sports"]] == ["basketball", "curling"]
    assert [s["url"] for s in page["sports"]] == ["/basketball/", "/curling/"]
    assert [s["demo_label"] for s in page["sports"]] == ["Open the Basketball demo", "Open the Curling demo"]
    assert [c["id"] for c in page["coming_soon"]] == ["hockey", "slopitch"]


def test_a_sport_entry_has_the_fixed_shape(page):
    for s in page["sports"]:
        assert list(s) == ["id", "name", "blurb", "url", "demo_label", "league_name", "layout", "window"]
        assert list(s["window"]) == ["league", "standings", "teams", "latest"]
        assert list(s["window"]["league"]) == ["name", "layout", "labels", "words", "display", "results_legend"]
        assert list(s["window"]["standings"]) == ["columns", "rows", "note"]
        assert set(s["window"]["latest"]) == {"label", "date_long", "game"}


def test_the_shell_is_what_the_header_nav_and_footer_read(page):
    shell = page["shell"]
    assert (shell["name"], shell["short_name"], shell["code"], shell["layout"]) == ("scorers-table",) * 2 + ("ST", "basketball")
    assert shell["extra_layouts"] == ["curling"]          # the page is Basketball; Curling's window needs its own look
    assert [n["key"] for n in shell["nav"]] == ["sports", "get-started"]
    assert [f["label"] for f in shell["footer_links"]] == ["Basketball demo", "Curling demo", "Setup guide (short version)",
                                                            "The code on GitHub"]
    assert page["active"] == {"sample_mode": False, "preview": False}
    assert shell["search_engines"] is False and shell["footer_line"] == ""
    assert all(u["url"].startswith(("https://", "/")) for u in [*shell["nav"], *shell["footer_links"], *page["links"]])


@pytest.mark.parametrize("sport_id", ["basketball", "curling"])
def test_the_standings_rows_are_the_top_three_of_the_demos_own_standings(page, demos, sport_id):
    entry = next(s for s in page["sports"] if s["id"] == sport_id)
    computed = demos[sport_id]
    season = load(computed, "active.json")["season"]
    standings = load(computed, season, "standings.json")
    window = entry["window"]["standings"]
    key = next(i for i, c in enumerate(standings["columns"]) if c["key_col"])
    assert window["columns"] == standings["columns"][:key + 1]               # up to and including the key column
    assert window["columns"][-1]["key_col"] is True and window["columns"][-1]["key"] == "pts"
    assert [r["team"] for r in window["rows"]] == [r["team"] for r in standings["rows"][:3]]
    for mine, theirs in zip(window["rows"], standings["rows"]):
        assert mine["rank"] == theirs["rank"]
        assert mine["display"] == {c["key"]: theirs["display"][c["key"]] for c in window["columns"]}
    total = len(standings["rows"])
    assert window["note"] == f"Top 3 of {total} · through {standings['through_display']}"
    teams = load(computed, season, "teams.json")
    for team_id, team in entry["window"]["teams"].items():
        assert {k: team[k] for k in ("name", "code", "slot", "colour")} == {k: teams[team_id][k] for k in ("name", "code", "slot", "colour")}
        assert team["url"] == f"/{sport_id}{teams[team_id]['url']}"
    assert list(entry["window"]["teams"]) == [r["team"] for r in window["rows"]]


@pytest.mark.parametrize("sport_id", ["basketball", "curling"])
def test_the_latest_result_is_the_first_game_of_the_demos_latest_day(page, demos, sport_id):
    entry = next(s for s in page["sports"] if s["id"] == sport_id)
    computed = demos[sport_id]
    season = load(computed, "active.json")["season"]
    results = load(computed, season, "results.json")
    games = load(computed, season, "games.json")
    day = next(d for d in load(computed, season, "schedule.json")["days"] if d["n"] == results[0]["day"])
    latest = entry["window"]["latest"]
    assert (latest["label"], latest["date_long"]) == (day["label"], day["date_long"])
    theirs = games[results[0]["games"][0]]
    mine = latest["game"]
    assert mine["url"] == f"/{sport_id}{theirs['url']}"
    for key in ("id", "home", "away", "tie", "status", "card", "line_score", "time_display"):
        assert mine[key] == theirs[key], key
    assert "blocks" not in mine and "tiles" not in mine           # the result card reads neither; they are the box score
    assert set(mine) <= set(theirs)


@pytest.mark.parametrize("sport_id", ["basketball", "curling"])
def test_the_window_league_is_the_demos_league_json(page, demos, sport_id):
    entry = next(s for s in page["sports"] if s["id"] == sport_id)
    league = load(demos[sport_id], "league.json")
    assert entry["window"]["league"] == {k: league[k] for k in ("name", "layout", "labels", "words", "display", "results_legend")}
    assert (entry["name"], entry["league_name"], entry["layout"]) == (league["sport_name"], league["name"], league["layout"])


def test_every_url_inside_a_window_is_in_its_demo(page):
    def urls(value, found):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == "url":
                    found.append(v)
                else:
                    urls(v, found)
        elif isinstance(value, list):
            for v in value:
                urls(v, found)
        return found
    for s in page["sports"]:
        found = urls(s["window"], [])
        assert found and all(u.startswith(s["url"]) and not u.startswith(s["url"] + s["url"][1:]) for u in found), found


def test_the_blurbs_are_the_sports_own(page):
    for s in page["sports"]:
        spec = yaml.safe_load((ROOT / "sports" / s["id"] / "sport.yml").read_text(encoding="utf-8"))
        assert s["blurb"] == spec["blurb"] and s["name"] == spec["name"]


def test_the_cards_say_the_demo_is_made_up_by_naming_its_league(page):
    assert [s["league_name"] for s in page["sports"]] == ["Riverside Masters Basketball", "Pine Lake Curling Club"]


def test_landing_json_matches_the_golden_file(page, on):
    text = (on / "_data" / "computed" / "landing.json").read_text(encoding="utf-8")
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8", newline="")
        pytest.skip("golden file rewritten (tests/golden/landing/landing.json)")
    expected = GOLDEN.read_text(encoding="utf-8")
    if text != expected:
        diff = "\n".join(list(difflib.unified_diff(expected.splitlines(), text.splitlines(), "golden/landing.json",
                                                   "build/landing.json", lineterm="", n=2))[:60])
        pytest.fail(f"landing.json differs from tests/golden/landing (UPDATE_GOLDEN=1 rewrites it if the change is "
                    f"meant):\n{diff}")


def test_the_same_inputs_give_the_same_bytes(tmp_path, on):
    again = make_root(tmp_path, landing_page=True)
    assert run_build(again) == 0
    assert (again / "_data" / "computed" / "landing.json").read_bytes() == (on / "_data" / "computed" / "landing.json").read_bytes()


# ------------------------------------------------------------------ the switch on: the build around it

def test_the_leagues_own_files_are_still_written_beside_landing_json(on):
    computed = on / "_data" / "computed"
    for name in ("league.json", "active.json", "seasons.json", "landing.json"):
        assert (computed / name).is_file(), name
    assert (computed / "sample-2026-27" / "standings.json").is_file()
    assert (on / "_teams").is_dir()


def test_the_overlay_leaves_the_leagues_pages_out_of_the_root(on):
    overlay = yaml.safe_load((on / "_config.landing.yml").read_text(encoding="utf-8"))
    base = yaml.safe_load((on / "_config.yml").read_text(encoding="utf-8"))["exclude"]
    assert overlay["landing_page"] is True and overlay["include"] == []
    assert "landing/" in base and "landing.yml" in base                  # _config.yml leaves the page out of every other build
    assert overlay["exclude"] == [*(e for e in base if e != "landing/"), *landing.LEAGUE_PAGES]   # the overlay puts it in
    assert {name: overlay["collections"][name]["output"] for name in ("games", "players", "teams", "archive")} == \
        {"games": False, "players": False, "teams": False, "archive": False}
    assert set(overlay) == {"landing_page", "exclude", "include", "collections"}


def test_the_overlay_repeats_the_exclude_list_it_is_given_without_landing(tmp_path):
    config = tmp_path / "_config.yml"
    config.write_text("exclude:\n  - league.yml\n  - landing/\n  - landing.yml\n", encoding="utf-8")
    overlay = yaml.safe_load(landing.overlay_text(True, config))
    assert overlay["exclude"] == ["league.yml", "landing.yml", *landing.LEAGUE_PAGES]       # the page itself stays in
    assert landing.overlay_text(False, config) == "landing_page: false\n"


def test_the_overlay_names_every_page_the_site_has_at_its_root():
    """A page added to the root later (the entry page, say) must be added to LEAGUE_PAGES, or it would show at the root
    under the landing page. A page is any file Jekyll would render: one that starts with front matter, whatever its
    name or extension and however deep in its folder (enter/sheet.html, help/faq/index.md, feed.xml...)."""
    excluded = {e.rstrip("/") for e in landing.exclude_list(ROOT / "_config.yml")}
    known = {p.rstrip("/") for p in landing.LEAGUE_PAGES} | {"404.html", "landing", "assets"}
    skipped = {"vendor", "node_modules", "_site"}               # Jekyll's own defaults (the gems of a local bundle)

    def rendered(path: Path) -> bool:
        with path.open("rb") as f:
            return f.read(5).startswith((b"---\n", b"---\r\n"))

    found = set()
    for top in ROOT.iterdir():
        name = top.name
        if name.startswith((".", "_")) or name in excluded or name in skipped:
            continue
        files = [top] if top.is_file() else [p for p in top.rglob("*") if p.is_file()
                                              and not any(part.startswith((".", "_")) for part in p.relative_to(top).parts)]
        if any(rendered(p) for p in files):
            found.add(name)
    assert found <= known, f"root pages the landing overlay does not know about: {sorted(found - known)}"


def test_a_plain_build_prints_the_note_and_the_command_to_see_the_page(tmp_path, capsys):
    root = make_root(tmp_path, landing_page=True)
    assert run_build(root) == 0
    out = capsys.readouterr().out
    assert NOTE in out and "bundle exec jekyll build --config _config.yml,_config.landing.yml" in out
    # the order that keeps the demos: Jekyll first, then build_preview.sh, then a plain file server (not jekyll serve,
    # which rebuilds _site/ when build_preview.sh swaps the data, and so deletes the demos)
    hint = out[out.index("To see it"):]
    assert hint.index("jekyll build") < hint.index("scripts/build_preview.sh") < hint.index("http.server")


def test_a_demo_or_preview_copy_writes_neither_landing_json_nor_the_overlay(tmp_path):
    root = make_root(tmp_path, landing_page=True)
    out = tmp_path / "copy"
    assert build.main(["--root", str(root), "--sample", "--today", TODAY, "--out", str(out)]) == 0
    assert not (out / "_config.landing.yml").exists() and not (out / "_data" / "computed" / "landing.json").exists()
    demo = preview_root.write_root("curling", tmp_path / "curling-root")
    assert build.main(["--root", str(demo), "--out", str(tmp_path / "curling-out"), "--sport-preview", "curling"]) == 0
    assert not (tmp_path / "curling-out" / "_config.landing.yml").exists()


def test_check_reads_landing_yml_but_builds_no_demo_and_writes_nothing(tmp_path, capsys):
    root = make_root(tmp_path, landing_page=True)
    assert build.main(["--root", str(root), "--out", str(root), "--check"]) == 0
    assert not (root / "_data").exists() and not (root / "_config.landing.yml").exists()
    (root / "landing.yml").write_text("name: x\n", encoding="utf-8")
    assert build.main(["--root", str(root), "--out", str(root), "--check"]) == 1
    assert "landing.yml: code: is required" in capsys.readouterr().err


# ------------------------------------------------------------------ the switch off: nothing changes

@pytest.mark.parametrize("line", [None, False])
def test_with_the_switch_off_or_absent_there_is_no_landing_json_and_the_overlay_is_one_line(tmp_path, line, capsys):
    root = make_root(tmp_path, landing_page=line, words=False)          # landing.yml is not even needed
    assert run_build(root) == 0
    assert (root / "_config.landing.yml").read_text(encoding="utf-8") == "landing_page: false\n"
    assert not (root / "_data" / "computed" / "landing.json").exists()
    assert "landing page" not in capsys.readouterr().out


def test_with_the_switch_off_the_data_files_are_the_same_as_without_the_line(tmp_path):
    absent = make_root(tmp_path, "absent")
    off = make_root(tmp_path, "off", landing_page=False)
    assert run_build(absent) == 0 and run_build(off) == 0

    def tree(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for folder in ("_data", "_games", "_teams", "_players", "_archive")
                for p in sorted((root / folder).rglob("*")) if p.is_file()}
    assert tree(absent) == tree(off)
    assert (absent / "_config.landing.yml").read_bytes() == (off / "_config.landing.yml").read_bytes()


def test_switching_off_again_removes_the_stale_landing_json(tmp_path):
    root = make_root(tmp_path, landing_page=True)
    assert run_build(root) == 0 and (root / "_data" / "computed" / "landing.json").is_file()
    text = (root / "league.yml").read_text(encoding="utf-8").replace("landing_page: true", "landing_page: false")
    (root / "league.yml").write_text(text, encoding="utf-8")
    assert run_build(root) == 0
    assert not (root / "_data" / "computed" / "landing.json").exists()
    assert (root / "_config.landing.yml").read_text(encoding="utf-8") == "landing_page: false\n"


# ------------------------------------------------------------------ the checks, each with its path

def problems_of(tmp_path, landing_yml: str | None, *, shown=("basketball", "curling"), sports_root=None):
    """(words, problems) of read_words for a league showing `shown`, with this landing.yml (None: no file)."""
    root = tmp_path / "site"
    root.mkdir(exist_ok=True)
    if landing_yml is not None:
        (root / "landing.yml").write_text(landing_yml, encoding="utf-8")
    league, _ = load_league(ROOT / "league.yml")
    return landing.read_words(replace(league, landing_page=True, sport_previews=tuple(shown)), root,
                              sports_root=sports_root or ROOT / "sports")


def shipped_words() -> dict:
    return yaml.safe_load((ROOT / "landing.yml").read_text(encoding="utf-8"))


def with_changes(**changes) -> str:
    return yaml.safe_dump({**shipped_words(), **changes}, sort_keys=False, allow_unicode=True)


def errors_of(problems) -> dict[str, str]:
    return {p.at: p.message for p in problems if p.level == "error"}


def test_the_shipped_landing_yml_is_valid():
    words, problems = landing.read_words(replace(load_league(ROOT / "league.yml")[0], landing_page=True), ROOT)
    assert words is not None and problems == []
    assert 0 < len(words["intro"]) and "\n" not in words["intro"]
    assert all(len(c["blurb"]) <= 100 for c in words["coming_soon"])


def test_a_missing_landing_yml_says_what_to_do(tmp_path):
    words, problems = problems_of(tmp_path, None)
    assert words is None
    [p] = problems
    assert (p.file, p.at) == ("landing.yml", "")
    assert format_human(problems) == ("landing.yml: landing_page: true in league.yml needs this file (the words of the "
                                      "front page). Put it back from the template, or set landing_page: false.")


def test_an_unknown_key_and_a_missing_key_are_named(tmp_path):
    shipped = shipped_words()
    del shipped["tagline"]
    _, problems = problems_of(tmp_path, yaml.safe_dump({**shipped, "taglin": "x"}))
    found = errors_of(problems)
    assert set(found) == {"tagline", "taglin"}
    assert found["tagline"] == "is required. Add a 'tagline:' line." and "Did you mean 'tagline'?" in found["taglin"]


def test_a_link_must_be_https_or_a_path_of_the_site(tmp_path):
    links = [{"label": "Setup", "url": "githb.com/x", "note": ""}, {"label": "Demo", "url": "/basketball/"},
             {"label": "Plain", "url": "http://example.com"}, {"label": "Code", "url": "https://github.com/x/y"}]
    words, problems = problems_of(tmp_path, with_changes(links=links))
    found = errors_of(problems)
    assert words is None and set(found) == {"links.0.url", "links.2.url"}
    assert found["links.0.url"] == "'githb.com/x' must start with https:// or be a path of this site, like /basketball/."


def test_nav_items_need_a_label_a_url_and_a_key(tmp_path):
    _, problems = problems_of(tmp_path, with_changes(nav=[{"label": "Sports", "url": "/#sports"}, "Get started"]))
    assert set(errors_of(problems)) == {"nav.0.key", "nav.1"}


def test_the_demo_label_needs_the_sports_name(tmp_path):
    _, problems = problems_of(tmp_path, with_changes(demo_label="Open the demo"))
    assert "{name}" in errors_of(problems)["demo_label"]


def test_a_coming_soon_sport_that_has_a_demo_is_dropped_with_a_warning(tmp_path):
    soon = [{"id": "hockey", "name": "Hockey", "blurb": "Periods."}, {"id": "curling", "name": "Curling", "blurb": "Ends."}]
    words, problems = problems_of(tmp_path, with_changes(coming_soon=soon))
    assert words is not None and [c["id"] for c in words["coming_soon"]] == ["hockey"]
    [warning] = problems
    assert (warning.level, warning.at, warning.file) == ("warning", "coming_soon.1", "landing.yml")
    assert warning.message == "'curling' has a demo now, so it gets a real card. Take it off coming_soon."


def test_coming_soon_entries_are_checked(tmp_path):
    soon = [{"id": "Hockey", "name": "Hockey", "blurb": "x"}, {"id": "golf", "name": "Golf", "blurb": "x" * 101},
            {"id": "golf", "name": "Golf", "blurb": "ok"}, {"id": "darts", "name": "Darts"}]
    words, problems = problems_of(tmp_path, with_changes(coming_soon=soon))
    found = errors_of(problems)
    assert words is None
    assert set(found) == {"coming_soon.0.id", "coming_soon.1.blurb", "coming_soon.3.blurb"}
    assert "Did you mean 'hockey'?" in found["coming_soon.0.id"]
    assert found["coming_soon.1.blurb"] == "is 101 characters; keep it to at most 100."
    assert found["coming_soon.3.blurb"] == "is required. Add a 'blurb:' line."


def test_coming_soon_ids_are_not_listed_twice(tmp_path):
    soon = [{"id": "golf", "name": "Golf", "blurb": "a"}, {"id": "golf", "name": "Golf", "blurb": "b"}]
    _, problems = problems_of(tmp_path, with_changes(coming_soon=soon))
    assert errors_of(problems) == {"coming_soon.1.id": "'golf' is listed twice."}


def test_a_sport_without_a_blurb_is_named_in_its_own_sport_yml(tmp_path):
    sports = tmp_path / "sports"
    shutil.copytree(ROOT / "sports" / "basketball", sports / "basketball", ignore=shutil.ignore_patterns("__pycache__"))
    spec = sports / "basketball" / "sport.yml"
    spec.write_text(spec.read_text(encoding="utf-8").replace("blurb: Quarters, a running score, free throws and fouls.\n", ""),
                    encoding="utf-8")
    words, problems = problems_of(tmp_path, with_changes(), shown=("basketball",), sports_root=sports)
    [p] = [p for p in problems if p.level == "error"]
    assert words is None
    assert (p.file, p.at) == ("sports/basketball/sport.yml", "blurb")
    assert p.message == "a sport on the landing page needs a one-line blurb (at most 100 characters)."


def test_landing_yml_is_not_read_for_a_sport_the_page_does_not_show(tmp_path):
    words, problems = problems_of(tmp_path, with_changes(), shown=("curling",))
    assert words is not None and problems == []


def test_a_broken_landing_yml_is_one_error_with_the_line(tmp_path):
    words, problems = problems_of(tmp_path, "name: [unclosed\n")
    assert words is None and problems[0].file == "landing.yml" and "not valid YAML" in problems[0].message


# ------------------------------------------------------------------ the switch and build.py's messages

def test_landing_page_on_without_demos_stops_the_build_with_a_message_a_volunteer_can_act_on(tmp_path, capsys):
    root = make_root(tmp_path, landing_page=True)
    text = (root / "league.yml").read_text(encoding="utf-8").replace("sport_previews: true", "sport_previews: false")
    (root / "league.yml").write_text(text, encoding="utf-8")
    assert run_build(root) == 1
    err = capsys.readouterr().err
    assert "league.yml: landing_page: the landing page shows the sport demos and links to them" in err
    assert "Set sport_previews: true, or set landing_page: false" in err
    assert not (root / "_data").exists() and not (root / "_config.landing.yml").exists()


def test_a_sport_list_in_league_yml_picks_and_orders_the_cards(tmp_path):
    root = make_root(tmp_path, landing_page=True)
    text = (root / "league.yml").read_text(encoding="utf-8").replace("sport_previews: true", "sport_previews: [curling]")
    (root / "league.yml").write_text(text, encoding="utf-8")
    assert run_build(root) == 0
    page = json.loads((root / "_data" / "computed" / "landing.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in page["sports"]] == ["curling"] and page["shell"]["extra_layouts"] == ["curling"]
    assert [f["label"] for f in page["shell"]["footer_links"]][0] == "Curling demo"
