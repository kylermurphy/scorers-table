"""Tests for scripts/check_contrast.py: the colour maths, the cascade (specificity, source order,
the OS-dark and data-theme blocks, the custom-colour blocks), the pair checks, the league colour
messages and the token lint. Run with `python -m pytest` from the repo root.
Reference colours marked (Chromium) were read back from Chromium 141 with a canvas."""
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_contrast as cc  # noqa: E402
from scripts.check_contrast import (  # noqa: E402
    BLACK, WHITE, Colour, Gradient, Pair, Palette, cascade_rules, check_league_colour, composite,
    contrast_ratio, dark_parity_errors, evaluate_pair, lint_tokens, parse_colour, parse_css, parse_paint,
    rgb8, substitute, to_hex,
)


def px(expr, base=WHITE):
    """8-bit rgb a browser paints for a CSS colour expression over `base`."""
    return rgb8(composite(parse_colour(expr), base))


def close(got, want, tol=1):
    return all(abs(a - b) <= tol for a, b in zip(got, want))


# --------------------------------------------------------------------- contrast maths

def test_black_on_white_is_21():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio(BLACK, WHITE) == pytest.approx(21.0)


def test_same_colour_is_1():
    assert contrast_ratio("#336699", "#336699") == pytest.approx(1.0)


def test_777_on_white_is_448():
    r = contrast_ratio("#777777", "#ffffff")
    assert round(r, 2) == 4.48
    assert r < 4.5          # the classic "almost AA" grey


def test_ratio_is_symmetric():
    assert contrast_ratio("#1D3A6E", "#F4F6FB") == pytest.approx(contrast_ratio("#F4F6FB", "#1D3A6E"))


def test_hex_forms():
    assert parse_colour("#fff") == WHITE
    assert parse_colour("#FFFFFF") == WHITE
    c = parse_colour("#FFFFFF1F")
    assert c.a == pytest.approx(31 / 255)
    assert to_hex(c) == "#FFFFFF1F"
    assert parse_colour("#f008") == Colour(1.0, 0.0, 0.0, 0x88 / 255)


def test_rgb_functions():
    assert rgb8(parse_colour("rgb(244, 236, 214)")) == (244, 236, 214)
    c = parse_colour("rgba(244, 236, 214, 0.045)")
    assert c.a == pytest.approx(0.045)
    assert parse_colour("rgb(0 0 0 / 50%)").a == pytest.approx(0.5)


def test_bad_colours_raise():
    for bad in ("#12", "banana", "color-mix(in oklch, red, blue)", "rgb(1,2)"):
        with pytest.raises(cc.ColourError):
            parse_colour(bad)


# ---------------------------------------------------------------- alpha compositing

def test_alpha_over_black_and_white():
    half = Colour(1, 1, 1, 0.5)
    assert rgb8(composite(half, BLACK)) == (128, 128, 128)
    assert rgb8(composite(Colour(0, 0, 0, 0.5), WHITE)) == (128, 128, 128)
    assert composite(Colour(0.2, 0.4, 0.6, 1.0), WHITE) == Colour(0.2, 0.4, 0.6, 1.0)
    assert composite(cc.TRANSPARENT, Colour(0.3, 0.3, 0.3)) == Colour(0.3, 0.3, 0.3)


def test_translucent_foreground_is_measured_composited():
    # #FFFFFF73 on blue: measured as the blended colour, not as pure white
    pal = Palette.from_decls({"--st-ring": "#FFFFFF73", "--st-hdr": "#032F98"})
    res = evaluate_pair(pal, Pair("ring", ("hdr",), "ui", "ring/hdr"))
    assert res.fg_hex == to_hex(composite(parse_colour("#FFFFFF73"), parse_colour("#032F98")))
    assert res.ratio == pytest.approx(contrast_ratio(res.fg_hex, "#032F98"))
    assert res.ratio < contrast_ratio("#FFFFFF", "#032F98")


def test_translucent_row_is_composited_over_panel():
    pal = Palette.from_decls({"--st-t": "#FFFFFF", "--st-panel": "#032F98", "--st-row": "#FFFFFF1F"})
    on_row = evaluate_pair(pal, Pair("t", ("panel", "row"), "text", "t/row"))
    on_panel = evaluate_pair(pal, Pair("t", ("panel",), "text", "t/panel"))
    assert on_row.ratio < on_panel.ratio        # the row lightens the blue
    assert on_row.bg_hex == to_hex(composite(parse_colour("#FFFFFF1F"), parse_colour("#032F98")))


# ---------------------------------------------------- oklab colour-mix (Chromium refs)

def test_oklab_mix_against_chromium():
    assert close(px("color-mix(in oklab, #1D4E89, white 62%)"), (166, 186, 211))      # Chromium
    assert close(px("color-mix(in oklab, #C98A12, black 30%)"), (124, 83, 7))         # Chromium
    assert close(px("color-mix(in oklab, #032F98, white)"), (124, 153, 208))          # Chromium
    assert close(px("color-mix(in oklab, #ff0000 25%, #0000ff)"), (81, 71, 210))      # Chromium
    assert close(px("color-mix(in oklab, #FF5C66, black 22%)"), (183, 64, 71))        # Chromium


