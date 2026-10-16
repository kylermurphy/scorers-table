"""Smoke test of the whole site: build the stub sample into a throwaway folder and read the pages back
(docs/stage-4-spec.md sections 5 and 7).

Each site is built in a temporary copy of the repository's source (`_config.yml`, `_layouts/`, `_includes/`,
`assets/`, the pages, `sports/`, `data/` and a `league.yml` changed for the case): `scripts/build.py --today
2026-11-20` writes the computed data and the stub pages there, then `bundle exec jekyll build` makes the HTML.
Nothing is written into the repository itself. The golden test pins the data; this one pins the pages.

What it checks: every nav page and one page of each stub kind exist; `data-layout` is the league's (all six
layouts build); the stylesheets are linked in the documented order (only the league's layout file); `noindex`
on and off; the league colour attribute and inline style on and off; the theme button is rendered hidden and the
page has no `aria-pressed`; no request leaves the site (every src and stylesheet is local, the only off-site
link is the scorers-table credit); no `Liquid error` anywhere; every page has one h1, the skip link first in
the body, a `<main id="main">` and a `lang`; the preview copy's banner link; every internal path goes through
`relative_url` (a build under a base path has none that miss it); an empty current season renders; the calendar
links exist when the current season has games; and html-proofer finds no broken link, image or script when it
is installed (the `test` group of the Gemfile).

Marked `jekyll`: skipped without Ruby, Bundler and the gems; CI always runs it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from scripts import build
from tests.parity.site import jekyll_command, skip_unless_ci

pytestmark = pytest.mark.jekyll

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ["_config.yml", "_layouts", "_includes", "assets", "index.html", "schedule", "stats", "teams", "archive",
          "rules", "404.html", "sports", "data"]
LAYOUTS = ["basketball", "curling", "hockey", "slopitch", "classic", "scoreboard"]
CSS_ORDER = ["fonts", "tokens", "layouts/{layout}", "base", "parts-shell", "parts-scores", "parts-data", "fallbacks"]
CREDIT = "https://github.com/kylermurphy/scorers-table"


@pytest.fixture(autouse=True)
def not_github(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


@pytest.fixture(scope="session")
def jekyll():
    command = jekyll_command()
    if command is None:
        skip_unless_ci("this test needs Ruby, Bundler and the gems: run `bundle install` (the Gemfile is in the "
                       "repository root); CI always runs it")
    return command


# ------------------------------------------------------------------ building a site

class Site:
    def __init__(self, root: Path, out: Path, stderr: str):
        self.root, self.out, self.stderr = root, out, stderr

    def html(self, path: str) -> str:
        """The built page for a site path ("/", "/schedule/", "/404.html")."""
        rel = path.lstrip("/")
        file = self.out / rel if rel.endswith(".html") else self.out / rel / "index.html"
        return file.read_text(encoding="utf-8")

    def pages(self) -> list[Path]:
        return sorted(self.out.rglob("*.html"))

    def computed(self, *parts: str):
        return json.loads(Path(self.root, "_data", "computed", *parts).read_text(encoding="utf-8"))


def make_site(tmp: Path, jekyll: list[str], *, league: str = "", real: bool = False, empty: bool = False,
              sample_flag: bool = False, baseurl: str = "", url: str = "", logo: bool = False,
              site_url: str = "", edit=None) -> Site:
    """Copy the source, change league.yml, run build.py and Jekyll.
    league: lines appended to league.yml; real: the sample season stands in as the real one (sample_data false);
    empty: sample_data false with the real season left empty; sample_flag: build.py --sample (the /preview/ copy);
    edit: a function called with the copied source folder before build.py runs (to change a sport, say)."""
    root = tmp / "src"
    root.mkdir()
    for name in SOURCE:
        src = ROOT / name
        shutil.copytree(src, root / name) if src.is_dir() else shutil.copy(src, root / name)
    text = (ROOT / "league.yml").read_text(encoding="utf-8")
    if real or empty:
        text = text.replace("sample_data: true", "sample_data: false")
    if real:
        shutil.rmtree(root / "data" / "2026-27")
        shutil.copytree(ROOT / "data" / "sample-2026-27", root / "data" / "2026-27")
    if logo:
        (root / "assets" / "league").mkdir(exist_ok=True)
        (root / "assets" / "league" / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><circle cx="48" cy="48" r="44"/></svg>')
        league += "\nlogo: assets/league/logo.svg"
    (root / "league.yml").write_text(text + "\n" + league + "\n", encoding="utf-8")
    if edit:
        edit(root)

    args = ["--root", str(root), "--out", str(root), "--today", "2026-11-20"]
    if sample_flag:
        args.append("--sample")
    if site_url:
        args += ["--site-url", site_url]
    assert build.main(args) == 0

    configs = [root / "_config.yml"]
    if url:
        (root / "_config.url.yml").write_text(f'url: "{url}"\n')
        configs.append(root / "_config.url.yml")
    out = tmp / "site"
    proc = subprocess.run([*jekyll, "build", "--source", str(root), "--destination", str(out), "--config",
                           ",".join(str(c) for c in configs), "--baseurl", baseurl, "--quiet"],
                          cwd=ROOT, capture_output=True, text=True, env=dict(os.environ))
    assert proc.returncode == 0, "jekyll build failed:\n" + proc.stdout + proc.stderr
    return Site(root, out, proc.stdout + proc.stderr)


@pytest.fixture(scope="module")
def site(tmp_path_factory, jekyll) -> Site:
    """The stub sample as the site shows it by default (sample_data: true, the Classic look)."""
    return make_site(tmp_path_factory.mktemp("sample"), jekyll)


# ------------------------------------------------------------------ reading a page

class Page(HTMLParser):
    """The few things the tests ask of a page."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.html = html
        self.h1 = 0
        self.mains: list[dict] = []
        self.html_attrs: dict = {}
        self.links: list[dict] = []      # <link ...> in order
        self.scripts: list[dict] = []
        self.meta: list[dict] = []
        self.hrefs: list[str] = []       # <a href>
        self.srcs: list[str] = []        # src of img/script/iframe/source
        self.body_children: list[tuple[str, dict]] = []   # the first tags after <body>
        self.buttons: list[dict] = []
        self.has_aria_pressed = False
        self._in_body = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_attrs = a
        elif tag == "h1":
            self.h1 += 1
        elif tag == "main":
            self.mains.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "script":
            self.scripts.append(a)
        elif tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        elif tag == "button":
            self.buttons.append(a)
        if tag in ("img", "script", "iframe", "source", "video", "audio") and a.get("src"):
            self.srcs.append(a["src"])
        if "aria-pressed" in a:
            self.has_aria_pressed = True
        if self._in_body and len(self.body_children) < 3:
            self.body_children.append((tag, a))
        if tag == "body":
            self._in_body = True

    def stylesheets(self) -> list[str]:
        return [l["href"] for l in self.links if l.get("rel") == "stylesheet"]

    def robots(self) -> list[str]:
        return [m["content"] for m in self.meta if m.get("name") == "robots"]


