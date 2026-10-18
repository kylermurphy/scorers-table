"""Tests for assets/css/fallbacks.css (browsers without color-mix()) and its generator
scripts/build_css_fallbacks.py: freshness, coverage of every color-mix() in the parts, the file
being generated-only, specificity, the pair run in fallback mode, and (with Playwright) a
simulated old browser. Run with `python -m pytest` from the repo root."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_css_fallbacks as gen  # noqa: E402
from scripts import check_contrast as cc  # noqa: E402
from tests.parity.site import skip_unless_ci  # noqa: E402

FALLBACKS = ROOT / "assets" / "css" / "fallbacks.css"


# ------------------------------------------------------------------ freshness and coverage

def test_committed_file_is_what_the_generator_writes():
    assert FALLBACKS.read_text(encoding="utf-8") == gen.render(), \
        "assets/css/fallbacks.css is stale: run python scripts/build_css_fallbacks.py"


def test_every_color_mix_in_the_parts_has_an_override():
    assert gen.coverage_problems() == []


def test_a_new_color_mix_in_a_part_is_reported(tmp_path):
    css = tmp_path / "css"
    shutil.copytree(ROOT / "assets" / "css", css)
    p = css / "parts-data.css"
    p.write_text(p.read_text(encoding="utf-8") + "\n.st-new { background: color-mix(in oklab, var(--st-link) 10%, transparent); }\n",
                 encoding="utf-8")
    probs = gen.coverage_problems(css)
    assert len(probs) == 1 and ".st-new" in probs[0] and "no entry in OVERRIDES" in probs[0]


def test_a_changed_color_mix_makes_its_override_stale(tmp_path):
    css = tmp_path / "css"
    shutil.copytree(ROOT / "assets" / "css", css)
    p = css / "parts-data.css"
    p.write_text(p.read_text(encoding="utf-8").replace("var(--st-panel-text) 22%", "var(--st-panel-text) 30%"), encoding="utf-8")
    probs = gen.coverage_problems(css)
    assert any("no entry in OVERRIDES" in x for x in probs) and any("no such declaration" in x for x in probs)


def test_stale_file_fails_the_check(tmp_path, monkeypatch):
    stale = tmp_path / "fallbacks.css"
    stale.write_text(FALLBACKS.read_text(encoding="utf-8").replace("--st-league-dim: #022274", "--st-league-dim: #022275"),
                     encoding="utf-8")
    monkeypatch.setattr(gen, "OUT_PATH", stale)
    monkeypatch.setattr(cc, "FALLBACKS_PATH", stale)
    assert any("out of date" in p for p in gen.problems())
    rep = cc.check_fallbacks()
    assert not rep.ok and any("out of date" in e for e in rep.errors)
    assert cc.run_checks(layouts=None, with_league=False).ok is False


# ------------------------------------------------------------------ the file is generated-only

def _rules():
    return list(gen.iter_declarations(FALLBACKS.read_text(encoding="utf-8")))


def test_file_is_one_supports_block_with_the_exact_condition():
    text = cc.strip_comments(FALLBACKS.read_text(encoding="utf-8")).strip()
    assert text.startswith("@supports " + gen.SUPPORTS_COND + " {") and text.endswith("}")
    assert text.count("@supports") == 1
    assert cc.NO_COLOR_MIX == gen.SUPPORTS_COND


def test_file_holds_literals_only():
    """No color-mix() and no var() (except the team's own hex), no role read: every value is a literal."""
    allowed_var = "var(--st-team-hex)"
    for media, sel, prop, value in _rules():
        assert "color-mix(" not in value, (sel, prop)
        if "var(" in value:
            assert (sel, prop, value) == (".st-team--custom", "--st-team", allowed_var)
        if prop.startswith("--st-") and prop != "--st-team":
            # a colour, a gradient of literals, or `none`
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?|transparent|none|"
                                r"(repeating-)?linear-gradient\([^()]*(\([^()]*\)[^()]*)*\)|rgba?\([^)]*\)|#[0-9A-Fa-f]{3,8}", value), (sel, prop, value)


def test_only_known_non_role_properties_outside_the_roles():
    """Besides the --st-* colour properties the file sets only what OVERRIDES lists."""
    known = {o.prop for o in gen.OVERRIDES}
    for media, sel, prop, value in _rules():
        assert prop.startswith("--st-") or prop in known, (sel, prop)


def test_header_says_generated_and_how_to_regenerate():
    head = FALLBACKS.read_text(encoding="utf-8")[:1500]
    assert "GENERATED" in head and "python scripts/build_css_fallbacks.py" in head and "LAST" in head


def test_every_layout_has_all_three_theme_blocks_and_custom_selectors():
    text = FALLBACKS.read_text(encoding="utf-8")
    for lid in cc.layout_ids():
        for sel in (gen.theme_prefix(lid, "light"), gen.theme_prefix(lid, "light", True),
                    gen.theme_prefix(lid, "os-dark"), gen.theme_prefix(lid, "os-dark", True),
                    gen.theme_prefix(lid, "dark"), gen.theme_prefix(lid, "dark", True)):
            assert sel + ",\n" in text or sel + " {" in text, sel
    assert text.count("@media (prefers-color-scheme: dark)") >= len(cc.layout_ids())