def test_nested_mix_against_chromium():
    expr = "color-mix(in oklab, color-mix(in oklab, #0A1022, #032F98 70%), white 10%)"
    assert close(px(expr), (30, 60, 129))                                             # Chromium


def test_srgb_mix_and_out_of_gamut_clip():
    assert close(px("color-mix(in srgb, #ff0000, #0000ff)"), (128, 0, 128))           # Chromium
    assert close(px("color-mix(in oklab, #00ff00, white 50%)"), (173, 255, 166))      # Chromium (clipped)
    assert close(px("color-mix(in oklab, #0000ff, #00ff00 80%)"), (0, 222, 128))      # Chromium


def test_mix_percentages():
    # both given and summing to less than 100 -> alpha scales (Chromium: over white / over black)
    c = parse_colour("color-mix(in oklab, #ffffff 40%, #000000 20%)")
    assert c.a == pytest.approx(0.6)
    assert close(px("color-mix(in oklab, #ffffff 40%, #000000 20%)"), (191, 191, 191))                 # Chromium
    assert close(px("color-mix(in oklab, #ffffff 40%, #000000 20%)", BLACK), (89, 89, 89))              # Chromium
    # one given, the other the rest; none given = half
    a = parse_colour("color-mix(in oklab, #123456 30%, #abcdef)")
    b = parse_colour("color-mix(in oklab, #123456 30%, #abcdef 70%)")
    assert a == b
    assert parse_colour("color-mix(in oklab, #000, #fff)") == parse_colour("color-mix(in oklab, #000 50%, #fff 50%)")
    # mixing with transparent keeps the colour and halves the alpha
    t = parse_colour("color-mix(in oklab, #1D3A6E, transparent 50%)")
    assert t.a == pytest.approx(0.5)
    assert close(px("color-mix(in oklab, #1D3A6E, transparent 50%)", BLACK), (15, 29, 55))             # Chromium


def test_mix_endpoints():
    assert rgb8(parse_colour("color-mix(in oklab, #336699 100%, #ffffff 0%)")) == (51, 102, 153)
    assert rgb8(parse_colour("color-mix(in oklab, #336699, white 0%)")) == (51, 102, 153)


# ------------------------------------------------------------------- var() and cascade

def test_substitute_var_and_fallbacks():
    decls = {"--a": "#112233", "--b": "var(--a)", "--pct": "30%"}
    assert substitute("var(--b)", decls) == "#112233"
    assert substitute("var(--missing, #abcdef)", decls) == "#abcdef"
    assert substitute("var(--missing, var(--a))", decls) == "#112233"
    assert substitute("color-mix(in oklab, var(--a), black var(--pct))", decls) == "color-mix(in oklab, #112233, black 30%)"
    assert substitute("var(--missing, color-mix(in oklab, red 10%, blue))", decls) == "color-mix(in oklab, red 10%, blue)"
    with pytest.raises(cc.UndefinedVar):
        substitute("var(--nope)", decls)
    # a custom property that cannot be resolved is invalid, so the fallback is used
    assert substitute("var(--c, #fff)", {"--c": "var(--nope)"}) == "#fff"
    # cycles do not hang
    with pytest.raises(cc.UndefinedVar):
        substitute("var(--x)", {"--x": "var(--y)", "--y": "var(--x)"})


SYNTHETIC_TOKENS = """
/* tokens */
[data-layout] {
  --st-dim: 30%;
  --st-league-base: var(--st-league-color);
  --st-league-dim: color-mix(in oklab, var(--st-league-base), black var(--st-dim));
}
@media (prefers-color-scheme: dark) {
  [data-layout]:not([data-theme="light"]) { --st-league-base: var(--st-league-color-dark, var(--st-league-color)); }
}
[data-layout][data-theme="dark"] { --st-league-base: var(--st-league-color-dark, var(--st-league-color)); }
"""

SYNTHETIC_LAYOUT = """
[data-layout="demo"] {
  --st-league-color: #1D4E89;
  --st-dim: 50%;
  --st-surface: #FFFFFF;
  --st-link: var(--st-league-base);
  --st-panel: var(--st-league-dim);
}
@media (prefers-color-scheme: dark) {
  [data-layout="demo"]:not([data-theme="light"]) { --st-surface: #101820; --st-league-color-dark: #A6BAD3; }
}
[data-layout="demo"][data-theme="dark"] { --st-surface: #101820; --st-league-color-dark: #A6BAD3; }
"""


def demo(theme, prefers_dark=False, overrides=None):
    rules = [parse_css(SYNTHETIC_TOKENS, "tokens.css"), parse_css(SYNTHETIC_LAYOUT, "demo.css")]
    return cascade_rules(rules, "demo", theme, prefers_dark, overrides)