def is_local(url: str) -> bool:
    """A path on this site (or an in-page anchor, or a data: icon): not another host."""
    return not re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) or url.startswith("data:")


# ------------------------------------------------------------------ pages that must exist

def test_every_nav_page_and_one_of_each_stub_page_exist(site):
    league = site.computed("league.json")
    for item in league["nav"]:
        assert (site.out / item["url"].lstrip("/") / "index.html").is_file(), item["url"]
    assert (site.out / "rules" / "index.html").is_file()
    assert (site.out / "404.html").is_file()
    active = site.computed("active.json")
    games = site.computed(active["season"], "games.json")
    assert games and all((site.out / "games" / gid / "index.html").is_file() for gid in games)
    for kind, file in (("teams", "teams.json"), ("players", "players.json")):
        ids = site.computed(active["season"], file)
        assert ids and all((site.out / kind / i / "index.html").is_file() for i in ids)
    for season in active["archive"]:
        assert (site.out / "archive" / season / "index.html").is_file()
        # a past season's games have pages too
        past = site.computed(season, "games.json")
        assert all((site.out / "games" / gid / "index.html").is_file() for gid in past)


def test_stub_pages_show_their_own_content(site):
    active = site.computed("active.json")
    teams = site.computed(active["season"], "teams.json")
    assert "<h1" in site.html("/teams/otters/") and teams["otters"]["name"] in site.html("/teams/otters/")
    assert "Box score" in site.html("/games/2026-11-19-1/") or "Ravens" in site.html("/games/2026-11-19-1/")
    assert "Game log" in site.html("/players/amy-p/")
    assert "Standings" in site.html("/archive/sample-2025-26/")


