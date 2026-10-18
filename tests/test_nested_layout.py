"""The landing page's sport cards hold a WINDOW in the sport's own look inside a page that has another look
(docs/landing-page-plan.md sections 3 and 4, question 1). That nesting is only safe while two things stay true,
and this file is where they are enforced:

  1. the page's look does not LEAK IN: no CSS rule of the page's layout reaches an element of a window, and no
     custom property the page's layout sets is left unset (and so inherited) by a window's layout;
  2. the window's look does not LEAK OUT: every rule of a layout file is scoped by that layout's own
     `[data-layout="id"]`, so loading all six layout files, in any order, changes nothing outside the elements
     that carry that attribute (and the sport card's own rules name no layout at all).

Two kinds of test:
  * static ones read assets/css/ and the sport card specimen (always run, no browser);
  * browser ones (Playwright + Chromium; skipped without them, like the old-browser test in
    test_css_fallbacks.py) lay out the real CSS and compare every computed style of a window inside each of the
    six page looks, light and dark, with the same window on a plain page; check that without JavaScript a window
    follows the phone's colour scheme; and press the real theme button of assets/js/site.js.

The cost of loading every layout (the plan's "Curling stylesheet 14 KB, fonts about 72 KB") is measured too.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_contrast as cc  # noqa: E402
from scripts.design_system import sample, specimens_shell  # noqa: E402
from scripts.design_system.model import Ctx  # noqa: E402

CSS = ROOT / "assets" / "css"
LAYOUTS = cc.layout_ids()                         # basketball classic curling hockey scoreboard slopitch
LANDING_LAYOUT = "basketball"                     # the landing page's own look (plan section 4)
PART_FILES = ["tokens.css", "base.css", "parts-shell.css", "parts-scores.css", "parts-data.css"]
CSS_ORDER = ["fonts.css", "tokens.css", "layouts/{page}.css", "base.css", "parts-shell.css", "parts-scores.css",
             "parts-data.css", "fallbacks.css"]
# What encloses a window on the landing page, outside the window: a rule may use these in the middle of a selector.
ABOVE_THE_WINDOW = {"st-page", "st-main", "st-section", "st-list", "st-card", "st-sport-card"}
# Rules of the landing page's look that DO name a class a window holds, and why that is fine.
ALLOWED_REACH = {
    '[data-layout="basketball"][data-league-colour] .st-line-score':
        "needs data-league-colour on an ancestor: only a league with its own colour sets it; the showcase never does",
}


def _sport_card_html(theme: str = "light") -> str:
    part = next(p for p in specimens_shell.PARTS if p.id == "sport-card")
    lay = sample.LAYOUT_BY_ID["basketball"]
    return part.render(Ctx(layout="basketball", theme=theme, sport="basketball", league=sample.LEAGUES["basketball"],
                           layout_meta=lay))


def _windows(html: str) -> list[str]:
    """The markup of each window (the element with class st-sport-card__window, up to the demo link after it)."""
    found = re.findall(r'<div class="st-page st-sport-card__window".*?(?=<a class="st-button st-sport-card__go")', html)
    assert len(found) == 2, "the specimen should hold a Basketball window and a Curling window"
    return found


def _window_vocabulary() -> tuple[set[str], set[str]]:
    classes, tags = set(), set()
    for w in _windows(_sport_card_html()):
        for value in re.findall(r'class="([^"]*)"', w):
            classes.update(value.split())
        tags.update(re.findall(r"<([a-z][a-z0-9]*)", w))
    return classes, tags


def _classes(compound: str) -> set[str]:
    return set(re.findall(r"\.([\w-]+)", re.sub(r"\[[^\]]*\]", "", compound)))


def _descendant_compounds(selector: str) -> list[str]:
    return [c for c in cc.split_ws(selector) if c not in (">", "+", "~")]


def _rules(files):
    for name in files:
        for rule in cc.load_rules(CSS / name):
            yield name, rule


# ---------------------------------------------------------------------------- static: nothing leaks in

def test_the_specimen_has_a_window_in_two_looks():
    html = _sport_card_html()
    assert 'data-layout="basketball"' in html and 'data-layout="curling"' in html
    assert html.count("st-sport-card--soon") == 2 and html.count('class="st-button st-sport-card__go"') == 2


def test_no_rule_of_the_landing_look_reaches_into_a_window():
    """A rule like `[data-layout="basketball"] .st-result-card` would also style the result card inside a Curling
    window. Reaching means: a layout-qualified ancestor, in-between compounds that the window or the page above it
    can match, and a last compound made only of classes (or a bare tag) a window holds."""
    classes, tags = _window_vocabulary()
    reach = classes | ABOVE_THE_WINDOW
    layout_attr = f'[data-layout="{LANDING_LAYOUT}"]'
    hits = []
    for name, rule in _rules(PART_FILES + [f"layouts/{l}.css" for l in LAYOUTS]):
        comps = _descendant_compounds(rule.selector)
        for i, comp in enumerate(comps[:-1]):
            if layout_attr not in comp:
                continue
            middle_ok = all(not _classes(m) or _classes(m) & reach for m in comps[i + 1:-1])
            subject = comps[-1]
            wanted = _classes(subject)
            bare = re.match(r"[a-z][a-z0-9]*", subject) if not wanted else None
            reaches = (wanted and wanted <= classes) or (bare and bare.group(0) in tags)
            if middle_ok and reaches and rule.selector not in ALLOWED_REACH:
                hits.append(f"{name}: {rule.selector}")
            break
    assert not hits, ("these rules of the landing page's look also style elements inside the sport cards' "
                      "windows; scope them with a class the windows do not hold, or add them to ALLOWED_REACH with "
                      "the reason:\n  " + "\n  ".join(hits))


def test_the_allowed_reaches_still_exist():
    selectors = {r.selector for _, r in _rules(["layouts/basketball.css"])}
    assert set(ALLOWED_REACH) <= selectors, "ALLOWED_REACH names a rule that is gone: remove it"


def _own_properties(layout: str) -> set[str]:
    """Every custom property the layout sets on its own element (in any theme)."""
    out: set[str] = set()
    for r in cc.load_rules(CSS / "layouts" / f"{layout}.css"):
        comps = cc.split_ws(r.selector)
        if len(comps) == 1 and r.selector.startswith(f'[data-layout="{layout}"]') and "data-league-colour" not in r.selector:
            out |= set(r.decls)
    return out


def _defaults_on_every_layout_element() -> set[str]:
    """What tokens.css declares on `[data-layout]`, i.e. on a window's own element, whatever its layout."""
    out: set[str] = set()
    for r in cc.load_rules(CSS / "tokens.css"):
        if r.selector == "[data-layout]" or r.selector.startswith("[data-layout]:not(") or r.selector.startswith("[data-layout][data-theme"):
            out |= set(r.decls)
    return out