def test_cascade_layout_beats_tokens_and_dark_beats_layout():
    light = demo("light")
    assert light["--st-dim"] == "50%"                    # layout [data-layout="demo"] after tokens' [data-layout]
    assert light["--st-surface"] == "#FFFFFF"
    dark = demo("dark")
    assert dark["--st-surface"] == "#101820"
    assert substitute(dark["--st-link"], dark) == "#A6BAD3"      # dark base follows color-dark
    assert substitute(light["--st-link"], light) == "#1D4E89"
    # derived helper follows the theme because it reads --st-league-base on the same element
    assert rgb8(parse_colour(substitute(dark["--st-panel"], dark))) != rgb8(parse_colour(substitute(light["--st-panel"], light)))


def test_cascade_os_dark_equals_data_theme_dark():
    assert demo(None, prefers_dark=True) == demo("dark")
    assert demo(None, prefers_dark=False) == demo("light")
    # explicit light beats the OS preference
    assert demo("light", prefers_dark=True)["--st-surface"] == "#FFFFFF"


def test_inline_override_wins():
    d = demo("dark", overrides={"--st-league-color": "#000000", "--st-league-color-dark": "#FFFFFF"})
    assert substitute(d["--st-link"], d) == "#FFFFFF"
    d = demo("light", overrides={"--st-league-color": "#C98A12"})
    assert substitute(d["--st-link"], d) == "#C98A12"


def test_pct_knob_read_through_var():
    d = demo("light")
    dim = parse_colour(substitute(d["--st-panel"], d))
    assert rgb8(dim) == rgb8(parse_colour("color-mix(in oklab, #1D4E89, black 50%)"))


def test_selector_matching():
    attrs = {"data-layout": "demo", "data-theme": "dark"}
    assert cc.match_selector('[data-layout="demo"]', attrs) == (0, 1, 0)
    assert cc.match_selector('[data-layout]:not([data-theme="light"])', attrs) == (0, 2, 0)
    assert cc.match_selector('[data-layout="other"]', attrs) is None
    assert cc.match_selector('[data-layout="demo"] .st-header', attrs) is None
    assert cc.match_selector('[data-layout]:not([data-theme="light"])', {"data-layout": "demo", "data-theme": "light"}) is None
    # the custom-colour forms: a bare attribute selector, alone and with :not() / a value
    custom = {"data-layout": "demo", "data-theme": "dark", "data-league-colour": ""}
    assert cc.match_selector('[data-layout="demo"][data-league-colour]', custom) == (0, 2, 0)
    assert cc.match_selector('[data-layout="demo"][data-league-colour]', attrs) is None
    assert cc.match_selector('[data-layout="demo"][data-league-colour]:not([data-theme="light"])', custom) == (0, 3, 0)
    assert cc.match_selector('[data-layout="demo"][data-league-colour][data-theme="dark"]', custom) == (0, 3, 0)
    assert cc.match_selector('[data-layout="demo"][data-league-colour]:not([data-theme="light"])',
                             {**custom, "data-theme": "light"}) is None


# The cascade is a real one: every matching rule, sorted by (specificity, stylesheet, source order).

def cas(css, theme=None, prefers_dark=False, custom=False, overrides=None, layout="x"):
    return cascade_rules([parse_css(css, "t.css")], layout, theme, prefers_dark, overrides, custom)


def test_specificity_beats_source_order():
    css = """
    [data-layout="x"][data-theme="dark"] { --st-a: #111111; }
    [data-layout="x"] { --st-a: #222222; --st-c: #222222; }
    [data-layout] { --st-a: #333333; --st-b: #333333; }
    """
    assert cas(css, "dark")["--st-a"] == "#111111"     # two attributes beat one, though it comes first
    assert cas(css, "light")["--st-a"] == "#333333"    # equal specificity (one attribute each): the later rule wins
    assert cas(css, "light")["--st-b"] == "#333333"    # a property only the weak rule sets still applies
    assert cas(css, "light")["--st-c"] == "#222222"
    assert cas(css, "dark")["--st-b"] == "#333333"


def test_later_stylesheet_wins_at_equal_specificity():
    one = parse_css('[data-layout] { --st-a: #111111; }', "tokens.css")
    two = parse_css('[data-layout="x"] { --st-a: #222222; }', "x.css")
    assert cascade_rules([one, two], "x", None)["--st-a"] == "#222222"
    assert cascade_rules([two, one], "x", None)["--st-a"] == "#111111"


def test_os_dark_blocks_need_the_media_query_and_no_light_attribute():
    css = """
    [data-layout="x"] { --st-a: #111111; }
    @media (prefers-color-scheme: dark) { [data-layout="x"]:not([data-theme="light"]) { --st-a: #222222; } }
    [data-layout="x"][data-theme="dark"] { --st-a: #222222; }
    """
    assert cas(css, None, prefers_dark=False)["--st-a"] == "#111111"
    assert cas(css, None, prefers_dark=True)["--st-a"] == "#222222"
    assert cas(css, "dark", prefers_dark=False)["--st-a"] == "#222222"     # the button works without the OS setting
    assert cas(css, "light", prefers_dark=True)["--st-a"] == "#111111"     # explicit light beats the OS preference
    assert cas(css, "dark", prefers_dark=True)["--st-a"] == "#222222"