def test_past_season_pages_never_link_to_missing_team_or_player_pages(site):
    for path in ("/archive/sample-2025-26/", "/games/2025-10-16-1/", "/games/2025-12-11-1/"):
        page = Page(site.html(path))
        assert 'href=""' not in page.html, path
        assert not any(re.match(r"^/(players|teams)/[^/]+/", h) for h in page.hrefs), path


# ------------------------------------------------------------------ every page

def test_every_page_has_one_h1_a_skip_link_first_a_main_and_a_lang(site):
    for file in site.pages():
        page = Page(file.read_text(encoding="utf-8"))
        name = file.relative_to(site.out).as_posix()
        assert page.h1 == 1, f"{name}: {page.h1} h1"
        assert page.html_attrs.get("lang") == "en", name
        assert [m.get("id") for m in page.mains] == ["main"], name
        tag, attrs = page.body_children[0]
        assert tag == "a" and attrs.get("class") == "st-skip-link" and attrs.get("href") == "#main", name


def test_no_liquid_error_anywhere(site):
    assert "Liquid" not in site.stderr
    for file in site.pages():
        assert "Liquid error" not in file.read_text(encoding="utf-8"), file


def test_the_theme_button_is_hidden_and_has_no_aria_pressed(site):
    for path in ("/", "/schedule/", "/games/2026-11-19-1/", "/archive/"):
        page = Page(site.html(path))
        toggles = [b for b in page.buttons if "st-theme-toggle" in b.get("class", "")]
        assert len(toggles) == 1 and "hidden" in toggles[0], path
        assert toggles[0]["aria-label"] == "Switch to dark theme"
        assert not page.has_aria_pressed
    html = site.html("/")
    # the inline script applies a saved theme before the first paint, and is wrapped in try/catch
    assert 'localStorage.getItem("st-theme")' in html and html.index("st-theme") < html.index("fonts.css")
    assert "try{" in html and "catch(e)" in html
    js = (site.out / "assets" / "js" / "site.js").read_text(encoding="utf-8")
    assert '"st-theme"' in js and "Switch to light theme" in js and "Switch to dark theme" in js
    assert "aria-pressed" not in js


def test_nothing_is_loaded_from_another_site(site):
    for file in site.pages():
        page = Page(file.read_text(encoding="utf-8"))
        name = file.relative_to(site.out).as_posix()
        for link in page.links:
            assert is_local(link.get("href", "")), (name, link)
        for src in page.srcs:
            assert is_local(src), (name, src)
        # the only off-site link on a page is the scorers-table credit
        assert [h for h in page.hrefs if not is_local(h)] == [CREDIT], name
        assert "fonts.googleapis" not in page.html and "<iframe" not in page.html


