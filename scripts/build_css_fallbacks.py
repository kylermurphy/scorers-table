#!/usr/bin/env python3
"""Write assets/css/fallbacks.css: what a browser WITHOUT color-mix() paints.

Why
---
Every league-derived colour role in the layouts is a `color-mix(in oklab, ...)` of the league
colour, and a few parts mix roles too. Where color-mix() is unknown (Safari/iOS before 16.2,
Chrome before 111, Firefox before 113) a declaration that holds var() plus color-mix() is still
PARSED as valid, then becomes "invalid at computed-value time": the custom property is unset,
so backgrounds turn transparent and text colours are inherited. A plain declaration in front
of it does not help. The one reliable tool is
    @supports not (color: color-mix(in oklab, red, red)) { ... }
which only browsers without color-mix() apply.

What it writes
--------------
One @supports block with
  1. for every layout: a literal value (#RRGGBB, #RRGGBBAA or a gradient with literal stops)
     for EVERY colour custom property (`--st-*`) the layout defines, including the helpers
     (`--st-league-*`, `--st-layout-accent-*`), as they resolve for the layout's DEFAULT league
     colour. Three blocks: light, the OS preference (`@media (prefers-color-scheme: dark)`
     with `:not([data-theme="light"])`) and the explicit `[data-theme="dark"]`. The same
     selectors are repeated with `[data-league-colour]` so the layouts' custom-colour blocks
     (which use color-mix too) lose to the same literals (same specificity, loaded later).
  2. for the few parts that use color-mix() themselves (OVERRIDES below): the same
     declaration with the colour worked out for the default colours, for each layout.
  3. `.st-team--custom`: `--st-team` is the team's own hex, without the dark lift.
Colours are worked out with the checker's resolver (scripts/check_contrast.py), not a second
copy of the maths. `python scripts/check_contrast.py` runs every pair of docs/contrast.md against
this file with the block treated as active and color-mix() as missing, and fails when the file
is stale.

Usage (from the repo root)
--------------------------
    python scripts/build_css_fallbacks.py            # write assets/css/fallbacks.css
    python scripts/build_css_fallbacks.py --check    # exit 1 if it is stale, or a part's color-mix()
                                                     #   has no entry in OVERRIDES
Load order everywhere: fonts, tokens, layouts/<layout>, base, parts-*, fallbacks (LAST).
Standard library only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_contrast as cc  # noqa: E402

CSS_DIR = ROOT / "assets" / "css"
OUT_PATH = CSS_DIR / "fallbacks.css"
SUPPORTS_COND = "not (color: color-mix(in oklab, red, red))"

# Colour inputs a league sets inline (or the layout declares as its default for it). They are not
# roles and are never replaced: the inline style must keep working.
INPUTS = {"--st-league-color", "--st-league-color-dark", "--st-layout-accent", "--st-layout-accent-dark"}

# CSS files whose color-mix() calls are audited (the layouts are covered by the generated roles).
AUDITED_FILES = ("tokens.css", "base.css", "parts-shell.css", "parts-scores.css", "parts-data.css")


# =============================================================================
# The parts that use color-mix() themselves
# =============================================================================

@dataclass(frozen=True)
class Override:
    """One declaration in the parts CSS that holds color-mix().

    file, selector, prop, source   the declaration exactly as the CSS file has it (whitespace aside);
                                   scripts/build_css_fallbacks.py --check fails if the CSS has a
                                   color-mix() declaration that is not listed here, or a listed one is gone.
    value      what to write instead, in roles; every `color-mix(...)` in it is worked out for the
               layout's default colours and written as a literal. Default: `source`.
    fallback   for a declaration that is not a colour of the layout: a fixed text, written once, with no
               layout prefix (used for `.st-team--custom`).
    what       one line for the header of fallbacks.css and the report: what the fallback looks like.
    """
    file: str
    selector: str
    prop: str
    source: str
    what: str
    value: str = ""
    fallback: str = ""


OVERRIDES = [
    Override("tokens.css", ".st-team--custom", "--st-team",
             "color-mix(in oklab, var(--st-team-hex), white var(--st-team-lift))",
             fallback="var(--st-team-hex)",
             what="the team's own colour, without the dark-theme lift (dark custom team colours can be low contrast)"),
    Override("parts-shell.css", ".st-theme-toggle:hover", "background",
             "color-mix(in oklab, currentColor 12%, transparent)",
             value="color-mix(in oklab, var(--st-header-text) 12%, transparent)",
             what="header text colour at 12% (same look; the toggle's colour is --st-header-text)"),
    Override("parts-shell.css", '[data-layout="scoreboard"] .st-brand__tint', "color",
             "color-mix(in oklab, var(--st-header-text) 78%, var(--st-league-base))",
             what="the same mix, for the default league colour"),
    Override("parts-scores.css", '[data-layout="scoreboard"] .st-legend__key--blank', "background",
             "color-mix(in oklab, var(--st-score-bg), var(--st-score-text) 16%)",
             what="the same grey tile, for the default colours"),
    Override("parts-scores.css", '[data-layout="scoreboard"] .st-legend__key--blank', "border-color",
             "color-mix(in oklab, var(--st-score-bg), var(--st-score-text) 16%)",
             what="the same grey tile, for the default colours"),
    Override("parts-scores.css", '[data-layout="scoreboard"] .st-line-score tbody td.is-blank', "background",
             "color-mix(in oklab, var(--st-score-bg), var(--st-score-text) 16%)",
             what="the same grey tile, for the default colours"),
    Override("parts-scores.css", ':is([data-layout="basketball"], [data-layout="classic"]) .st-final', "--ls-bg",
             "color-mix(in oklab, var(--st-panel-text) 9%, var(--st-panel-bg))",
             what="the same inset box, for the default colours"),
    Override("parts-scores.css",
             ':is([data-layout="basketball"], [data-layout="classic"]) .st-final :is(thead th, tbody td).is-blank',
             "background", "color-mix(in oklab, var(--st-panel-text) 8%, transparent)",
             what="the same 8% veil, for the default colours"),
    Override("parts-scores.css",
             ':is([data-layout="basketball"], [data-layout="classic"]) .st-final .st-legend__key--blank',
             "background", "color-mix(in oklab, var(--st-panel-text) 8%, transparent)",
             what="the same 8% veil, for the default colours"),
    Override("parts-scores.css", '[data-layout="hockey"] .st-final::before', "background",
             "linear-gradient(color-mix(in oklab, var(--st-link) 11%, transparent), "
             "color-mix(in oklab, var(--st-link) 11%, transparent)) 28% 0 / 4px 100% no-repeat, "
             "linear-gradient(color-mix(in oklab, var(--st-hot) 11%, transparent), "
             "color-mix(in oklab, var(--st-hot) 11%, transparent)) 50% 0 / 4px 100% no-repeat, "
             "linear-gradient(color-mix(in oklab, var(--st-link) 11%, transparent), "
             "color-mix(in oklab, var(--st-link) 11%, transparent)) 72% 0 / 4px 100% no-repeat",
             what="the same three rink lines (11% veils), for the default colours"),
    Override("parts-scores.css", '[data-layout="slopitch"] .st-final .st-line-scroll', "background-image",
             "repeating-linear-gradient(180deg, transparent 0 23px, "
             "color-mix(in oklab, var(--st-line) 60%, transparent) 23px 24px)",
             what="the same ruled-paper lines (60% veil), for the default colours"),
    Override("parts-data.css", ".st-race__row--lead .st-race__bar", "background",
             "color-mix(in oklab, var(--st-panel-text) 22%, transparent)",
             what="the same 22% track, for the default colours"),
]


# =============================================================================
# Reading the CSS (all declarations, not only custom properties)
# =============================================================================

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def iter_declarations(text: str, media=None):
    """Yield (media, selector, prop, value) for every declaration in the CSS text (comments
    removed; @media and @supports are entered, @keyframes and @font-face are skipped)."""
    text = cc.strip_comments(text)
    i, n = 0, len(text)
    while i < n:
        j, depth, quote = i, 0, None
        while j < n:
            ch = text[j]
            if quote:
                if ch == "\\":
                    j += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and ch in "{;":
                break
            j += 1
        prelude = text[i:j].strip()
        if j >= n:
            break
        if text[j] == ";":
            i = j + 1
            continue
        k = cc._matching_brace(text, j)
        body = text[j + 1:k]
        low = prelude.lower()
        if low.startswith("@media") or low.startswith("@supports"):
            yield from iter_declarations(body, _norm(prelude) if low.startswith("@media") else media)
        elif prelude.startswith("@"):
            pass
        elif prelude:
            for part in cc.split_top(body, ";"):
                if ":" in part:
                    prop, _, value = part.partition(":")
                    yield media, _norm(prelude), prop.strip(), _norm(value)
        i = k + 1


def color_mix_declarations(css_dir: Path = CSS_DIR) -> list:
    """[(file name, media, selector, prop, value)] for every declaration holding color-mix() in the
    audited CSS files."""
    found = []
    for name in AUDITED_FILES:
        path = css_dir / name
        if not path.exists():
            continue
        for media, sel, prop, value in iter_declarations(path.read_text(encoding="utf-8")):
            if "color-mix(" in value:
                found.append((name, media, sel, prop, value))
    return found


def coverage_problems(css_dir: Path = CSS_DIR) -> list:
    """Strings describing color-mix() declarations in the parts without an OVERRIDES entry, and
    OVERRIDES entries that no longer match the CSS."""
    problems = []
    listed = {(o.file, _norm(o.selector), o.prop, _norm(o.source)) for o in OVERRIDES}
    seen = set()
    for name, media, sel, prop, value in color_mix_declarations(css_dir):
        key = (name, sel, prop, value)
        seen.add(key)
        if name == "tokens.css" and sel == "[data-layout]" and prop.startswith("--st-") and all(
                prop in colour_props(lid) for lid in cc.layout_ids()):
            continue            # a league helper: written for every layout with the roles
        if media:
            problems.append("%s: `%s { %s }` is inside @media %s: OVERRIDES does not handle that" % (name, sel, prop, media))
        elif key not in listed:
            problems.append("%s: `%s { %s: %s }` uses color-mix() but has no entry in OVERRIDES in "
                            "scripts/build_css_fallbacks.py (old browsers would lose it)" % (name, sel, prop, value))
    for key in sorted(listed - seen):
        problems.append("%s: OVERRIDES lists `%s { %s: %s }` but the CSS has no such declaration: update or remove the entry"
                        % key)
    return problems


# =============================================================================
# Literal colours
# =============================================================================

_POS = re.compile(r"^[-+]?[\d.]+(%|px)?$")
_DIRECTION = re.compile(r"^\s*(to\s|[-+]?[\d.]+(deg|turn|rad|grad))", re.I)


def literal_paint(text: str) -> str:
    """A resolved colour or linear-gradient (var() already substituted) as literal CSS: text
    without color-mix() is kept as it is; otherwise #RRGGBB / #RRGGBBAA, or the gradient with
    each colour stop a literal."""
    s = _norm(text)
    if "color-mix(" not in s:
        return s                # already literal (a hex, rgba(), a gradient of those, `none`)
    m = re.match(r"^((?:repeating-)?linear-gradient)\(", s, re.I)
    if not m:
        return cc.to_hex(cc.parse_colour(s))
    args = cc.split_top(cc._func_args(s, m.group(1)))
    out = []
    for idx, arg in enumerate(args):
        if idx == 0 and _DIRECTION.match(arg):
            out.append(arg.strip())
            continue
        toks = cc.split_ws(arg)
        pos = []
        while len(toks) > 1 and _POS.match(toks[-1]):
            pos.insert(0, toks.pop())
        out.append(" ".join([cc.to_hex(cc.parse_colour(" ".join(toks)))] + pos))
    return "%s(%s)" % (m.group(1), ", ".join(out))


def colour_props(layout: str) -> list:
    """Names of the custom properties of `layout` that hold a colour or gradient, in any theme or
    custom-colour state."""
    names = set()
    for theme in cc.THEMES:
        for custom in (False, True):
            pal = cc.Palette(layout, theme, custom=custom)
            for name, raw in pal.decls.items():
                if not name.startswith("--st-") or name in INPUTS:
                    continue
                try:
                    cc.parse_paint(cc.substitute(raw, pal.decls))
                except cc.ColourError:
                    continue
                names.add(name)
    return sorted(names)


def role_values(layout: str, theme: str) -> dict:
    """{--st-role: literal} for the layout's default colours in one theme (the layout's own
    cascade, color-mix and all, worked out)."""
    pal = cc.Palette(layout, theme)
    out = {}
    for name in colour_props(layout):
        if name not in pal.decls:
            continue
        out[name] = literal_paint(cc.substitute(pal.decls[name], pal.decls))
    return out


def resolve_value(value: str, pal) -> str:
    """`value` with every color-mix(...) worked out for the palette's colours."""
    out, i = [], 0
    while True:
        j = value.find("color-mix(", i)
        if j < 0:
            out.append(value[i:])
            break
        end = cc._match_paren(value, j + len("color-mix"))
        paint = pal.paint(value[j:end + 1])
        if paint is None or not isinstance(paint, cc.Colour):
            raise ValueError("cannot work out %r for %s %s" % (value[j:end + 1], pal.layout, pal.theme))
        out.append(value[i:j])
        out.append(cc.to_hex(paint))
        i = end + 1
    res = "".join(out)
    if "var(" in res:
        raise ValueError("override value %r still holds var() after resolving: it may only read roles inside color-mix()" % res)
    return res


