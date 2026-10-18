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
the body, a `<main id="main">` and a `lang`; the preview copy's banner link, and the sport previews built by scripts/build_preview.sh; every internal path goes through
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
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

from scripts import build
from tests.conftest import set_landing_page
from tests.stub_root import use_the_stub
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
              site_url: str = "", live_baseurl: str | None = None, edit=None) -> Site:
    """Copy the source, change league.yml, run build.py and Jekyll.
    league: lines appended to league.yml; real: the sample season stands in as the real one (sample_data false);
    empty: sample_data false with the real season left empty; sample_flag: build.py --sample (the /preview/ copy);
    live_baseurl: the live site's base path, as the preview copies are built with it (see build_preview.sh);
    edit: a function called with the copied source folder before build.py runs (to change a sport, say)."""
    root = tmp / "src"
    root.mkdir()
    for name in SOURCE:
        src = ROOT / name
        shutil.copytree(src, root / name) if src.is_dir() else shutil.copy(src, root / name)
    shutil.copy(ROOT / "league.yml", root / "league.yml")
    use_the_stub(root)
    text = (root / "league.yml").read_text(encoding="utf-8")
    if real or empty:
        text = text.replace("sample_data: true", "sample_data: false")
    if real:
        shutil.rmtree(root / "data" / "2026-27")
        shutil.copytree(root / "data" / "sample-2026-27", root / "data" / "2026-27")
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
    if url or live_baseurl is not None:
        overlay = f'url: "{url}"\n' + (f'live_baseurl: "{live_baseurl}"\n' if live_baseurl is not None else "")
        (root / "_config.url.yml").write_text(overlay)
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


def test_a_forfeit_page_has_no_empty_line_score(site):
    """A forfeit has no sheet, so no line score: the final panel shows the score and who forfeited, and no empty
    'Score by period' table."""
    active = site.computed("active.json")
    forfeits = [gid for gid, g in site.computed(active["season"], "games.json").items() if g["forfeit"]]
    assert forfeits, "the sample has a forfeit"
    for gid in forfeits:
        html = site.html(f"/games/{gid}/")
        assert "forfeited" in html and "st-final__score" in html, gid
        assert "st-line-score" not in html and "st-final__body" not in html, gid


def test_a_forfeit_scored_by_the_default_carries_the_placeholder_marker(site):
    """The stub leaves `standings.forfeit` undecided: the game page and the standings note say
    the forfeit score is a default the league has not confirmed."""
    active = site.computed("active.json")
    games = site.computed(active["season"], "games.json")
    forfeits = [gid for gid, g in games.items() if g["forfeit"]]
    assert forfeits
    for gid in forfeits:
        html = site.html(f"/games/{gid}/")
        assert ('<p class="st-note">[placeholder] The league has not decided how a forfeit is scored yet. '
                "The site counts it as 1–0.</p>") in html, gid
    assert "A forfeit counts as 1–0 [placeholder]." in site.html("/")
    assert "For now the site uses: 1–0" in site.html("/rules/")


def test_a_league_that_sets_the_forfeit_score_has_no_marker_for_it(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("forfeit_set"), jekyll, league="standings: {forfeit: {score: [1, 0]}}")
    gid = next(gid for gid, g in built.computed(built.computed("active.json")["season"], "games.json").items() if g["forfeit"])
    for path in (f"/games/{gid}/", "/"):
        html = built.html(path)
        assert "forfeit is scored" not in html and "A forfeit counts as" not in html, path
    assert "forfeited" in built.html(f"/games/{gid}/")
    rules = built.html("/rules/")
    assert "standings.forfeit" not in rules and "standings.tiebreakers" in rules          # the others are still listed


def test_past_season_pages_never_link_to_missing_team_or_player_pages(site):
    for path in ("/archive/sample-2025-26/", "/games/2025-10-16-1/", "/games/2025-12-11-1/"):
        page = Page(site.html(path))
        assert 'href=""' not in page.html, path
        assert not any(re.match(r"^/(players|teams)/[^/]+/", h) for h in page.hrefs), path


def _current_tab(html: str) -> list[str]:
    """The labels of the main-navigation tabs marked as the current page."""
    return re.findall(r'<a class="st-nav__link" href="[^"]*" aria-current="page">([^<]*)</a>', html)


def test_a_game_page_highlights_the_tab_it_is_reached_from(site):
    """A current-season game belongs to Schedule; a past season's game, reached from the archive, to Archive."""
    assert _current_tab(site.html("/games/2026-11-19-1/")) == ["Schedule"]
    assert _current_tab(site.html("/games/2025-10-16-1/")) == ["Archive"]
    assert _current_tab(site.html("/archive/sample-2025-26/")) == ["Archive"]


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
    # a forfeit's card says who forfeited, with the marker for the default score, in every look (Classic's quiet
    # foot included)
    assert re.search(r"<b>[^<]+</b> forfeited · score \[placeholder\]", built.html("/schedule/")), layout


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
                      baseurl="/club/preview", live_baseurl="/club")
    page = Page(built.html("/"))
    assert "Preview with sample data." in page.html
    assert 'class="st-banner__link" href="/club/"' in page.html
    assert 'href="/club/preview/schedule/"' in page.html      # its own pages stay inside the preview
    with_origin = make_site(tmp_path_factory.mktemp("preview_origin"), jekyll, empty=True, sample_flag=True,
                            baseurl="/club/preview", url="https://league.example", live_baseurl="/club")
    assert 'href="https://league.example/club/"' in with_origin.html("/")
    at_root = make_site(tmp_path_factory.mktemp("preview_root"), jekyll, empty=True, sample_flag=True,
                        baseurl="/preview", live_baseurl="")
    assert 'class="st-banner__link" href="/"' in at_root.html("/")      # an empty live_baseurl is the root, not the baseurl