def test_every_colour_role_of_every_layout_is_written_in_every_block():
    rules = {}
    for media, sel, prop, value in _rules():
        for one in cc.split_top(sel):
            rules.setdefault((media, one.strip()), set()).add(prop)
    for lid in cc.layout_ids():
        roles = {"--st-" + r for r in cc.COLOUR_ROLES} | {"--st-" + h for h in cc.LEAGUE_HELPERS}
        for variant, media in (("light", None), ("os-dark", "@media (prefers-color-scheme: dark)"), ("dark", None)):
            for custom in (False, True):
                got = rules[(media, gen.theme_prefix(lid, variant, custom))]
                assert roles <= got, (lid, variant, custom, sorted(roles - got))


# ------------------------------------------------------------------ specificity

def specificity(selector: str) -> tuple:
    """(ids, classes+attributes+pseudo-classes, types+pseudo-elements) of one selector (no commas at top level)."""
    s = selector
    a = b = c = 0
    # functional pseudo-classes: :is/:not take their most specific argument, :where counts nothing
    while True:
        m = re.search(r":(is|not|where)\(", s)
        if not m:
            break
        end = cc._match_paren(s, m.end() - 1)
        inner = s[m.end():end]
        args = cc.split_top(inner)
        if m.group(1) != "where":
            best = max(specificity(x.strip()) for x in args)
            a, b, c = a + best[0], b + best[1], c + best[2]
        s = s[:m.start()] + " " + s[end + 1:]
    a += len(re.findall(r"#[\w-]+", s))
    s2 = re.sub(r"\[[^\]]*\]", lambda m: "." + "x", s)
    b += len(re.findall(r"\.[\w-]+", s2)) + len(re.findall(r"(?<!:):[\w-]+", s2))
    s3 = re.sub(r"\.[\w-]+|(?<!:):[\w-]+|#[\w-]+", " ", s2)
    c += len(re.findall(r"::[\w-]+", s3))
    s3 = re.sub(r"::[\w-]+", " ", s3)
    c += len([t for t in re.split(r"[\s>+~]+", s3) if re.fullmatch(r"[a-zA-Z][\w-]*", t)])
    return a, b, c


def test_specificity_helper():
    assert specificity('[data-layout="a"] .x tbody td.y') == (0, 3, 2)
    assert specificity(':is([data-layout="a"], [data-layout="b"]) .st-final :is(thead th, tbody td).is-blank') == (0, 3, 2)
    assert specificity('[data-layout="a"]:not([data-theme="light"])') == (0, 2, 0)
    assert specificity('[data-layout="hockey"] .st-final::before') == (0, 2, 1)


def test_override_selectors_are_at_least_as_specific_as_the_part_rules():
    layouts = cc.layout_ids()
    text = FALLBACKS.read_text(encoding="utf-8")
    for o in gen.OVERRIDES:
        if o.fallback:
            assert o.selector + " {" in text and specificity(o.selector) >= (0, 1, 0)
            continue
        part = specificity(o.selector)
        ids, rest = gen.layouts_and_rest(o.selector, layouts)
        assert ids
        for lid in ids:
            for variant in ("light", "os-dark", "dark"):
                ours = gen.theme_prefix(lid, variant) + rest
                assert specificity(ours) >= part, (o.selector, ours)
            assert gen.theme_prefix(lid, "light") + rest + " {" in text, (lid, o.selector)


# ------------------------------------------------------------------ the checker's fallback mode

def test_modern_cascade_ignores_the_supports_block_and_fallback_mode_applies_it():
    modern = cc.Palette("basketball", "light")
    old = cc.Palette("basketball", "light", fallback=True)
    assert "color-mix(" in modern.decls["--st-league-dim"]
    assert old.decls["--st-league-dim"] == "#022274"
    assert cc.to_hex(modern.paint("league-dim")) == cc.to_hex(old.paint("league-dim"))


def test_fallback_palette_equals_the_modern_palette_at_the_default_colours():
    """What an old browser paints is what a new browser paints with no league colour (to 1/255)."""
    for lid in cc.layout_ids():
        for theme in cc.THEMES:
            new, old = cc.Palette(lid, theme), cc.Palette(lid, theme, fallback=True)
            for role in list(cc.COLOUR_ROLES) + list(cc.LEAGUE_HELPERS):
                a, b = new.paint(role), old.paint(role)
                if isinstance(a, cc.Gradient):
                    assert len(a.stops) == len(b.stops)
                    pairs = [(x[0], y[0]) for x, y in zip(a.stops, b.stops)]
                elif a is None:
                    assert b is None
                    continue
                else:
                    pairs = [(a, b)]
                for x, y in pairs:
                    assert max(abs(p - q) for p, q in zip(cc.rgb8(x), cc.rgb8(y))) <= 1, (lid, theme, role)
                    assert abs(x.a - y.a) < 0.01