def test_stylesheets_load_in_the_documented_order(site):
    for path in ("/", "/games/2026-11-19-1/", "/404.html"):
        sheets = Page(site.html(path)).stylesheets()
        assert sheets == [f"/assets/css/{name.format(layout='classic')}.css" for name in CSS_ORDER], path
    assert not any("scoreboard" in s for s in Page(site.html("/")).stylesheets())


def test_the_site_is_marked_noindex_unless_the_league_allows_search_engines(site, tmp_path_factory, jekyll):
    for file in site.pages():
        assert Page(file.read_text(encoding="utf-8")).robots() == ["noindex, nofollow"], file
    on = make_site(tmp_path_factory.mktemp("search"), jekyll, league="search_engines: true")
    for file in on.pages():
        assert Page(file.read_text(encoding="utf-8")).robots() == [], file


def test_the_league_colour_is_an_attribute_and_an_inline_style_only_when_set(site, tmp_path_factory, jekyll):
    for file in site.pages():
        attrs = Page(file.read_text(encoding="utf-8")).html_attrs
        assert "data-league-colour" not in attrs and "style" not in attrs, file
    coloured = make_site(tmp_path_factory.mktemp("colour"), jekyll, league='colour: "#1D3A6E"')
    for file in coloured.pages():
        attrs = Page(file.read_text(encoding="utf-8")).html_attrs
        assert "data-league-colour" in attrs and attrs["style"] == "--st-league-color:#1D3A6E", file
    both = make_site(tmp_path_factory.mktemp("colours"), jekyll,
                     league='colour: "#1D3A6E"\ncolour_dark: "#3D5FA8"')
    attrs = Page(both.html("/")).html_attrs
    assert attrs["style"] == "--st-league-color:#1D3A6E;--st-league-color-dark:#3D5FA8"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_builds_with_its_own_stylesheet(layout, tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp(layout), jekyll, league=f"layout: {layout}")
    assert "Liquid" not in built.stderr
    for path in ("/", "/schedule/", "/stats/", "/teams/", "/teams/lynx/", "/games/2026-11-19-1/",
                 "/players/amy-p/", "/archive/sample-2025-26/"):
        page = Page(built.html(path))
        assert page.html_attrs["data-layout"] == layout, path
        assert "Liquid error" not in page.html, path
        layouts = [s for s in page.stylesheets() if "/layouts/" in s]
        assert layouts == [f"/assets/css/layouts/{layout}.css"], path
        assert page.h1 == 1, path
    # the Scoreboard shows its ticker of the latest scores
    assert ('class="st-ticker"' in built.html("/")) == (layout == "scoreboard")


def test_a_league_logo_is_used_in_the_header_and_as_the_icon(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("logo"), jekyll, logo=True)
    html = built.html("/")
    assert 'src="/assets/league/logo.svg"' in html and 'rel="icon" href="/assets/league/logo.svg"' in html
    assert (built.out / "assets" / "league" / "logo.svg").is_file()
    assert 'href="data:,"' not in html


def test_the_icon_is_an_empty_data_url_without_a_logo(site):
    assert 'rel="icon" href="data:,"' in site.html("/")


# ------------------------------------------------------------------ the preview copy and a base path

def test_the_preview_banner_links_back_to_the_live_site(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("preview"), jekyll, empty=True, sample_flag=True,
                      baseurl="/club/preview")
    page = Page(built.html("/"))
    assert "Preview with sample data." in page.html
    assert 'class="st-banner__link" href="/club/"' in page.html
    assert 'href="/club/preview/schedule/"' in page.html      # its own pages stay inside the preview
    with_origin = make_site(tmp_path_factory.mktemp("preview_origin"), jekyll, empty=True, sample_flag=True,
                            baseurl="/club/preview", url="https://league.example")
    assert 'href="https://league.example/club/"' in with_origin.html("/")
    at_root = make_site(tmp_path_factory.mktemp("preview_root"), jekyll, empty=True, sample_flag=True,
                        baseurl="/preview")
    assert 'class="st-banner__link" href="/"' in at_root.html("/")