def test_without_a_live_baseurl_the_banner_links_to_the_sites_own_address(tmp_path_factory, jekyll):
    built = make_site(tmp_path_factory.mktemp("no_live"), jekyll, empty=True, sample_flag=True, baseurl="/club/preview")
    assert 'class="st-banner__link" href="/club/preview/"' in built.html("/")


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


# ------------------------------------------------------------------ sport previews (stage 5 spec, section 7)

BASE = "/club"


def _copy_the_build_scripts(root: Path) -> None:
    """What scripts/build_preview.sh needs next to the copied source: itself, its helpers and the Gemfile. Also
    league.yml: the demo of basketball only (the shipped file says `true`, which today means the same)."""
    text = (root / "league.yml").read_text(encoding="utf-8")
    assert "\nsport_previews: true\n" in text
    (root / "league.yml").write_text(text.replace("\nsport_previews: true\n", "\nsport_previews: [basketball]\n"), encoding="utf-8")
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("Gemfile", "Gemfile.lock"):
        shutil.copy(ROOT / name, root / name)


def _files(folder: Path, skip: tuple[str, ...] = ()) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and p.relative_to(folder).parts[0] not in skip}


def _bundler_env(base: dict | None = None) -> dict:
    """The environment for a `bundle exec` run from a copy of the site in a temporary folder. CI installs the gems
    under the repository (ruby/setup-ruby's bundler-cache sets a relative BUNDLE_PATH), so from the copy Bundler
    would look for them in the temporary folder and report "command not found: jekyll". Pointing it at the
    repository's Gemfile makes the gem folder resolve against the repository, as for every other test here."""
    return dict(os.environ if base is None else base, BUNDLE_GEMFILE=str(ROOT / "Gemfile"))


def _real_build(root: Path) -> None:
    """The real build, as CI runs it before build_preview.sh (today is the real date, as the script's restore)."""
    assert build.main(["--root", str(root), "--out", str(root)]) == 0


def _state(root: Path) -> dict[str, dict[str, bytes]]:
    """What the real build leaves in the source folder: computed data, stub pages, calendar files."""
    return {name: _files(root / name) for name in ("_data/computed", "_games", "_players", "_teams", "_archive", "calendar")}