CUSTOM_CSS = """
[data-layout="x"] { --st-a: #111111; --st-b: #111111; --st-c: #111111; --st-d: #111111; }
@media (prefers-color-scheme: dark) {
  [data-layout="x"]:not([data-theme="light"]) { --st-a: #222222; --st-b: #222222; --st-c: #222222; }
}
[data-layout="x"][data-theme="dark"] { --st-a: #222222; --st-b: #222222; --st-c: #222222; }
[data-layout="x"][data-league-colour] { --st-a: #333333; --st-b: #333333; --st-d: var(--st-league-color); }
@media (prefers-color-scheme: dark) {
  [data-layout="x"][data-league-colour]:not([data-theme="light"]) { --st-a: #444444; --st-d: #444444; }
}
[data-layout="x"][data-league-colour][data-theme="dark"] { --st-a: #444444; --st-d: #444444; }
"""


def test_custom_blocks_apply_only_with_the_attribute():
    assert cas(CUSTOM_CSS, "light")["--st-a"] == "#111111"
    assert cas(CUSTOM_CSS, "light", custom=True)["--st-a"] == "#333333"
    assert cas(CUSTOM_CSS, "light", custom=True)["--st-c"] == "#111111"      # untouched roles keep the layout value
    assert cas(CUSTOM_CSS, "light", custom=True, overrides={"--st-league-color": "#abcdef"})["--st-d"] == "var(--st-league-color)"


def test_dark_custom_beats_light_custom_beats_normal_dark():
    d = cas(CUSTOM_CSS, "dark", custom=True)
    assert d["--st-a"] == "#444444"        # the dark custom block (3 attributes) wins
    # --st-b is not restated in the dark custom block: the light custom block, same specificity as the
    # normal dark block but later in the file, wins and the dark colour is lost. This is what the restate rule prevents.
    assert d["--st-b"] == "#333333"
    assert d["--st-c"] == "#222222"        # not touched by the custom blocks: the normal dark value
    assert cas(CUSTOM_CSS, "dark")["--st-b"] == "#222222"                    # without the attribute, dark is dark


def test_custom_os_dark_equals_custom_data_theme_dark():
    assert cas(CUSTOM_CSS, None, prefers_dark=True, custom=True) == cas(CUSTOM_CSS, "dark", custom=True)
    assert cas(CUSTOM_CSS, None, prefers_dark=False, custom=True) == cas(CUSTOM_CSS, "light", custom=True)
    assert cas(CUSTOM_CSS, "light", prefers_dark=True, custom=True)["--st-a"] == "#333333"


def test_palette_custom_mode_reads_the_custom_blocks(monkeypatch, tmp_path):
    css = tmp_path / "css"
    (css / "layouts").mkdir(parents=True)
    (css / "tokens.css").write_text(SYNTHETIC_TOKENS, encoding="utf-8")
    (css / "layouts" / "demo.css").write_text(SYNTHETIC_LAYOUT + """
[data-layout="demo"][data-league-colour] { --st-link: #FFFF00; }
@media (prefers-color-scheme: dark) { [data-layout="demo"][data-league-colour]:not([data-theme="light"]) { --st-link: #FFFF01; } }
[data-layout="demo"][data-league-colour][data-theme="dark"] { --st-link: #FFFF01; }
""", encoding="utf-8")
    monkeypatch.setattr(cc, "CSS_DIR", css)
    monkeypatch.setattr(cc, "LAYOUT_DIR", css / "layouts")
    assert cc.palette("demo", "light").text_of("link") == "#1D4E89"
    assert cc.palette("demo", "light", custom=True).text_of("link") == "#FFFF00"
    assert cc.palette("demo", "dark", custom=True).text_of("link") == "#FFFF01"
    # stage 4's check sees the pair that only breaks in custom mode (yellow links on white cards)
    pairs = cc.PAIRS
    monkeypatch.setattr(cc, "PAIRS", [p for p in pairs if p.id in ("link/surface",)])
    problems = check_league_colour("demo", "#1D4E89")
    assert [(p.theme, p.pair) for p in problems if p.theme == "light"] == [("light", "link/surface")]
    assert "league.yml colour #1D4E89" in problems[0].message


def test_inline_override_still_beats_the_custom_blocks():
    d = cas(CUSTOM_CSS, "light", custom=True, overrides={"--st-a": "#abcdef"})
    assert d["--st-a"] == "#abcdef"


# ------------------------------------------------------------------ dark block parity