@pytest.mark.parametrize("window", LAYOUTS)
def test_a_window_resets_every_property_the_landing_look_sets(window):
    """Custom properties inherit. If the page's layout sets one that the window's layout (and tokens.css's
    `[data-layout]` block) does not, the window would inherit the PAGE's value instead of its own default."""
    leaking = _own_properties(LANDING_LAYOUT) - _own_properties(window) - _defaults_on_every_layout_element()
    leaking = {p for p in leaking if not p.startswith("--st-league-")}
    assert not leaking, (f"{LANDING_LAYOUT}.css sets {sorted(leaking)} but {window}.css does not, so a {window} "
                         f"window inside a {LANDING_LAYOUT} page would inherit them: set them in {window}.css too")


# ---------------------------------------------------------------------------- static: nothing leaks out

@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_rule_of_a_layout_file_is_scoped_to_its_own_layout(layout):
    """All six layout files are loaded on the landing page (order does not matter because of this)."""
    bad = [r.selector for r in cc.load_rules(CSS / "layouts" / f"{layout}.css")
           if f'[data-layout="{layout}"]' not in r.selector]
    assert not bad, f"layouts/{layout}.css has rules that are not scoped to [data-layout=\"{layout}\"]: {bad}"


def test_the_sport_card_rules_name_no_layout():
    css = (CSS / "parts-shell.css").read_text(encoding="utf-8")
    start = css.rindex("/*", 0, css.index("sport card (landing page)"))
    section = re.sub(r"/\*.*?\*/", "", css[start:], flags=re.S)
    assert ".st-sport-card" in section
    assert "data-layout" not in section, "the sport card is one part for every look: no per-layout rule in it"


# ---------------------------------------------------------------------------- measured: what the extra looks cost

def _woff2_bytes(family: str) -> dict[str, int]:
    css = (CSS / "fonts.css").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"@font-face\s*{([^}]*)}", css):
        body = m.group(1)
        fam = re.search(r'font-family:\s*"([^"]+)"', body).group(1)
        url = re.search(r'url\("([^"]+\.woff2)"\)', body).group(1)
        if fam == family:
            out[url] = (CSS / url).resolve().stat().st_size
    return out


def _fonts_of(layout: str) -> set[str]:
    """The font files a layout's two families need (all weights it declares), by path."""
    text = (CSS / "layouts" / f"{layout}.css").read_text(encoding="utf-8")
    families = []
    for prop in ("--st-font-display", "--st-font-body"):
        m = re.search(prop + r':\s*"([^"]+)"', text)
        families.append(m.group(1))
    files: dict[str, int] = {}
    for fam in families:
        files.update(_woff2_bytes(fam))
    return set(files)