def _run_preview_script(root: Path, tmp: Path, *, fail_on: str = "") -> subprocess.CompletedProcess:
    """The CI steps for the copy at `root`: the main site into _site/ under BASE, then build_preview.sh. With
    `fail_on`, a `bundle` that fails when its arguments mention that text stands in front of the real one."""
    env = _bundler_env({k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"})
    env.update(BASE_PATH=BASE, SITE_ORIGIN="", JEKYLL_ENV="production")
    if fail_on:
        (tmp / "bin").mkdir()
        stub = tmp / "bin" / "bundle"
        stub.write_text(f'#!/usr/bin/env bash\ncase "$*" in *{fail_on}*) echo "bundle: made to fail" >&2; exit 7;; esac\n'
                        f'exec {shutil.which("bundle")} "$@"\n', encoding="utf-8")
        stub.chmod(0o755)
        env["PATH"] = f"{tmp / 'bin'}{os.pathsep}{env['PATH']}"
    return subprocess.run(["bash", "scripts/build_preview.sh"], cwd=root, capture_output=True, text=True, env=env)


@pytest.fixture(scope="module")
def previewed(tmp_path_factory, jekyll):
    """The real site (the stub's sample as the real season, with calendar files) under /club, then
    build_preview.sh with `sport_previews: [basketball]`: the /preview/ copy and the basketball demo beside it.
    Returns (source root, the state of the real build before the script, the script's result)."""
    tmp = tmp_path_factory.mktemp("sport_preview")
    site = make_site(tmp, jekyll, real=True, baseurl=BASE, site_url="https://x.example/club",
                     edit=_copy_the_build_scripts)
    root = site.root
    (root / "_config.ci.yml").write_text('url: ""\n')
    _real_build(root)
    main = subprocess.run([*jekyll, "build", "--source", str(root), "--destination", str(root / "_site"), "--config",
                           f"{root / '_config.yml'},{root / '_config.ci.yml'}", "--baseurl", BASE, "--quiet"],
                          cwd=root, capture_output=True, text=True, env=_bundler_env())
    assert main.returncode == 0, main.stdout + main.stderr
    before, main_site = _state(root), _files(root / "_site")
    result = _run_preview_script(root, tmp)
    return root, before, main_site, result


def test_the_script_builds_the_league_preview_and_the_sport_demo(previewed):
    root, _, _, result = previewed
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "_site" / "preview" / "index.html").is_file() and (root / "_site" / "basketball" / "index.html").is_file()
    assert "Sport preview copy: _site/basketball/" in result.stdout
    assert "Still to decide" not in result.stdout          # a demo's undecided settings are not the league's business
    league = (root / "_site" / "basketball" / "index.html").read_text(encoding="utf-8")
    assert "Riverside Masters Basketball" in league and 'data-layout="basketball"' in league
    assert "Example Valley Stub League" not in league and "Example Valley Stub League" in (root / "_site" / "index.html").read_text(encoding="utf-8")


def test_every_internal_link_and_asset_of_a_sport_preview_starts_with_its_base_path(previewed):
    root, _, _, _ = previewed
    pages = sorted((root / "_site" / "basketball").rglob("*.html"))
    assert len(pages) > 40
    for file in pages:
        page = Page(file.read_text(encoding="utf-8"))
        local = [h for h in page.hrefs + page.srcs + [l.get("href", "") for l in page.links]
                 if is_local(h) and not h.startswith(("#", "data:"))]
        outside = [h for h in local if not (h.startswith(f"{BASE}/basketball/") or h == f"{BASE}/basketball")]
        assert outside == [f"{BASE}/"] * len(outside) and len(outside) <= 1, (file.name, outside)    # only "Go to the live site"


def test_every_sport_preview_page_is_noindex_and_says_what_it_is_and_links_back(previewed):
    root, _, _, _ = previewed
    for file in sorted((root / "_site" / "basketball").rglob("*.html")):
        html = file.read_text(encoding="utf-8")
        page = Page(html)
        assert page.robots() == ["noindex, nofollow"], file
        assert "<strong>Sport preview:</strong> a made-up basketball league, to show what the template does." in html, file
        assert f'<a class="st-banner__link" href="{BASE}/">Go to the live site</a>' in html, file
        assert "Preview with sample data" not in html and "Sample data." not in html, file
    assert (root / "_site" / "index.html").is_file()                      # the link goes somewhere


def test_a_sport_preview_has_no_calendar_files_or_subscribe_links(previewed):
    root, _, _, _ = previewed
    assert not list((root / "_site" / "basketball").rglob("*.ics"))
    assert not (root / "_site" / "basketball" / "calendar").exists()
    for file in (root / "_site" / "basketball").rglob("*.html"):
        html = file.read_text(encoding="utf-8")
        assert ".ics" not in html and "webcal:" not in html, file


def test_the_real_site_is_unchanged_and_links_nowhere_into_a_sport_preview(previewed):
    root, _, main_site, _ = previewed
    assert any(k.startswith("calendar/") and k.endswith(".ics") for k in main_site)           # it has calendar files
    after = _files(root / "_site", skip=("basketball", "preview"))
    assert after == main_site                                             # every page and .ics, byte for byte
    for name, content in after.items():
        if name.endswith(".html"):
            assert b"/basketball" not in content, name


def test_the_league_preview_banner_lists_the_sport_previews_and_the_live_site(previewed):
    root, _, _, _ = previewed
    html = (root / "_site" / "preview" / "index.html").read_text(encoding="utf-8")
    assert f'Sport previews: <a class="st-banner__link" href="{BASE}/basketball/">Basketball</a>.' in html
    assert f'<a class="st-banner__link" href="{BASE}/">Go to the live site</a>' in html
    assert f'href="{BASE}/preview/schedule/"' in html


def test_the_real_build_is_back_after_the_script(previewed):
    root, before, _, _ = previewed
    assert _state(root) == before
    active = json.loads((root / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))
    assert (active["sample_mode"], active["preview"], active["preview_kind"], active["season"]) == (False, False, "", "2026-27")
    league = json.loads((root / "_data" / "computed" / "league.json").read_text(encoding="utf-8"))
    assert league["name"] == "Example Valley Stub League"


@pytest.mark.parametrize("failing", ["_site/basketball", "_site/preview"])
def test_the_real_build_is_back_when_a_step_fails(previewed, tmp_path, failing):
    root, before, _, _ = previewed
    result = _run_preview_script(root, tmp_path, fail_on=failing)
    assert result.returncode == 7, result.stdout + result.stderr
    assert "made to fail" in result.stderr
    assert _state(root) == before


@pytest.fixture
def league_yml(previewed):
    """The source's league.yml, put back after a test changes it."""
    path = previewed[0] / "league.yml"
    text = path.read_text(encoding="utf-8")
    yield path, text
    path.write_text(text, encoding="utf-8")


def test_the_script_does_nothing_when_nothing_is_asked_for(previewed, league_yml, tmp_path):
    path, text = league_yml
    path.write_text(text.replace("sport_previews: [basketball]", "sport_previews: false") + "\npreview: false\n",
                    encoding="utf-8")
    result = _run_preview_script(previewed[0], tmp_path)
    assert result.returncode == 0 and "Preview copies: none" in result.stdout
    assert _state(previewed[0]) == previewed[1]


def _without_sample_seasons(previewed, tmp: Path) -> Path:
    """A copy of the previewed source (not its _site/) whose data/seasons.yml lists no sample season and whose sample
    folders are gone: a real league that cleaned them out and left `preview: true` (the default)."""
    root = tmp / "no-sample"
    shutil.copytree(previewed[0], root, ignore=shutil.ignore_patterns("_site", "__pycache__"))
    seasons = [s for s in yaml.safe_load((root / "data" / "seasons.yml").read_text(encoding="utf-8")) if not s.get("sample")]
    (root / "data" / "seasons.yml").write_text(yaml.safe_dump(seasons, allow_unicode=True), encoding="utf-8")
    for folder in root.glob("data/sample-*"):
        shutil.rmtree(folder)
    return root


def test_without_a_sample_season_the_script_skips_preview_and_still_builds_the_sport_previews(previewed, tmp_path):
    root = _without_sample_seasons(previewed, tmp_path)
    _real_build(root)
    before = _state(root)
    result = _run_preview_script(root, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no sample season in data/seasons.yml: skipping /preview/" in result.stdout
    assert "sample_data is on" not in result.stdout + result.stderr
    assert not (root / "_site" / "preview").exists()
    assert (root / "_site" / "basketball" / "index.html").is_file()
    assert "Sport preview copy: _site/basketball/" in result.stdout
    assert _state(root) == before                                          # and the real build is back


def test_without_a_sample_season_and_without_sport_previews_the_script_has_nothing_to_do(previewed, tmp_path):
    root = _without_sample_seasons(previewed, tmp_path)
    path = root / "league.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("sport_previews: [basketball]", "sport_previews: false"), encoding="utf-8")
    result = _run_preview_script(root, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipping /preview/" in result.stdout and not (root / "_site" / "preview").exists()


def test_a_broken_sample_season_still_stops_the_preview(previewed, tmp_path):
    """Only a missing sample season skips /preview/: one that is listed but not there is a real problem."""
    root = tmp_path / "broken"
    shutil.copytree(previewed[0], root, ignore=shutil.ignore_patterns("_site", "__pycache__"))
    shutil.rmtree(next(root.glob("data/sample-2026-27")))
    result = _run_preview_script(root, tmp_path)
    assert result.returncode != 0 and "skipping /preview/" not in result.stdout


def test_a_sport_id_that_is_a_page_of_the_site_stops_the_script_before_it_builds(previewed, league_yml, tmp_path):
    root, before, _, _ = previewed
    shutil.copytree(root / "sports" / "basketball", root / "sports" / "stats", ignore=shutil.ignore_patterns("__pycache__"))
    try:
        path, text = league_yml
        path.write_text(text.replace("sport_previews: [basketball]", "sport_previews: [stats]"), encoding="utf-8")
        result = _run_preview_script(root, tmp_path)
    finally:
        shutil.rmtree(root / "sports" / "stats")
    assert result.returncode == 1
    assert "sport_previews.0" in result.stderr and "already a page or folder of the site" in result.stderr
    assert "Sport preview copy" not in result.stdout and _state(root) == before


def test_a_test_sport_or_a_typo_in_sport_previews_stops_the_script_with_the_sports_there_are(previewed, league_yml, tmp_path):
    path, text = league_yml
    path.write_text(text.replace("sport_previews: [basketball]", "sport_previews: [stub, basketbal]"), encoding="utf-8")
    result = _run_preview_script(previewed[0], tmp_path)
    assert result.returncode == 1
    assert "sport_previews.0" in result.stderr and "demo: false" in result.stderr
    assert "sport_previews.1" in result.stderr and "Did you mean 'basketball'?" in result.stderr


def test_a_sport_preview_banner_links_to_the_other_sport_previews(tmp_path_factory, jekyll):
    """Two demo sports (basketball and a copy of it called Hoops): each copy's banner names the other, not itself."""
    import re as _re
    from scripts import preview_root

    def add_hoops(root: Path) -> None:
        shutil.copytree(root / "sports" / "basketball", root / "sports" / "hoops", ignore=shutil.ignore_patterns("__pycache__"))
        spec = root / "sports" / "hoops" / "sport.yml"
        spec.write_text(_re.sub(r"(?m)^name: .*$", "name: Hoops", spec.read_text(encoding="utf-8")), encoding="utf-8")
        text = (root / "league.yml").read_text(encoding="utf-8")
        (root / "league.yml").write_text(text.replace("\nsport_previews: true\n", "\nsport_previews: [basketball, hoops]\n"),
                                         encoding="utf-8")

    tmp = tmp_path_factory.mktemp("two_sports")
    site = make_site(tmp, jekyll, real=True, edit=add_hoops)
    banners = {}
    for sport_id in ("basketball", "hoops"):
        temp_root = preview_root.write_root(sport_id, tmp / f"root-{sport_id}", site.root)
        assert build.main(["--root", str(temp_root), "--out", str(site.root), "--sport-preview", sport_id]) == 0
        overlay = tmp / f"{sport_id}.yml"
        overlay.write_text(f'url: "https://league.example"\nbaseurl: "/club/{sport_id}"\nlive_baseurl: "/club"\n')
        out = tmp / f"out-{sport_id}"
        proc = subprocess.run([*jekyll, "build", "--source", str(site.root), "--destination", str(out), "--config",
                               f"{site.root / '_config.yml'},{overlay}", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        banners[sport_id] = _re.search(r'<div class="st-banner".*?</div>', (out / "index.html").read_text(encoding="utf-8")).group(0)
    assert ('Other sports: <a class="st-banner__link" href="https://league.example/club/hoops/">Hoops</a>.' in banners["basketball"]
            and "/club/basketball/" not in banners["basketball"])
    assert ('Other sports: <a class="st-banner__link" href="https://league.example/club/basketball/">Basketball</a>.' in banners["hoops"]
            and "/club/hoops/" not in banners["hoops"])
    for banner in banners.values():
        assert '<a class="st-banner__link" href="https://league.example/club/">Go to the live site</a>' in banner
        assert "a made-up" in banner


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


# ------------------------------------------------------------------ core extensions E5, E6 (curling spec, section 6)

def _add_numbers_and_roster_to_the_stub(root: Path) -> None:
    """The stub with a `numbers` and a `roster` block on every game: the first player of a side is its key row, the
    second is a spare for the third."""
    sport = root / "sports" / "stub"
    rules = (sport / "rules.py").read_text(encoding="utf-8")
    note = '    blocks.append({"type": "note", "text": "Points come from the Final box and each player\'s row."})'
    assert note in rules
    rules = rules.replace(note, '''    blocks.append({"type": "numbers", "title": "The game in numbers", "corner": "This game", "note": "A made-up note.",
                   "rows": [{"label": "Points", "cells": {"home": str(score.final["home"]), "away": str(score.final["away"])},
                             "key": "home" if score.final["home"] > score.final["away"] else "away", "hot": False},
                            {"label": "Stolen", "cells": {"home": "1", "away": "0"}, "key": "home", "hot": True}]})
    teams = []
    for side in SIDE_KEYS:
        people = [ln.player for ln in reading.lines if ln.side == side]
        if len(people) >= 3:
            teams.append({"side": side, "rows": [
                {"role": "Lead", "player": people[0], "key": True, "spare_for": None},
                {"role": "Second", "player": people[1], "key": False, "spare_for": people[2]}]})
    blocks.append({"type": "roster", "title": "Lineups", "teams": teams, "link_label": "Team", "note": "In order."})
''' + note)
    (sport / "rules.py").write_text(rules, encoding="utf-8")


@pytest.fixture(scope="module")
def lineups(tmp_path_factory, jekyll) -> Site:
    return make_site(tmp_path_factory.mktemp("lineups"), jekyll, edit=_add_numbers_and_roster_to_the_stub)


def test_a_roster_head_links_the_team_page_and_is_a_plain_div_in_a_past_season(lineups):
    page = lineups.html("/games/2026-11-19-1/")
    assert re.search(r'<a class="st-roster__head" href="/teams/[a-z-]+/">', page)
    assert "st-roster__link" in page and "for " in page and "st-badge--outline" in page
    old = lineups.html("/games/2025-10-16-1/")
    assert "st-roster__head" in old and "st-roster__list" in old
    assert re.search(r'<div class="st-roster__head">', old) and '<a class="st-roster__head"' not in old
    assert "st-roster__link" not in old
    assert not any(re.match(r"^/teams/[^/]+/", h) for h in Page(old).hrefs)


def test_the_numbers_block_heads_each_column_with_the_teams_code_and_marks_the_key_cell(lineups):
    page = lineups.html("/games/2026-11-19-1/")
    table = re.search(r'<table class="st-table st-table--numbers">.*?</table>', page, re.S).group(0)
    assert len(re.findall(r'<th scope="col"><span class="st-chip', table)) == 2
    assert table.count('class="is-key"') >= 1 and table.count('class="is-key is-hot"') == 1
    assert "A made-up note." in page


# ------------------------------------------------------------------ core extension E9: the results legend

LEGEND = [{"kind": "hammer", "text": "Hammer in end 1"}, {"kind": "mark", "text": "Stolen end"},
          {"kind": "x", "text": "Not played"}]


def _add_a_results_legend_to_the_stub(root: Path) -> None:
    """The stub's sport.yml with `display.results_legend` (as curling's will have)."""
    path = root / "sports" / "stub" / "sport.yml"
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec["display"]["results_legend"] = LEGEND
    path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")


@pytest.fixture(scope="module")
def legend(tmp_path_factory, jekyll) -> Site:
    return make_site(tmp_path_factory.mktemp("legend"), jekyll, edit=_add_a_results_legend_to_the_stub)


def _team_with_results(built: Site) -> str:
    teams = built.computed(built.computed("active.json")["season"], "teams.json")
    return next(t["url"] for t in teams.values() if t["results"])


def test_a_sport_with_a_results_legend_prints_it_above_the_result_cards(legend):
    for path in ("/", "/schedule/", _team_with_results(legend)):
        html = legend.html(path)
        assert html.count('<div class="st-legend">') == 1, path
        block = re.search(r'<div class="st-legend">(.*?)</div>', html, re.S).group(1)
        # the keys are decoration (aria-hidden); the words beside them are plain visible text
        assert re.findall(r"<span>([^<]+)</span></span>", block) == [i["text"] for i in LEGEND], path
        assert '<svg class="st-hammer"' in block and 'aria-hidden="true" focusable="false"' in block
        assert 'st-legend__key--mark" aria-hidden="true"' in block and 'st-legend__key--x" aria-hidden="true">X<' in block
        after = html[html.index('<div class="st-legend">'):]
        assert after.index("st-result-card") < after.index("</main>"), path     # result cards follow it


def test_without_a_results_legend_no_page_prints_one(site, previewed):
    """The stub and basketball set no `display.results_legend`: Home, Schedule and team pages have no legend."""
    assert site.computed("league.json")["results_legend"] == []
    for path in ("/", "/schedule/", _team_with_results(site)):
        assert "st-legend" not in site.html(path), path
    demo = previewed[0] / "_site" / "basketball"
    pages = [demo / "index.html", demo / "schedule" / "index.html", *sorted((demo / "teams").glob("*/index.html"))]
    assert len(pages) > 3
    for file in pages:
        assert "st-legend" not in file.read_text(encoding="utf-8"), file


# ------------------------------------------------------------------ the curling sport preview (stage 5, part 2)

@pytest.fixture(scope="module")
def curling_demo(previewed, tmp_path_factory):
    """build_preview.sh with `sport_previews: [basketball, curling]` (and no /preview/), run on a copy of the
    previewed source: the curling demo beside the basketball one, under BASE. Returns (copy of the source, result)."""
    tmp = tmp_path_factory.mktemp("curling_demo")
    root = tmp / "root"
    shutil.copytree(previewed[0], root, ignore=shutil.ignore_patterns("_site", "__pycache__"))
    path = root / "league.yml"
    text = path.read_text(encoding="utf-8")
    assert "sport_previews: [basketball]" in text
    path.write_text(text.replace("sport_previews: [basketball]", "sport_previews: [basketball, curling]") + "\npreview: false\n",
                    encoding="utf-8")
    return root, _run_preview_script(root, tmp)


def _curling(demo, path: str) -> str:
    return (demo[0] / "_site" / "curling" / path.strip("/") / "index.html").read_text(encoding="utf-8")


def _curling_games(demo) -> dict[str, str]:
    return {file.parent.name: file.read_text(encoding="utf-8")
            for file in sorted((demo[0] / "_site" / "curling" / "games").glob("*/index.html"))}


def test_the_script_builds_the_curling_demo_beside_the_basketball_one(curling_demo):
    root, result = curling_demo
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Sport preview copy: _site/curling/" in result.stdout and "Sport preview copy: _site/basketball/" in result.stdout
    assert "Still to decide" not in result.stdout
    home = _curling(curling_demo, "/")
    assert "Pine Lake Curling Club" in home and 'data-layout="curling"' in home
    assert f'href="{BASE}/curling/assets/css/layouts/curling.css"' in home
    assert "Riverside Masters Basketball" not in home and "Example Valley Stub League" not in home
    assert 'data-layout="basketball"' in (root / "_site" / "basketball" / "index.html").read_text(encoding="utf-8")
    assert not (root / "_site" / "preview").exists()


def test_every_curling_preview_page_has_its_base_path_the_noindex_tag_and_the_banner(curling_demo):
    root = curling_demo[0]
    pages = sorted((root / "_site" / "curling").rglob("*.html"))
    assert len(pages) > 60
    for file in pages:
        html = file.read_text(encoding="utf-8")
        page = Page(html)
        local = [h for h in page.hrefs + page.srcs + [l.get("href", "") for l in page.links]
                 if is_local(h) and not h.startswith(("#", "data:"))]
        outside = [h for h in local if not (h.startswith(f"{BASE}/curling/") or h == f"{BASE}/curling")]
        assert sorted(outside) == [f"{BASE}/", f"{BASE}/basketball/"] or outside == [f"{BASE}/"], (file.name, outside)
        assert page.robots() == ["noindex, nofollow"], file
        assert "<strong>Sport preview:</strong> a made-up curling league, to show what the template does." in html, file
        assert f'Other sports: <a class="st-banner__link" href="{BASE}/basketball/">Basketball</a>.' in html, file
        assert f'<a class="st-banner__link" href="{BASE}/">Go to the live site</a>' in html, file


def test_the_curling_preview_has_no_calendar_files_or_subscribe_links(curling_demo):
    site = curling_demo[0] / "_site" / "curling"
    assert not list(site.rglob("*.ics")) and not (site / "calendar").exists()
    for file in site.rglob("*.html"):
        html = file.read_text(encoding="utf-8")
        assert ".ics" not in html and "webcal:" not in html, file


def test_a_curling_game_that_ended_in_a_concession_says_so_on_the_page_and_the_card(curling_demo):
    conceded = {gid: html for gid, html in _curling_games(curling_demo).items()
                if re.search(r"Shook hands after \d+ of 8 ends", html)}
    assert conceded, "the sample has a concession"
    schedule = _curling(curling_demo, "/schedule/")
    for gid, html in conceded.items():
        assert 'class="is-void"' in html and "st-table--numbers" in html and "st-roster" in html, gid
        assert 'svg class="st-hammer"' in html, gid
        if f'href="{BASE}/curling/games/{gid}/"' in schedule:        # a game of the current season: its card says it too
            assert re.search(r"Shook hands after \d+<", schedule) or re.search(r"Shook hands after \d+ ", schedule), gid


def test_a_curling_game_with_an_extra_end_has_the_ee_column_and_the_final_ee_status(curling_demo):
    extra = {gid: html for gid, html in _curling_games(curling_demo).items() if "Final · EE" in html}
    assert extra, "the past sample season has an extra-end game"
    for gid, html in extra.items():
        assert '<th scope="col">EE</th>' in html and "8 ends · extra end" in html, gid
        assert "st-table--numbers" in html and "st-roster" in html, gid
        assert 'class="st-roster__head" href' not in html and '<div class="st-roster__head">' in html, gid   # a past season: no link
    assert not any("Final · OT" in html or ">OT<" in html for html in _curling_games(curling_demo).values())


def test_a_curling_game_of_this_season_links_each_rink_and_shows_a_spare(curling_demo):
    games = {gid: html for gid, html in _curling_games(curling_demo).items() if gid >= "2026" and "st-roster" in html}
    assert len(games) > 10                                            # (a forfeit has no lineups)
    assert all(f'<a class="st-roster__head" href="{BASE}/curling/teams/' in html for html in games.values())
    assert any('st-badge st-badge--outline">Spare</span> <span class="st-roster__for">for ' in html for html in games.values())
    assert all("Lead</span>" in html or ">Lead<" in html for html in games.values())


def test_the_curling_home_schedule_and_team_pages_show_the_legend_the_draws_the_sheets_and_the_skip(curling_demo):
    for path in ("/", "/schedule/", "/teams/stone-cold/"):
        html = _curling(curling_demo, path)
        assert html.count('<div class="st-legend">') == 1, path
        block = re.search(r'<div class="st-legend">(.*?)</div>', html, re.S).group(1)
        assert re.findall(r"<span>([^<]+)</span></span>", block) == ["Hammer in end 1", "Stolen end", "Not played"], path
    home, schedule = _curling(curling_demo, "/"), _curling(curling_demo, "/schedule/")
    assert "Latest draw" in home and "Next draw" in home and "Rink leaders" in home and ">Rink<" in home
    assert re.search(r"Draw \d+", schedule) and "Sheet A" in schedule and "Sheet C" in schedule
    assert re.search(r"Skip [A-Z][a-z]+ [A-Z]\.", _curling(curling_demo, "/teams/stone-cold/"))
    assert 'data-layout="curling"' in home


def test_a_curling_forfeit_card_says_who_forfeited_after_the_sheet_and_time(curling_demo):
    """Curling's card foot is the meta ("Sheet A · 6:30 PM"); a forfeit has no line score, so without the note
    the card would read like a 1-0 game."""
    schedule = _curling(curling_demo, "/schedule/")
    feet = re.findall(r'<span class="st-result-card__note">(.*?)</span><span class="st-result-card__link">Details', schedule)
    assert feet, "the sample has a forfeit"
    for foot in feet:
        assert re.fullmatch(r"Sheet [A-C] · \d+:\d\d PM · <b>[A-Za-z ]+</b> forfeited · score \[placeholder\]", foot), foot


def test_the_basketball_demo_next_to_the_curling_one_has_no_curling_in_it(curling_demo):
    site = curling_demo[0] / "_site" / "basketball"
    for file in site.rglob("*.html"):
        html = file.read_text(encoding="utf-8")
        assert '<div class="st-legend">' not in html and "Pine Lake" not in html and "st-table--numbers" not in html, file


# ------------------------------------------------------------------ the landing page (docs/landing-page-plan.md)
# The CI chain with `landing_page: true` as the template ships it, in a temporary copy under a base path: build.py,
# the main Jekyll build with the overlay build.py wrote, scripts/build_preview.sh. The league is the shipped one
# (basketball), so what the landing page links to is what the demos are.

SOURCE_LANDING = SOURCE + ["landing", "landing.yml", "scripts", "Gemfile", "Gemfile.lock"]
LANDING_OLD_COMMIT = "a9c507f"              # the commit before any landing page work (origin/main when it was planned)


def _landing_chain(tmp: Path, jekyll: list[str], *, league_text=None, source: Path = ROOT, overlay: bool = True
                   ) -> tuple[Path, subprocess.CompletedProcess, str]:
    """Copy the source, write league.yml (`league_text(the source's text)`), run build.py, the main Jekyll build
    (with _config.landing.yml when `overlay`) and build_preview.sh, all under BASE. Returns (the copy, the script's
    result, the main Jekyll build's output)."""
    root = tmp / "src"
    root.mkdir()
    for name in SOURCE_LANDING:
        src = source / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, root / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(src, root / name)
    text = (source / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(league_text(text) if league_text else text, encoding="utf-8")
    (root / "_config.ci.yml").write_text('url: ""\n')
    env = _bundler_env({k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"})
    env.update(BASE_PATH=BASE, SITE_ORIGIN="", JEKYLL_ENV="production")
    built = subprocess.run([sys.executable, str(root / "scripts" / "build.py"), "--root", str(root), "--out", str(root),
                            "--today", "2026-11-20", "--site-url", BASE],
                           cwd=root, capture_output=True, text=True, env=env)
    assert built.returncode == 0, built.stdout + built.stderr
    configs = ["_config.yml"] + (["_config.landing.yml"] if overlay else []) + ["_config.ci.yml"]
    main = subprocess.run([*jekyll, "build", "--config", ",".join(configs), "--baseurl", BASE],
                          cwd=root, capture_output=True, text=True, env=env)
    assert main.returncode == 0, main.stdout + main.stderr
    result = subprocess.run(["bash", "scripts/build_preview.sh"], cwd=root, capture_output=True, text=True, env=env)
    return root, result, main.stdout + main.stderr


@pytest.fixture(scope="module")
def landed(tmp_path_factory, jekyll):
    """The template as shipped (landing_page: true): (source copy, build_preview.sh's result, the main build's output)."""
    assert "\nlanding_page: true\n" in (ROOT / "league.yml").read_text(encoding="utf-8")
    return _landing_chain(tmp_path_factory.mktemp("landing_on"), jekyll)


def _landing_page(landed) -> tuple[str, Page]:
    html = (landed[0] / "_site" / "index.html").read_text(encoding="utf-8")
    return html, Page(html)


def _file_of(site: Path, href: str) -> Path:
    """The built file a link on the site (under BASE) reaches."""
    path = href.split("#")[0].split("?")[0]
    assert path == BASE or path.startswith(BASE + "/"), href
    rel = path[len(BASE):].lstrip("/")
    return site / rel / "index.html" if (not rel or path.endswith("/")) else site / rel


def test_with_the_switch_on_the_root_is_the_landing_page_beside_404_and_the_demos(landed):
    root, result, main_output = landed
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (root / "_site").iterdir()) == ["404.html", "assets", "basketball", "curling", "index.html"]
    assert "skipping /preview/" in result.stdout and "Sport preview copy: _site/curling/" in result.stdout
    assert "Conflict" not in main_output + result.stdout + result.stderr
    html, page = _landing_page(landed)
    assert "<title>scorers-table</title>" in html and page.h1 == 1
    assert "A website for your league, from its score sheets" in html
    assert 'id="sports"' in html and 'id="get-started"' in html
    assert page.html_attrs["data-layout"] == "basketball"                     # the landing page is the Basketball look
    assert "Copying this template? Set landing_page: false in league.yml" in html
    assert page.robots() == ["noindex, nofollow"]
    assert (root / "_config.landing.yml").read_text(encoding="utf-8").startswith("# Written by scripts/build.py")


def test_the_landing_page_loads_each_sports_look_after_its_own_and_draws_every_window_in_it(landed):
    _, page = _landing_page(landed)
    css = page.stylesheets()
    own, extra, base = (css.index(f"{BASE}/assets/css/{n}.css") for n in ("layouts/basketball", "layouts/curling", "base"))
    assert own < extra < base
    assert re.findall(r'<div class="st-page st-sport-card__window" data-layout="([a-z]+)"', page.html) == ["basketball", "curling"]
    assert page.html.index('aria-label="Basketball demo preview"') < page.html.index('aria-label="Curling demo preview"')


def test_every_link_of_the_landing_page_and_404_goes_somewhere_and_starts_with_the_base_path(landed):
    root, _, _ = landed
    site = root / "_site"
    for name in ("index.html", "404.html"):
        page = Page((site / name).read_text(encoding="utf-8"))
        local = [h for h in page.hrefs + page.srcs + [l.get("href", "") for l in page.links]
                 if is_local(h) and not h.startswith(("#", "data:"))]
        assert local, name
        for href in local:
            assert _file_of(site, href).is_file(), (name, href)
    html, page = _landing_page(landed)
    hrefs = set(page.hrefs)
    assert {f"{BASE}/basketball/", f"{BASE}/curling/", f"{BASE}/#sports", f"{BASE}/#get-started"} <= hrefs
    assert any(h.startswith(f"{BASE}/basketball/games/") for h in hrefs)
    assert any(h.startswith(f"{BASE}/curling/games/") for h in hrefs)
    assert "https://github.com/kylermurphy/scorers-table#publish-it" in hrefs                      # the setup guide
    assert "design-system" not in html
    notfound = (site / "404.html").read_text(encoding="utf-8")
    assert f'href="{BASE}/#sports"' in notfound and f'href="{BASE}/#get-started"' in notfound


def test_the_teams_and_games_the_cards_name_have_pages_in_their_demo(landed):
    root, _, _ = landed
    page = json.loads((root / "_data" / "computed" / "landing.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in page["sports"]] == ["basketball", "curling"]
    for sport in page["sports"]:
        for team in sport["window"]["teams"].values():
            assert team["url"].startswith(f"/{sport['id']}/teams/"), team
            assert (root / "_site" / team["url"].strip("/") / "index.html").is_file(), team["url"]
        game_url = sport["window"]["latest"]["game"]["url"]
        assert game_url.startswith(f"/{sport['id']}/games/")
        assert (root / "_site" / game_url.strip("/") / "index.html").is_file()


def test_the_coming_soon_cards_have_no_link_and_no_window(landed):
    html, _ = _landing_page(landed)
    soon = re.findall(r'<article class="st-card st-sport-card st-sport-card--soon">.*?</article>', html, re.S)
    assert len(soon) == 2 and "Hockey" in soon[0] and "Slo-pitch" in soon[1]
    for card in soon:
        assert "<a " not in card and "href" not in card and "st-sport-card__window" not in card
        assert "Coming soon" in card


def test_the_landing_page_requests_nothing_from_another_site(landed):
    html, page = _landing_page(landed)
    assert all(is_local(s) for s in page.srcs) and all(is_local(l.get("href", "")) for l in page.links)
    assert "@import" not in html and "http://" not in html
    setup, code = "https://github.com/kylermurphy/scorers-table#publish-it", "https://github.com/kylermurphy/scorers-table"
    assert sorted(h for h in page.hrefs if not is_local(h)) == sorted([setup, code, setup, code, code])   # page, footer, credit
    assert page.srcs == [f"{BASE}/assets/js/site.js"]


def test_without_javascript_the_landing_page_and_its_windows_follow_the_phone(landed):
    html, page = _landing_page(landed)
    assert "data-theme" not in page.html_attrs                                  # the head script sets it only from a saved choice
    assert not re.search(r'<div class="st-page st-sport-card__window"[^>]*data-theme', html)
    assert page.buttons and all("hidden" in b for b in page.buttons)             # the theme button stays hidden without JS
    assert html.count('querySelectorAll(".st-sport-card__window")') == 1       # the saved choice, copied before the first paint


def test_the_demos_banners_say_all_sports_and_link_to_the_landing_page(landed):
    root, _, _ = landed
    for sport in ("basketball", "curling"):
        pages = sorted((root / "_site" / sport).rglob("*.html"))
        assert len(pages) > 40
        for file in pages:
            html = file.read_text(encoding="utf-8")
            assert f'<a class="st-banner__link" href="{BASE}/">All sports</a>' in html, file
            assert "Go to the live site" not in html, file
            assert Page(html).robots() == ["noindex, nofollow"], file
    other = (root / "_site" / "curling" / "index.html").read_text(encoding="utf-8")
    assert f'Other sports: <a class="st-banner__link" href="{BASE}/basketball/">Basketball</a>.' in other
    assert "st-banner" not in (root / "_site" / "index.html").read_text(encoding="utf-8")      # no sample banner on the landing page


def test_the_source_is_left_as_the_real_build_writes_it(landed):
    root, _, _ = landed
    assert (root / "_data" / "computed" / "landing.json").is_file()            # the restore at the end of build_preview.sh
    assert "\nlanding_page: true\n" in (root / "_config.landing.yml").read_text(encoding="utf-8")
    active = json.loads((root / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))
    assert active["preview_kind"] == "" and active["sample_mode"] is True


# ------------------------------------------------------------------ the switch off: today's site, byte for byte

def _html_tree(site: Path) -> dict[str, bytes]:
    return {p.relative_to(site).as_posix(): p.read_bytes() for p in sorted(site.rglob("*.html"))}


@pytest.fixture(scope="module")
def landing_off(tmp_path_factory, jekyll):
    """The same chain with the `landing_page` line left out (every existing copy of the template), the overlay on."""
    return _landing_chain(tmp_path_factory.mktemp("landing_off"), jekyll, league_text=lambda t: set_landing_page(t, None))


def test_with_the_line_left_out_the_overlay_is_one_line_and_the_site_is_the_leagues_own(landing_off):
    root, result, _ = landing_off
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "_config.landing.yml").read_text(encoding="utf-8") == "landing_page: false\n"
    assert not (root / "_data" / "computed" / "landing.json").exists()
    names = {p.name for p in (root / "_site").iterdir()}
    assert {"schedule", "stats", "teams", "archive", "rules", "games", "players", "basketball", "curling"} <= names
    assert not ({"landing", "landing.yml"} & names)
    assert "A website for your league" not in (root / "_site" / "index.html").read_text(encoding="utf-8")
    demo = (root / "_site" / "curling" / "index.html").read_text(encoding="utf-8")
    assert f'href="{BASE}/">Go to the live site</a>' in demo and "All sports" not in demo


def test_the_overlay_that_says_off_changes_no_byte_of_the_root(landing_off, tmp_path, jekyll):
    root, _, _ = landing_off
    env = _bundler_env({k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"})
    env.update(JEKYLL_ENV="production")
    without = tmp_path / "without"
    proc = subprocess.run([*jekyll, "build", "--config", "_config.yml,_config.ci.yml", "--baseurl", BASE,
                           "--destination", str(without), "--quiet"], cwd=root, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _files(root / "_site", skip=("basketball", "curling")) == _files(without)


def _have_the_old_commit() -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{LANDING_OLD_COMMIT}^{{commit}}"], cwd=ROOT,
                          capture_output=True).returncode == 0


@pytest.mark.skipif(not _have_the_old_commit(), reason=f"commit {LANDING_OLD_COMMIT} (before the landing page work) is not in this clone")
def test_with_the_line_left_out_every_page_is_what_the_commit_before_the_landing_work_built(landing_off, tmp_path_factory, jekyll):
    """The riskiest promise of the plan: a league that never heard of `landing_page` gets today's site. Build the
    commit before the landing work the way CI did then (no overlay) and compare every HTML page of the root and of
    both demos with the new chain's. (The stylesheets and scripts changed with the sport card part, so only the pages
    are compared.)"""
    tmp = tmp_path_factory.mktemp("landing_before")
    old = tmp / "old"
    old.mkdir()
    archive = subprocess.run(["git", "archive", LANDING_OLD_COMMIT], cwd=ROOT, capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(old)], input=archive.stdout, check=True)
    root, result, _ = _landing_chain(tmp, jekyll, source=old, overlay=False)
    assert result.returncode == 0, result.stdout + result.stderr
    before, after = _html_tree(root / "_site"), _html_tree(landing_off[0] / "_site")
    assert sorted(before) == sorted(after) and len(before) > 150
    different = [name for name in before if before[name] != after[name]]
    assert different == [], different[:10]