# =============================================================================
# Selectors
# =============================================================================

_LAYOUT_ATTR = r'\[data-layout="([\w-]+)"\]'
_PREFIX = re.compile(r"^(?:%s|:is\(\s*(%s(?:\s*,\s*%s)*)\s*\))" % (_LAYOUT_ATTR, _LAYOUT_ATTR, _LAYOUT_ATTR))


def layouts_and_rest(selector: str, all_layouts: list) -> tuple:
    """(layouts, rest) for a parts selector: the layouts it names at its start and the rest of the
    selector after that prefix; without a layout prefix, all layouts and ' ' + the selector."""
    m = _PREFIX.match(selector)
    if m:
        ids = [m.group(1)] if m.group(1) else re.findall(_LAYOUT_ATTR, m.group(2))
        return ids, selector[m.end():]
    return list(all_layouts), " " + selector


def theme_prefix(layout: str, variant: str, custom: bool = False) -> str:
    base = '[data-layout="%s"]%s' % (layout, "[data-league-colour]" if custom else "")
    return {"light": base, "os-dark": base + ':not([data-theme="light"])', "dark": base + '[data-theme="dark"]'}[variant]


# =============================================================================
# Writing the file
# =============================================================================

def _block(selectors: list, decls: dict, indent: str = "  ") -> list:
    lines = [indent + (",\n" + indent).join(selectors) + " {"]
    for k in sorted(decls):
        lines.append("%s  %s: %s;" % (indent, k, decls[k]))
    lines.append(indent + "}")
    return lines