def test_custom_attribute_gets_the_default_look_in_fallback_mode():
    for lid in cc.layout_ids():
        for theme in cc.THEMES:
            plain = cc.Palette(lid, theme, fallback=True)
            custom = cc.Palette(lid, theme, custom=True, fallback=True)
            for role in list(cc.COLOUR_ROLES) + list(cc.LEAGUE_HELPERS):
                assert plain.text_of(role) == custom.text_of(role), (lid, theme, role)


def test_color_mix_still_reachable_is_an_error():
    text = FALLBACKS.read_text(encoding="utf-8")
    broken = re.sub(r"\n\s*--st-league-dim: #[0-9A-Fa-f]+;", "", text)
    assert broken != text
    rules = [cc.load_rules(cc.CSS_DIR / "tokens.css"), cc.load_rules(cc.LAYOUT_DIR / "basketball.css"),
             cc.parse_css(broken, "fallbacks.css")]
    decls = cc.cascade_rules(rules, "basketball", "light", fallback=True)
    pal = cc.Palette("basketball", "light", decls=decls, fallback=True)
    msgs = cc.color_mix_reachable(pal)
    assert any("--st-league-dim" in m and "color-mix" in m for m in msgs)
    # and the committed file leaves nothing reachable
    for lid in cc.layout_ids():
        for custom in (False, True):
            for theme in cc.THEMES:
                assert cc.color_mix_reachable(cc.Palette(lid, theme, custom=custom, fallback=True)) == []


def test_fallback_pair_run_passes_everywhere():
    rep = cc.check_fallbacks()
    assert rep.errors == []
    assert rep.failures == []
    assert rep.n_pairs > 1500
    assert len(rep.results) == len(cc.layout_ids()) * 2 * 2


def test_default_run_includes_the_fallback_run():
    rep = cc.run_checks(layouts=["classic"], with_league=False)
    assert rep.fallback is not None and rep.fallback.layouts == ["classic"]
    md = cc.render_markdown(rep)
    assert "## Browsers without color-mix()" in md and "Browsers without `color-mix()`:" in md


def test_a_failing_fallback_pair_fails_the_run(monkeypatch):
    """Make the fallback's text colour as light as its background: the run must fail."""
    text = FALLBACKS.read_text(encoding="utf-8")
    bad = re.sub(r"(--st-text: )#[0-9A-Fa-f]{6}", r"\1#F4F6FB", text, count=1)
    assert bad != text
    orig = cc.load_rules

    def fake(path):
        return cc.parse_css(bad, "fallbacks.css") if str(path).endswith("fallbacks.css") else orig(path)

    monkeypatch.setattr(cc, "load_rules", fake)
    rep = cc.check_fallbacks(freshness=False)
    assert rep.failures and not rep.ok


# ------------------------------------------------------------------ wiring

def test_load_order_ends_with_fallbacks():
    src = (ROOT / "scripts" / "build_design_system.py").read_text(encoding="utf-8")
    m = re.search(r"CSS_ORDER = \[(.*?)\n\]", src, re.S)
    assert m and m.group(1).rstrip().rstrip(",").endswith('"fallbacks.css"')


def test_team_custom_falls_back_to_the_plain_hex():
    rules = [r for r in cc.load_rules(FALLBACKS) if r.selector == ".st-team--custom"]
    assert rules and rules[-1].decls["--st-team"] == "var(--st-team-hex)"


# ------------------------------------------------------------------ simulated old browser (Chromium)

def _playwright_python():
    """A Python that can import Playwright: this one, or $ST_PLAYWRIGHT_PYTHON."""
    try:
        import playwright  # noqa: F401
        return sys.executable
    except Exception:
        pass
    alt = os.environ.get("ST_PLAYWRIGHT_PYTHON")
    return alt if alt and os.access(alt, os.X_OK) else None


def test_simulated_old_browser_looks_like_the_modern_one():
    """color-mix( is renamed to an unknown function outside fallbacks.css and the @supports block is
    forced on: in the design-system page the computed colours of every element must match the real
    render (league-colour frames and a custom team colour's dark lift excepted), and the OS-dark path
    must give the same roles. tests/old_browser_sim.py prints the details.

    Needs Playwright and Chromium (requirements-ci.txt, playwright install chromium): skipped without them on a
    computer, a failure in CI (the `CI` variable)."""
    python = _playwright_python()
    if python is None:
        skip_unless_ci("Playwright is not installed (pip install -r requirements-ci.txt, then playwright install "
                       "chromium; or set ST_PLAYWRIGHT_PYTHON); CI always runs it")
    proc = subprocess.run([python, str(ROOT / "tests" / "old_browser_sim.py")],
                          capture_output=True, text=True, timeout=600)
    if "Executable doesn't exist" in proc.stderr or "BrowserType.launch" in proc.stderr:
        skip_unless_ci("Chromium is not available (playwright install chromium); CI always runs it")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