def test_parity_ok_and_detects_differences():
    good = parse_css(SYNTHETIC_LAYOUT, "demo.css")
    assert dark_parity_errors(good, "demo.css") == []
    # whitespace differences are fine
    spaced = parse_css(SYNTHETIC_LAYOUT.replace("--st-surface: #101820; --st-league", "--st-surface:   #101820;\n --st-league"), "d")
    assert dark_parity_errors(spaced, "d") == []
    # a changed value
    bad = parse_css(SYNTHETIC_LAYOUT.replace("#101820; --st-league-color-dark: #A6BAD3; }\n", "#101821; --st-league-color-dark: #A6BAD3; }\n", 1), "d")
    errs = dark_parity_errors(bad, "d")
    assert len(errs) == 1 and "--st-surface" in errs[0] and "#101821" in errs[0]
    # an extra property in one block
    extra = parse_css(SYNTHETIC_LAYOUT.replace('[data-layout="demo"][data-theme="dark"] {', '[data-layout="demo"][data-theme="dark"] { --st-extra: red;'), "d")
    assert any("--st-extra" in e for e in dark_parity_errors(extra, "d"))
    # a block with no twin
    only_media = parse_css(SYNTHETIC_LAYOUT.split('[data-layout="demo"][data-theme="dark"]')[0], "d")
    assert any("exists only as" in e for e in dark_parity_errors(only_media, "d"))


CUSTOM_LAYOUT = SYNTHETIC_LAYOUT + """
[data-layout="demo"][data-league-colour] { --st-link: #123456; --st-panel: #654321; }
@media (prefers-color-scheme: dark) {
  [data-layout="demo"][data-league-colour]:not([data-theme="light"]) { --st-link: #ABCDEF; --st-panel: #FEDCBA; }
}
[data-layout="demo"][data-league-colour][data-theme="dark"] { --st-link: #ABCDEF; --st-panel: #FEDCBA; }
"""


def test_custom_blocks_parity_and_restate_rule():
    assert dark_parity_errors(parse_css(CUSTOM_LAYOUT, "c.css"), "c.css") == []
    # no custom blocks at all (today's state of the layouts): still fine
    assert dark_parity_errors(parse_css(SYNTHETIC_LAYOUT, "c.css"), "c.css") == []
    # media block and data-theme block of the custom pair must agree
    bad = CUSTOM_LAYOUT.replace("#ABCDEF; --st-panel: #FEDCBA; }\n}", "#ABCDEF; --st-panel: #FEDCBB; }\n}", 1)
    errs = dark_parity_errors(parse_css(bad, "c.css"), "c.css")
    assert len(errs) == 1 and "--st-panel" in errs[0] and "#FEDCBB" in errs[0]
    # the dark custom blocks must restate every property the light custom block sets
    short = CUSTOM_LAYOUT.replace(" --st-panel: #FEDCBA;", "")
    errs = dark_parity_errors(parse_css(short, "c.css"), "c.css")
    assert len(errs) == 1 and "do not restate --st-panel" in errs[0]
    # a light custom block with no dark twin is a failure too
    no_dark = SYNTHETIC_LAYOUT + '[data-layout="demo"][data-league-colour] { --st-link: #123456; }'
    errs = dark_parity_errors(parse_css(no_dark, "c.css"), "c.css")
    assert len(errs) == 1 and "no dark custom block" in errs[0]
    # extra properties in the dark blocks are allowed (only the light ones must be restated)
    extra = CUSTOM_LAYOUT.replace("--st-link: #ABCDEF;", "--st-link: #ABCDEF; --st-hot: red;", 1)
    assert dark_parity_errors(parse_css(extra, "c.css"), "c.css") != []     # ...but both dark blocks must still agree
    both = extra.replace('[data-theme="dark"] { --st-link: #ABCDEF;', '[data-theme="dark"] { --st-hot: red; --st-link: #ABCDEF;')
    assert dark_parity_errors(parse_css(both, "c.css"), "c.css") == []


def test_real_dark_blocks_match():
    assert cc.check_dark_parity() == []
    for lid in cc.layout_ids():
        assert cc.check_dark_equivalence(lid) == []


# ------------------------------------------------------------------------- gradients

def test_gradient_parse_keeps_stops():
    g = parse_paint("linear-gradient(180deg, #032F98 0%, color-mix(in oklab, #000, #fff) 58%, #EE6A2F 100%)")
    assert isinstance(g, Gradient)
    assert [p for _, p in g.stops] == [0.0, 0.58, 1.0]
    assert to_hex(g.stops[2][0]) == "#EE6A2F"


def test_gradient_worst_stop():
    pal = Palette.from_decls({
        "--st-hdr": "linear-gradient(180deg, #032F98 0%, #3A2A8C 74%, #EE6A2F 100%)",
        "--st-ink": "#FFFFFF",
    })
    res = evaluate_pair(pal, Pair("ink", ("hdr",), "text", "ink/hdr"))
    assert res.status == "FAIL"                       # white on orange is 3.1:1
    assert "stop 3 of 3" in res.worst and "#EE6A2F" in res.worst
    assert res.ratio == pytest.approx(contrast_ratio("#FFFFFF", "#EE6A2F"))
    # inside a zone that excludes the orange stop it passes
    cc.GRADIENT_TEXT_ZONE["test"] = 0.74
    try:
        res = evaluate_pair(pal, Pair("ink", ("hdr",), "text", "ink/hdr"))
    finally:
        del cc.GRADIENT_TEXT_ZONE["test"]
    assert res.status == "pass"