def test_the_live_site_has_no_banner_and_the_sample_site_says_so(site, tmp_path_factory, jekyll):
    assert "Sample data." in site.html("/") and "Preview with" not in site.html("/")
    live = make_site(tmp_path_factory.mktemp("live"), jekyll, real=True)
    assert "st-banner" not in live.html("/")


def test_every_internal_path_goes_through_relative_url(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("base"), jekyll, real=True, baseurl="/club", site_url="https://x.example/club")
    for file in built.pages():
        page = Page(file.read_text(encoding="utf-8"))
        name = file.relative_to(built.out).as_posix()
        local = [h for h in page.hrefs + page.srcs + [l.get("href", "") for l in page.links]
                 if is_local(h) and not h.startswith(("#", "data:"))]
        assert local, name
        assert all(h.startswith("/club/") or h == "/club" for h in local), (name, [h for h in local if not h.startswith("/club/")])


# ------------------------------------------------------------------ states of the season

def test_an_empty_current_season_shows_messages_instead_of_blank_sections(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("empty"), jekyll, empty=True)
    assert "Liquid" not in built.stderr
    home = built.html("/")
    for text in ("No games are scheduled yet", "No games have been played yet", "standings show up here",
                 "leaders show up here"):
        assert text in home, text
    assert "show up here" in built.html("/stats/") and "show up here" in built.html("/teams/")
    assert "No games are scheduled yet" in built.html("/schedule/")
    assert "There are no past seasons yet" in built.html("/archive/")
    for file in built.pages():
        page = Page(file.read_text(encoding="utf-8"))
        assert page.h1 == 1 and "Liquid error" not in page.html, file
        assert "<table" not in page.html or "<tbody></tbody>" not in page.html, file


def test_calendar_links_appear_when_the_current_season_has_games(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("calendar"), jekyll, real=True, site_url="https://x.example/club")
    assert (built.out / "calendar" / "league.ics").is_file() and (built.out / "calendar" / "otters.ics").is_file()
    schedule = built.html("/schedule/")
    assert 'href="/calendar/league.ics"' in schedule and "webcal://x.example/club/calendar/league.ics" in schedule
    assert 'href="/calendar/ravens.ics"' in schedule and "webcal://x.example/club/calendar/ravens.ics" not in schedule
    team = built.html("/teams/otters/")
    assert 'href="/calendar/otters.ics"' in team and "webcal://x.example/club/calendar/otters.ics" in team
    # no sample banner, and every game page links back to the schedule
    assert 'href="/schedule/"' in built.html("/games/2026-11-19-1/")


def test_a_sample_site_has_no_calendar_section(site):
    assert "calendar" not in site.html("/schedule/").lower().replace("calendar-", "")
    assert "Calendar" not in site.html("/teams/otters/")


def test_all_times_pm_is_said_where_game_rows_are_printed(site):
    assert "All times PM." in site.html("/schedule/")
    assert "All times PM." in site.html("/")
    assert "All times PM." in site.html("/teams/lynx/")


def test_the_tiebreak_note_follows_the_standings_on_home(site):
    html = site.html("/")
    note = site.computed("sample-2026-27", "standings.json")["tiebreak_note"]
    assert note.split(".")[0] in html


def test_the_rules_page_lists_the_placeholders(site):
    html = site.html("/rules/")
    for item in site.computed("league.json")["placeholders"]:
        assert item["setting"] in html
    assert "[League rules]" in html


# ------------------------------------------------------------------ links

def _proofer(jekyll):
    probe = subprocess.run(["bundle", "exec", "htmlproofer", "--version"], cwd=ROOT, capture_output=True, text=True)
    return probe.returncode == 0


def _check_links(folder: Path, *, swap: str = "") -> subprocess.CompletedProcess:
    args = ["bundle", "exec", "htmlproofer", str(folder), "--checks", "Links,Images,Scripts", "--disable-external",
            "--no-allow-missing-href", "--no-enforce-https"]
    if swap:
        args += ["--swap-urls", swap]
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, LC_ALL="C.UTF-8"))