def test_the_extra_looks_cost_what_the_plan_says():
    """Plan question 1: with the Curling window the page loads curling.css (14 KB) and the Curling fonts (about
    72 KB), and 'more as hockey and slo-pitch arrive'. Measured here so a change in either shows up."""
    size = {p: (CSS / p).stat().st_size for p in [f"layouts/{l}.css" for l in LAYOUTS]}
    page_fonts = _fonts_of(LANDING_LAYOUT)

    def font_bytes(layout):
        return sum((CSS / u).resolve().stat().st_size for u in _fonts_of(layout) - page_fonts)

    curling_css, curling_fonts = size["layouts/curling.css"], font_bytes("curling")
    assert 12_000 <= curling_css <= 16_000, f"curling.css is {curling_css} bytes; the plan says 14 KB"
    assert 68_000 <= curling_fonts <= 76_000, f"the Curling fonts are {curling_fonts} bytes; the plan says about 72 KB"

    others = [l for l in LAYOUTS if l != LANDING_LAYOUT]
    all_css = sum(size[f"layouts/{l}.css"] for l in others)
    all_fonts = sum((CSS / u).resolve().stat().st_size for u in set().union(*[_fonts_of(l) for l in others]) - page_fonts)
    # What the page would load if every look were on it (the plan's "more as hockey and slo-pitch arrive"):
    # a budget that stops a layout file or a font from growing unnoticed.
    assert all_css <= 80_000, f"the five other layout files are {all_css} bytes"
    assert all_fonts <= 340_000, f"the fonts of the five other looks are {all_fonts} bytes"
    print(f"\nextra cost of nested looks: curling {curling_css} B css + {curling_fonts} B fonts; "
          f"all five others {all_css} B css + {all_fonts} B fonts")


# ---------------------------------------------------------------------------- browser: the real thing

def _chromium() -> str | None:
    for pat in (os.environ.get("CHROMIUM_PATH", ""), "/opt/pw-browsers/chromium-*/chrome-linux/chrome"):
        for hit in sorted(glob.glob(pat)) if pat else []:
            if os.access(hit, os.X_OK):
                return hit
    return None


@pytest.fixture(scope="module")
def browser():
    pw_mod = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed")
    with pw_mod.sync_playwright() as pw:
        kw = {"args": ["--no-sandbox"]}
        exe = _chromium()
        if exe:
            kw["executable_path"] = exe
        try:
            b = pw.chromium.launch(**kw)
        except Exception as err:                                  # pragma: no cover - environment
            pytest.skip(f"Chromium is not available: {err}")
        yield b
        b.close()


def _page_html(page_layout: str | None, theme: str | None, body: str, width: int = 390) -> str:
    links = "".join(f'<link rel="stylesheet" href="{(CSS / p.format(page=page_layout or "basketball")).as_uri()}">'
                    for p in CSS_ORDER
                    # every look's file, after the page's own (the landing page's head does the same)
                    ) + "".join(f'<link rel="stylesheet" href="{(CSS / "layouts" / f"{l}.css").as_uri()}">'
                                for l in LAYOUTS if l != (page_layout or "basketball"))
    attrs = ""
    if page_layout:
        attrs += f' data-layout="{page_layout}"'
    if theme:
        attrs += f' data-theme="{theme}"'
    return (f'<!doctype html><html{attrs}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'{links}<style>body{{margin:0;width:{width}px}}</style></head>'
            f'<body class="{"st-page" if page_layout else ""}">{body}</body></html>')


def _open(page, html: str, folder: Path, name: str) -> None:
    """Load html from a file: a page set with set_content may not load file:// stylesheets or scripts."""
    path = folder / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    page.goto(path.as_uri(), wait_until="load")


_STYLES_JS = """
(sel) => {
  const root = document.querySelector(sel);
  const out = [];
  for (const el of [root, ...root.querySelectorAll('*')]) {
    const cs = getComputedStyle(el), rec = {};
    for (const p of cs) rec[p] = cs.getPropertyValue(p);
    out.push([el.tagName.toLowerCase() + '.' + (el.getAttribute('class') || ''), rec]);
  }
  return out;
}
"""
# Values that follow the element's box, not its look.
_BOX_ONLY = {"width", "height", "inline-size", "block-size", "perspective-origin", "transform-origin",
             "min-width", "min-height", "min-inline-size", "min-block-size",
             "top", "right", "bottom", "left", "inset-block-start", "inset-block-end", "inset-inline-start",
             "inset-inline-end"}      # where an absolutely placed element (the hidden caption) landed