def test_gradient_stops_with_alpha_foreground():
    pal = Palette.from_decls({"--st-hdr": "linear-gradient(#000000, #FFFFFF)", "--st-line": "#FFFFFF80"})
    res = evaluate_pair(pal, Pair("line", ("hdr",), "ui", "line/hdr"))
    assert res.status == "FAIL" and res.ratio == pytest.approx(1.0)         # white half-alpha on white
    assert "stop 2 of 2" in res.worst


# ------------------------------------------------------------------ pair statuses

def test_undefined_and_transparent_roles_skip():
    pal = Palette.from_decls({"--st-a": "#000000", "--st-b": "#FFFFFF", "--st-t": "transparent"})
    assert evaluate_pair(pal, Pair("a", ("nope",), "text", "a/nope")).status == "skip"
    assert evaluate_pair(pal, Pair("a", ("nope",), "text", "a/nope")).missing == ("nope",)
    assert "transparent" in evaluate_pair(pal, Pair("t", ("b",), "ui", "t/b")).note
    assert evaluate_pair(pal, Pair("a", ("b",), "text", "a/b")).status == "pass"


def test_decor_never_fails():
    pal = Palette.from_decls({"--st-a": "#EEEEEE", "--st-b": "#FFFFFF"})
    assert evaluate_pair(pal, Pair("a", ("b",), "decor", "a/b")).status == "decor"
    assert evaluate_pair(pal, Pair("a", ("b",), "decor", "a/b", required=3.0)).status == "decor-miss"


def test_ui_and_large_thresholds():
    pal = Palette.from_decls({"--st-a": "#949494", "--st-b": "#FFFFFF"})   # 3.03:1
    assert evaluate_pair(pal, Pair("a", ("b",), "ui", "a/b")).status == "pass"
    assert evaluate_pair(pal, Pair("a", ("b",), "large", "a/b")).status == "pass"
    assert evaluate_pair(pal, Pair("a", ("b",), "text", "a/b")).status == "FAIL"


# -------------------------------------------------------------- league colour examples

def test_gold_fails_white_on_colour():
    problems = check_league_colour("classic", "#C98A12")
    assert problems
    white = [p for p in problems if p.pair == "league-ink/league-base"]
    assert white and white[0].theme == "light"
    msg = white[0].message
    assert msg.startswith("league.yml colour #C98A12: white text on it is 2.")
    assert "light theme (needs 4.5:1)" in msg
    assert "darker colour" in msg
    assert white[0].required == 4.5 and white[0].ratio < 3.0


def test_navy_passes():
    assert check_league_colour("classic", "#1D3A6E") == []
    assert check_league_colour("basketball", "#1D3A6E") == []


def test_gold_dark_variant_is_checked_separately():
    # a good dark colour fixes the dark theme; the light theme still fails
    problems = check_league_colour("classic", "#C98A12", hex_dark="#1D3A6E")
    assert any(p.theme == "light" for p in problems)
    dark = [p for p in problems if p.theme == "dark" and p.pair == "league-ink/league-base"]
    assert not dark


def test_dark_theme_failure_tells_the_league_to_set_colour_dark():
    problems = check_league_colour("basketball", "#C98A12")
    dark = [p for p in problems if p.theme == "dark" and p.pair == "league-ink/league-base"]
    assert dark and "in the dark theme" in dark[0].message
    assert "colour_dark" in dark[0].message and "darker colour" in dark[0].message
    assert dark[0].setting == "colour"            # no colour_dark yet: the colour in use is `colour`
    problems = check_league_colour("basketball", "#1D3A6E", hex_dark="#C98A12")
    dark = [p for p in problems if p.theme == "dark" and p.pair == "league-ink/league-base"]
    assert dark and dark[0].setting == "colour_dark"
    assert dark[0].message.startswith("league.yml colour_dark #C98A12:") and "Change colour_dark" in dark[0].message


def test_bad_hex_is_a_clear_error():
    with pytest.raises(ValueError, match="colour"):
        check_league_colour("classic", "gold")
    with pytest.raises(ValueError, match="colour_dark"):
        check_league_colour("classic", "#1D3A6E", hex_dark="blue")


def test_there_is_no_second_league_colour():
    import inspect
    params = inspect.signature(check_league_colour).parameters
    assert list(params) == ["layout", "hex", "hex_dark"]
    with pytest.raises(TypeError):
        check_league_colour("classic", "#1D3A6E", hex_2="#FF0000")        # noqa
    assert cc.league_overrides("#1D3A6E", "#A6BAD3") == {"--st-league-color": "#1D3A6E", "--st-league-color-dark": "#A6BAD3"}
    assert "--st-layout-accent" not in cc.INLINE_INPUTS
    src = Path(cc.__file__).read_text(encoding="utf-8")
    assert "colour_2" not in src.replace("`colour_2` is not a league setting", "")
    assert "league-2" not in src
    assert "hex_2" not in src