def test_no_broken_internal_link_image_or_script(site, tmp_path_factory, jekyll):
    if not _proofer(jekyll):
        skip_unless_ci("html-proofer is not installed (bundle install --with test)")
    result = _check_links(site.out)
    assert result.returncode == 0, result.stdout + result.stderr
    live = make_site(tmp_path_factory.mktemp("proof"), jekyll, real=True, baseurl="/club")
    result = _check_links(live.out, swap="^/club:")
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ core extensions E1, E3, E4 (stage 5 spec, section 5)

def _extend_the_stub(root: Path) -> None:
    """The stub with a top-performer block on every game, a board kept off Home and out of the Ranks line, and its
    own column order on the Stats table, the player's totals and the game log."""
    import yaml
    sport = root / "sports" / "stub"
    rules = (sport / "rules.py").read_text(encoding="utf-8")
    note = '    blocks.append({"type": "note", "text": "Points come from the Final box and each player\'s row."})'
    assert note in rules
    rules = rules.replace(note, '''    if top is not None:
        blocks.insert(0, {"type": "top_performer", "label": "Top scorer", "player": top.player, "side": top.side,
                          "value": top.counts["pts"], "unit": "Points", "detail": "Made-up detail"})
''' + note)
    (sport / "rules.py").write_text(rules, encoding="utf-8")
    spec = yaml.safe_load((sport / "sport.yml").read_text(encoding="utf-8"))
    spec["leaderboards"].append({"id": "pts_stats", "of": "player", "group": "player", "stat": "pts",
                                 "label": "Points, Stats only", "home": False, "player_rank": False})
    spec["stats"]["columns"] = {"player": {"table": ["ppg", "pts"], "totals": ["pts", "gp"], "log": ["pts"]}}
    (sport / "sport.yml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")


@pytest.fixture(scope="module")
def extended(tmp_path_factory, jekyll) -> Site:
    return make_site(tmp_path_factory.mktemp("extended"), jekyll, edit=_extend_the_stub)


def _header_labels(html: str) -> list[list[str]]:
    """The <abbr> labels of each table header row, in order."""
    return [re.findall(r"<abbr[^>]*>([^<]*)</abbr>", row) for row in re.findall(r"<thead>(.*?)</thead>", html, re.S)]


def test_a_top_performer_links_the_player_and_is_plain_text_in_a_past_season(extended):
    page = extended.html("/games/2026-11-19-1/")
    assert re.search(r'<a class="st-top-scorer__name" href="/players/[a-z-]+/">', page)
    assert "Made-up detail" in page and "st-top-scorer__num" in page
    old = extended.html("/games/2025-10-16-1/")
    assert re.search(r'<span class="st-top-scorer__name">[^<]+</span>', old) and 'class="st-top-scorer__name" href' not in old


def test_a_board_with_home_false_is_on_the_stats_page_only(extended):
    assert "Points, Stats only" in extended.html("/stats/") and "Points, Stats only" not in extended.html("/")
    assert "Points / game" in extended.html("/")                       # the boards without the switch stay on Home


def test_a_board_with_player_rank_false_is_not_in_the_ranks_line(extended):
    page = extended.html("/players/noa-a/")
    ranks = re.search(r'<p class="st-note">Ranks: (.*?)</p>', page).group(1)
    assert "Points: No. 1" in ranks and "Points / game: No. 5" in ranks and "Stats only" not in ranks


def test_column_lists_order_the_stats_table_the_totals_and_the_game_log(extended):
    assert _header_labels(extended.html("/stats/"))[-1] == ["PPG", "PTS"]
    totals, log = _header_labels(extended.html("/players/noa-a/"))
    assert totals == ["PTS", "GP"] and log == ["PTS"]
