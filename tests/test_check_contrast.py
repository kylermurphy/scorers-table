"""Tests for scripts/check_contrast.py: the colour maths, the cascade, the pair checks,
the league colour messages and the token lint. Run with `python -m pytest` from the repo root.
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


def test_bad_hex_is_a_clear_error():
    with pytest.raises(ValueError, match="colour"):
        check_league_colour("classic", "gold")


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
                    "## Token lint", "## Accepted exceptions"):
        assert heading in md