def test_helper_names_are_the_renamed_ones():
    assert "layout-accent-base" in cc.LEAGUE_HELPERS and "layout-accent-tint" in cc.LEAGUE_HELPERS
    assert not any("league-2" in h for h in cc.LEAGUE_HELPERS)


def test_example_colours():
    cols = cc.alt_league_colours()
    names = [c["name"] for c in cols]
    assert names == ["Navy", "Deep red", "Forest green", "Teal", "Purple", "Brown", "Mid blue", "Gold"]
    assert [c["name"] for c in cols if c["expected_fail"]] == ["Gold"]
    for c in cols:                   # every colour that must pass has white text at 4.5:1 or more
        assert (contrast_ratio("#FFFFFF", c["hex"]) >= 4.5) == (not c["expected_fail"]), c


def test_report_flags_unexpected_league_failures_and_a_gold_that_passes():
    rep = cc.Report(layouts=["x"], colours=[{"name": "A", "hex": "#111111", "expected_fail": False},
                                              {"name": "G", "hex": "#222222", "expected_fail": True}])
    rep.league[("x", "A", "#111111")] = []
    rep.league[("x", "G", "#222222")] = [cc.Problem("x", "light", "p", 2.0, 4.5, "msg", "colour")]
    assert rep.ok and rep.league_failures == [] and rep.expected_fail_passes == []
    rep.league[("x", "A", "#111111")] = [cc.Problem("x", "dark", "p", 2.0, 4.5, "msg", "colour")]
    assert not rep.ok and len(rep.league_failures) == 1
    rep.league[("x", "A", "#111111")] = []
    rep.league[("x", "G", "#222222")] = []
    assert not rep.ok and rep.expected_fail_passes == ["G"]


# ---------------------------------------------------------------- the pair list

def pair_ids():
    return {p.id for p in cc.PAIRS}


def test_mark_outline_is_an_ui_pair_in_every_layout():
    marks = [p for p in cc.PAIRS if p.fg == "mark-line"]
    assert {p.id for p in marks} == {"mark-line/surface", "mark-line/mark-bg", "mark-line/score-bg"}
    for p in marks:
        assert p.kind == "ui" and p.enforced and p.need == 3.0
    plain = [p for p in marks if p.id != "mark-line/score-bg"]
    assert all(not p.only and not p.not_in for p in plain)             # no decor exemption, no slopitch-only split
    assert [p.only for p in marks if p.id == "mark-line/score-bg"] == [("scoreboard",)]


def test_review_pairs_are_present():
    ids = pair_ids()
    for want in ("panel-tile-text/panel-tile-bg", "panel-tile-text/tile-on-row", "score-text/panel-bg",
                 "score-text/footer-bg", "panel-text/score-bg", "text/blank-bg", "muted/blank-bg",
                 "brand-tint/header-bg", "badge-monogram", "badge-monogram-hockey", "panel-muted/score-bg",
                 "panel-text/ls-box", "panel-muted/ls-box", "panel-text-80/panel-bg"):
        assert want in ids, want
    assert len(ids) == len(cc.PAIRS)              # ids are unique (check_league_colour keys on them)
    tile = {p.id: p for p in cc.PAIRS}["panel-tile-text/tile-on-row"]
    assert tile.bg == ("panel-bg", "panel-row", "panel-tile-bg")


def test_either_measures_the_worst_alternative():
    pal = Palette.from_decls({"--st-t": "#FFFFFF", "--st-dark": "#000000", "--st-mid": "#808080"})
    pair = Pair("t", ("either(var(--st-dark), var(--st-mid))",), "text", "t/either")
    res = evaluate_pair(pal, pair)
    assert res.status == "FAIL"                                    # white on mid grey is 3.95:1
    assert res.ratio == pytest.approx(contrast_ratio("#FFFFFF", "#808080"))
    assert "case 2 of 2" in res.worst
    only_dark = evaluate_pair(pal, Pair("t", ("either(var(--st-dark), #101010)",), "text", "t/either"))
    assert only_dark.status == "pass"


def test_expressions_work_as_foreground_and_background():
    pal = Palette.from_decls({"--st-ink": "#000000", "--st-card": "#FFFFFF"})
    pair = Pair("color-mix(in oklab, var(--st-ink) 80%, transparent)", ("card",), "text", "ink-80/card")
    res = evaluate_pair(pal, pair)
    assert res.status == "pass" and res.fg_hex == to_hex(composite(parse_colour("color-mix(in oklab, #000 80%, transparent)"), WHITE))
    two_layers = Pair("ink", ("card", "color-mix(in oklab, var(--st-ink) 60%, transparent)"), "text", "ink/layer")
    assert evaluate_pair(pal, two_layers).status == "FAIL"        # black on 60% black