def _compare(nested, plain, label):
    assert len(nested) == len(plain), f"{label}: the windows have a different number of elements"
    diffs = []
    for (name, a), (name2, b) in zip(nested, plain):
        assert name == name2
        for prop in a:
            if prop in _BOX_ONLY:
                continue
            if a[prop] != b.get(prop):
                diffs.append(f"{name}  {prop}: {a[prop]!r} inside the page, {b.get(prop)!r} on its own")
    assert not diffs, f"{label}: {len(diffs)} computed styles differ, e.g.\n  " + "\n  ".join(diffs[:8])


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_a_window_looks_the_same_inside_the_landing_page_as_on_its_own(browser, theme, tmp_path):
    """The same window markup (the Basketball one, then the Curling one) is laid out inside the landing page's
    look, with all six layout files loaded, and on a plain page; every computed style of every element in it must
    be identical. A leak of a rule, or of an inherited custom property, shows up as a difference."""
    cards = _sport_card_html(theme)
    wins = _windows(cards)
    ctx = browser.new_context(viewport={"width": 390, "height": 900}, color_scheme="light")
    try:
        page = ctx.new_page()
        _open(page, _page_html(LANDING_LAYOUT, theme, f'<main class="st-main">{cards}</main>'), tmp_path, "nested")
        widths = page.evaluate("""() => [...document.querySelectorAll('.st-sport-card__window')].map((w, i) => {
            w.id = 'w' + i; return w.closest('.st-sport-card').getBoundingClientRect().width; })""")
        alone = ctx.new_page()
        for i, win in enumerate(wins):
            _open(alone, _page_html(None, None, f'<article class="st-card st-sport-card" style="width:{widths[i]}px">{win}</article>', width=int(widths[i])),
                  tmp_path, f"alone{i}")
            alone.evaluate("() => { document.querySelector('.st-sport-card__window').id = 'w'; }")
            _compare(page.evaluate(_STYLES_JS, f"#w{i}"), alone.evaluate(_STYLES_JS, "#w"),
                     f"{LANDING_LAYOUT}/{theme}/window {i + 1}")
    finally:
        ctx.close()


def test_without_javascript_a_window_follows_the_phone(browser, tmp_path):
    """No data-theme anywhere (JavaScript off): the page and its windows each follow prefers-color-scheme."""
    seen = {}
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 390, "height": 900}, color_scheme=scheme)
        try:
            page = ctx.new_page()
            cards = re.sub(r' data-theme="[^"]*"', "", _sport_card_html())
            _open(page, _page_html(LANDING_LAYOUT, None, f'<main class="st-main">{cards}</main>'), tmp_path, scheme)
            seen[scheme] = page.evaluate("""() => ({
                page: getComputedStyle(document.body).backgroundColor,
                windows: [...document.querySelectorAll('.st-sport-card__window')].map(w => getComputedStyle(w).backgroundColor)})""")
        finally:
            ctx.close()
    assert seen["light"]["page"] != seen["dark"]["page"]
    for i in range(2):
        assert seen["light"]["windows"][i] != seen["dark"]["windows"][i], f"window {i + 1} ignores the phone's setting"


def test_the_theme_button_switches_the_windows_too(browser, tmp_path):
    """assets/js/site.js copies the page's data-theme onto every window when the button is pressed (and removes it
    again when the page has none)."""
    toggle = '<header><button class="st-theme-toggle" type="button" hidden></button></header>'
    cards = re.sub(r' data-theme="[^"]*"', "", _sport_card_html())
    html = _page_html(LANDING_LAYOUT, None, toggle + f'<main class="st-main">{cards}</main>')
    html = html.replace("</body>", f'<script src="{(ROOT / "assets/js/site.js").as_uri()}"></script></body>')
    ctx = browser.new_context(viewport={"width": 390, "height": 900}, color_scheme="light")
    try:
        page = ctx.new_page()
        _open(page, html, tmp_path, "button")
        probe = """() => ({root: document.documentElement.getAttribute('data-theme'),
            windows: [...document.querySelectorAll('.st-sport-card__window')].map(w => w.getAttribute('data-theme')),
            bg: [...document.querySelectorAll('.st-sport-card__window')].map(w => getComputedStyle(w).backgroundColor)})"""
        before = page.evaluate(probe)
        assert before["root"] is None and before["windows"] == [None, None]
        page.click(".st-theme-toggle")
        dark = page.evaluate(probe)
        assert dark["root"] == "dark" and dark["windows"] == ["dark", "dark"]
        assert dark["bg"][0] != before["bg"][0] and dark["bg"][1] != before["bg"][1], "the windows did not turn dark"
        page.click(".st-theme-toggle")
        light = page.evaluate(probe)
        assert light["root"] == "light" and light["windows"] == ["light", "light"]
        assert light["bg"] == before["bg"]
    finally:
        ctx.close()