def render(layouts: list = None) -> str:
    layouts = layouts or cc.layout_ids()
    L = []
    add = L.append
    add("/* scorers-table: fallbacks for browsers without color-mix().")
    add(" *")
    add(" * GENERATED by scripts/build_css_fallbacks.py. Do not edit by hand. To regenerate:")
    add(" *     python scripts/build_css_fallbacks.py        (--check: exit 1 if stale)")
    add(" * `python scripts/check_contrast.py` also fails when this file is stale.")
    add(" *")
    add(" * Load it LAST: fonts, tokens, layouts/<layout>, base, parts-*, fallbacks. Its selectors have")
    add(" * the same specificity as the layout blocks they replace (the custom-colour ones too), so")
    add(" * source order decides.")
    add(" *")
    add(" * Why: the layouts derive every league colour with color-mix(in oklab, ...). A browser that does")
    add(" * not know color-mix() (Safari/iOS before 16.2, Chrome before 111, Firefox before 113) reads a")
    add(" * declaration holding var() + color-mix() as valid, then drops the custom property: backgrounds")
    add(" * go transparent and text colours are inherited. A plain declaration in front does not help.")
    add(" * Only browsers that fail the @supports test below read the rules in this file.")
    add(" *")
    add(" * What it does: for every layout, a literal value for every colour custom property (--st-*,")
    add(" * the helpers --st-league-* and --st-layout-accent-* too) as the layout resolves it for its")
    add(" * DEFAULT league colour, in light, in the OS dark preference and in [data-theme=\"dark\"]; the same")
    add(" * selectors again with [data-league-colour] so the layouts' custom-colour blocks lose; and the")
    add(" * few part rules that use color-mix() themselves, listed below.")
    add(" *")
    add(" * What a league loses on such a browser: its own colour. The page is the layout's default look")
    add(" * (readable, every text pair at WCAG AA, checked by scripts/check_contrast.py --fallbacks), and a")
    add(" * league's custom team colour is shown without the dark-theme lift. Everything else is the same.")
    add(" *")
    add(" * Part rules replaced (file: selector { property }):")
    for o in OVERRIDES:
        add(" *   %s: %s { %s }: %s" % (o.file, o.selector, o.prop, o.what))
    add(" */")
    add("@supports %s {" % SUPPORTS_COND)

    for lid in layouts:
        light = role_values(lid, "light")
        dark = role_values(lid, "dark")
        names = set(light) | set(dark)
        add("  /* ---- %s */" % lid)
        sel = lambda variant: [theme_prefix(lid, variant), theme_prefix(lid, variant, custom=True)]
        L += _block(sel("light"), light)
        add("  @media (prefers-color-scheme: dark) {")
        L += _block(sel("os-dark"), dark, "    ")
        add("  }")
        L += _block(sel("dark"), dark)
        assert names == set(light) == set(dark), "%s: light and dark define different colour properties" % lid

    add("")
    add("  /* ---- parts that use color-mix() themselves (OVERRIDES in scripts/build_css_fallbacks.py) */")
    groups = {}                     # (selector, tuple of layouts) -> [Override]
    for o in OVERRIDES:
        if o.fallback:
            continue
        groups.setdefault(o.selector, []).append(o)
    for selector, items in groups.items():
        ids, rest = layouts_and_rest(selector, layouts)
        for lid in ids:
            if lid not in layouts:
                continue
            by_variant = {}
            for variant, theme in (("light", "light"), ("dark", "dark")):
                pal = cc.Palette(lid, theme)
                by_variant[variant] = {o.prop: resolve_value(o.value or o.source, pal) for o in items}
            L += _block([theme_prefix(lid, "light") + rest], by_variant["light"])
            if by_variant["dark"] != by_variant["light"]:
                add("  @media (prefers-color-scheme: dark) {")
                L += _block([theme_prefix(lid, "os-dark") + rest], by_variant["dark"], "    ")
                add("  }")
                L += _block([theme_prefix(lid, "dark") + rest], by_variant["dark"])
    for o in OVERRIDES:
        if o.fallback:
            L += _block([o.selector], {o.prop: o.fallback})
    add("}")
    return "\n".join(L) + "\n"