def test_real_pairs_that_the_review_found_missing_are_measured():
    pal = cc.palette("scoreboard", "light")
    res = {r.pair.id: r for r in cc.evaluate_palette(pal)}
    for pid in ("score-text/panel-bg", "score-text/footer-bg", "panel-text/score-bg", "brand-tint/header-bg",
                "mark-line/score-bg", "panel-tile-text/tile-on-row"):
        assert res[pid].status in ("pass", "FAIL"), (pid, res[pid].status, res[pid].note)
    assert res["badge-monogram"].status == "pass"
    assert res["badge-monogram-hockey"].status == "skip"          # Hockey only
    assert cc.evaluate_palette(cc.palette("hockey", "light"))[0] is not None


def test_trace_lists_every_role_in_both_themes():
    lines = cc.trace_custom("classic", "#2F6B3A")
    text = "\n".join(lines)
    assert "[light theme]" in text and "[dark theme]" in text
    assert "--st-league-base" in text and "--st-link" in text and "#2F6B3A" in text


# -------------------------------------------------------------------------- lint

def make_css_dir(tmp_path, parts, layout=None):
    css = tmp_path / "css"
    (css / "layouts").mkdir(parents=True)
    (css / "tokens.css").write_text(SYNTHETIC_TOKENS, encoding="utf-8")
    (css / "layouts" / "demo.css").write_text(layout or SYNTHETIC_LAYOUT, encoding="utf-8")
    for name, text in parts.items():
        (css / name).write_text(textwrap.dedent(text), encoding="utf-8")
    return css


def test_lint_flags_undefined_unused_and_raw_colours(tmp_path):
    css = make_css_dir(tmp_path, {
        "parts-x.css": """
            .a { color: var(--st-link); background: var(--st-ghost); }
            .b { color: var(--st-opt, var(--st-also-opt)); border-color: #ff0000; }
            .c { background: rgba(0, 0, 0, .5); color: white; }
            /* a comment about #123456 and white is fine */
            .d { background: color-mix(in oklab, var(--st-link) 20%, transparent); color: currentColor; }
            .e { fill: %23fff; }
        """,
    })
    out = lint_tokens(css)
    errors = [f for f in out if f.level == "ERROR"]
    text = "\n".join("%s %s" % (f.where, f.message) for f in errors)
    assert "--st-ghost" in text and "demo" in text                   # read, not defined
    assert "--st-opt" not in text and "--st-also-opt" not in text     # has a fallback
    assert "#ff0000" in text and "rgba(" in text and "white" in text and "%23fff" in text
    assert "#123456" not in text                                      # comments are ignored
    assert "transparent" not in text and "currentColor" not in text
    warnings = [f.message for f in out if f.level == "WARNING"]
    assert any("--st-surface" in w for w in warnings)                 # defined in the layout, read nowhere
    assert not any("--st-link" in w for w in warnings)                # read by a part
    assert not any("--st-league-color" in w for w in warnings)        # read by another token


def test_lint_reads_by_other_tokens_count(tmp_path):
    css = make_css_dir(tmp_path, {"parts-x.css": ".a { color: var(--st-link); }"})
    warnings = [f.message for f in lint_tokens(css) if f.level == "WARNING"]
    assert not any("--st-dim" in w for w in warnings)                 # read by --st-league-dim
    assert not any("--st-panel" in w and "demo" not in w for w in warnings)


def test_lint_clean_parts(tmp_path):
    layout = SYNTHETIC_LAYOUT
    css = make_css_dir(tmp_path, {"parts-x.css": ".a { color: var(--st-link); background: var(--st-surface); }"}, layout)
    assert [f for f in lint_tokens(css) if f.level == "ERROR" and "raw colour" in f.message] == []


def test_real_parts_have_no_raw_colours():
    bad = [f for f in lint_tokens() if f.level == "ERROR" and "raw colour" in f.message]
    assert bad == [], bad


# ------------------------------------------------------------------- the whole run

def test_real_layouts_resolve_every_pair_role():
    """Every layout resolves all the colour roles of the contract in both themes."""
    for lid in cc.layout_ids():
        for theme in cc.THEMES:
            pal = cc.palette(lid, theme)
            for role in cc.COLOUR_ROLES + list(cc.LEAGUE_HELPERS):
                assert pal.paint(role) is not None, (lid, theme, role)


def test_markdown_renders():
    rep = cc.run_checks(layouts=["classic"], with_league=False)
    md = cc.render_markdown(rep)
    assert md.startswith("<!-- GENERATED")
    for heading in ("## Summary", "## Failures", "## Every pair", "## League colour examples",
                    "## How stage 4 calls this", "## Token lint", "## Accepted exceptions"):
        assert heading in md


def test_markdown_league_matrix():
    rep = cc.run_checks(layouts=["classic", "curling"])
    md = cc.render_markdown(rep)
    sec = md[md.index("## League colour examples"):md.index("## How stage 4 calls this")]
    assert "| Colour | classic light | classic dark | curling light | curling dark |" in sec
    assert "| Navy #1D3A6E | pass | pass | pass | pass |" in sec
    assert "(expected fail)" in sec and "colour_2" in sec and "is not a league setting" in sec
    assert "check_league_colour(layout_id" in md and "data-league-colour" in md