def problems(layouts: list = None) -> list:
    """Everything wrong with the committed fallbacks.css: missing, stale, or a part's
    color-mix() without an override. Empty = fine."""
    out = coverage_problems()
    try:
        want = render(layouts)
    except Exception as e:      # a colour that cannot be worked out
        return out + ["cannot generate fallbacks.css: %s" % e]
    have = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else None
    if have is None:
        out.append("assets/css/fallbacks.css does not exist: run python scripts/build_css_fallbacks.py")
    elif have != want:
        out.append("assets/css/fallbacks.css is out of date: run python scripts/build_css_fallbacks.py")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write assets/css/fallbacks.css (browsers without color-mix()).")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if the file is stale or a part is not covered")
    ap.add_argument("--out", default=str(OUT_PATH), help="where to write")
    args = ap.parse_args(argv)
    if args.check:
        probs = problems()
        for p in probs:
            print("ERROR", p)
        print("fallbacks.css: %s" % ("up to date" if not probs else "%d problem(s)" % len(probs)))
        return 1 if probs else 0
    cov = coverage_problems()
    for p in cov:
        print("ERROR", p)
    if cov:
        return 1
    text = render()
    Path(args.out).write_text(text, encoding="utf-8")
    print("wrote %s (%d lines)" % (os.path.relpath(args.out, ROOT) if str(args.out).startswith(str(ROOT)) else args.out,
                                   text.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
