#!/usr/bin/env python3
"""WCAG contrast check and token lint for the scorers-table design system.

What it does
------------
1. Reads assets/css/tokens.css and assets/css/layouts/<id>.css and works out, for every
   layout, theme (light, dark, or the OS preference with no data-theme) and "custom
   colour" state (the <html> carries data-league-colour or not), the value of every
   --st-* custom property by running a small cascade the way a browser does: every
   matching rule, sorted by specificity and then source order; var() with fallbacks;
   color-mix() in oklab/srgb; hex and rgb(); linear-gradient().
2. Measures every text / background / UI pair the design needs (PAIRS below), with
   alpha colours composited over what they sit on, and gradients checked on every
   stop. Writes docs/contrast.md (generated).
3. Runs the league colour examples (--st-league-color set inline and the
   data-league-colour attribute on, as stage 4 does) through the same pairs.
   `check_league_colour()` is the function stage 4's data check calls.
4. Lints the tokens (roles read but undefined, roles never read, raw colours in the
   parts CSS) and checks that each layout's two dark blocks (the media query and the
   [data-theme="dark"] one) are identical, for the custom-colour blocks too, and that
   a dark custom block restates every property its light custom block sets.
5. Browsers without color-mix(): runs every pair again on the cascade with the `@supports not (color:
   color-mix(...))` block of assets/css/fallbacks.css (written by scripts/build_css_fallbacks.py) active,
   for every layout x theme x {default, data-league-colour attribute}; any color-mix() still reachable is an
   error, and a stale fallbacks.css fails the run (--check or not).
6. `--verify-browser` compares the colour maths with real Chromium (optional).

Usage (from the repo root)
--------------------------
    python scripts/check_contrast.py                 # run everything, write docs/contrast.md
    python scripts/check_contrast.py --check         # same, but fail if docs/contrast.md is stale
    python scripts/check_contrast.py --tokens        # token lint only
    python scripts/check_contrast.py --fallbacks     # only: every pair with assets/css/fallbacks.css active, color-mix() missing
    python scripts/check_contrast.py --verify-browser  # also compare the maths with Chromium
    python scripts/check_contrast.py --trace classic "#2F6B3A"  # how every role resolves in custom mode
Exit code 1 when an enforced pair fails, the dark blocks differ, the lint finds an
ERROR, or the Chromium comparison is out by more than 1/255.

The colour maths (`parse_colour`, `mix_colours`, `contrast_ratio`, `composite`, ...)
is importable: `from scripts.check_contrast import contrast_ratio`.
Standard library only.
"""
from __future__ import annotations

import argparse
import functools
import glob
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "assets" / "css"
LAYOUT_DIR = CSS_DIR / "layouts"
DOC_PATH = ROOT / "docs" / "contrast.md"
FALLBACKS_PATH = CSS_DIR / "fallbacks.css"
THEMES = ("light", "dark")

# WCAG 2.x thresholds
REQUIRED = {"text": 4.5, "large": 3.0, "ui": 3.0}


# =============================================================================
# 1. Colour maths
# =============================================================================

@dataclass(frozen=True)
class Colour:
    """An sRGB colour: r, g, b in 0..1 (may lie outside 0..1 for out-of-gamut
    colour-mix results, which are only clipped when painted), alpha 0..1."""
    r: float
    g: float
    b: float
    a: float = 1.0


@dataclass(frozen=True)
class Gradient:
    """A linear-gradient: a list of (Colour, position 0..1 or None). With `either` it is
    not a gradient but a list of alternative colours (`either(a, b)`): a pair is measured
    on each of them and the worst counts (the same text sits on one OR the other)."""
    stops: tuple
    either: bool = False


class ColourError(ValueError):
    """A value that is not a colour this checker understands."""


class UndefinedVar(ColourError):
    """var(--x) with no value and no fallback."""


WHITE = Colour(1.0, 1.0, 1.0)
BLACK = Colour(0.0, 0.0, 0.0)
TRANSPARENT = Colour(0.0, 0.0, 0.0, 0.0)


def _lin(c: float) -> float:
    """sRGB (gamma) -> linear, sign-preserving so out-of-gamut values round-trip."""
    s = -1.0 if c < 0 else 1.0
    c = abs(c)
    return s * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)


def _gam(c: float) -> float:
    """linear -> sRGB (gamma), sign-preserving."""
    s = -1.0 if c < 0 else 1.0
    c = abs(c)
    return s * (c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def to_oklab(c: Colour) -> tuple:
    """Colour -> (L, a, b) in Oklab (Ottosson's matrices)."""
    r, g, b = _lin(c.r), _lin(c.g), _lin(c.b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = math.copysign(abs(l) ** (1 / 3), l), math.copysign(abs(m) ** (1 / 3), m), math.copysign(abs(s) ** (1 / 3), s)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def from_oklab(L: float, a: float, b: float, alpha: float = 1.0) -> Colour:
    """Oklab -> Colour (not clipped to the sRGB gamut)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return Colour(_gam(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
                  _gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
                  _gam(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s), alpha)


def mix_colours(c1: Colour, c2: Colour, p1: Optional[float] = None, p2: Optional[float] = None,
                space: str = "oklab") -> Colour:
    """CSS `color-mix(in <space>, c1 p1%, c2 p2%)` (percentages 0..100; both omitted = 50/50,
    one omitted = the rest). Premultiplied interpolation; percentages that sum to
    less than 100 scale the alpha, to more than 100 are normalised. Oklab or srgb."""
    if p1 is None and p2 is None:
        p1, p2 = 50.0, 50.0
    elif p1 is None:
        p1 = 100.0 - p2
    elif p2 is None:
        p2 = 100.0 - p1
    total = p1 + p2
    if total <= 0:
        raise ColourError("color-mix percentages add up to 0")
    alpha_mult = min(total, 100.0) / 100.0
    w1, w2 = p1 / total, p2 / total
    alpha = (c1.a * w1 + c2.a * w2)
    if alpha <= 0:
        return TRANSPARENT
    if space == "oklab":
        x1, x2 = to_oklab(c1), to_oklab(c2)
    elif space == "srgb":
        x1, x2 = (c1.r, c1.g, c1.b), (c2.r, c2.g, c2.b)
    else:
        raise ColourError("color-mix space %r not supported (oklab and srgb are)" % space)
    mixed = [(x1[i] * c1.a * w1 + x2[i] * c2.a * w2) / alpha for i in range(3)]
    alpha *= alpha_mult
    if space == "oklab":
        return from_oklab(mixed[0], mixed[1], mixed[2], alpha)
    return Colour(mixed[0], mixed[1], mixed[2], alpha)


def _clip(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def rgb8(c: Colour) -> tuple:
    """The 8-bit (r, g, b) a browser paints for this colour (alpha ignored, gamut clipped)."""
    return tuple(int(math.floor(_clip(v) * 255 + 0.5)) for v in (c.r, c.g, c.b))


def to_hex(c: Colour) -> str:
    """'#RRGGBB', or '#RRGGBBAA' when translucent."""
    h = "#%02X%02X%02X" % rgb8(c)
    if c.a < 1:
        h += "%02X" % int(math.floor(_clip(c.a) * 255 + 0.5))
    return h


def composite(fg: Colour, bg: Colour) -> Colour:
    """`fg` painted over the opaque `bg` (in gamma-encoded sRGB, as browsers do)."""
    a = _clip(fg.a)
    return Colour(_clip(fg.r) * a + _clip(bg.r) * (1 - a),
                  _clip(fg.g) * a + _clip(bg.g) * (1 - a),
                  _clip(fg.b) * a + _clip(bg.b) * (1 - a), 1.0)


def relative_luminance(c: Union[Colour, str]) -> float:
    """WCAG relative luminance of a colour (8-bit values, alpha ignored)."""
    if isinstance(c, str):
        c = parse_colour(c)
    r, g, b = (v / 255 for v in rgb8(c))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(a: Union[Colour, str], b: Union[Colour, str]) -> float:
    """WCAG contrast ratio (1..21) of two opaque colours (hex strings or Colour)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def floor2(x: float) -> float:
    """Truncate to 2 decimals so a failing 4.497 never prints as 4.50."""
    return math.floor(x * 100 + 1e-9) / 100


# ----------------------------------------------------------------- parsing text

def split_top(s: str, sep: str = ",") -> list:
    """Split on `sep` outside brackets and quotes."""
    out, depth, quote, cur = [], 0, None, []
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def split_ws(s: str) -> list:
    """Split on whitespace outside brackets."""
    out, depth, cur = [], 0, []
    for ch in s.strip():
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch.isspace() and depth == 0:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)"
_NUM_RE = re.compile("^" + _NUM + "$")
_PCT_RE = re.compile("^(" + _NUM + ")%$")
_NAMED = {"white": WHITE, "black": BLACK, "transparent": TRANSPARENT}


def _func_args(s: str, name: str) -> str:
    """The text inside `name( ... )` for a string that is exactly one such call."""
    s = s.strip()
    if not s.endswith(")"):
        raise ColourError("bad %s() value: %r" % (name, s))
    return s[len(name) + 1:-1]


def parse_colour(text: str) -> Colour:
    """Parse one colour: #hex (3/4/6/8 digits), rgb()/rgba(), white/black/transparent,
    color-mix(in oklab|srgb, ...) with nested colours. var() must already be substituted."""
    s = text.strip()
    low = s.lower()
    if low in _NAMED:
        return _NAMED[low]
    if low.startswith("#"):
        h = low[1:]
        if not re.fullmatch(r"[0-9a-f]+", h) or len(h) not in (3, 4, 6, 8):
            raise ColourError("bad hex colour %r" % text)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        v = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
        return Colour(v[0], v[1], v[2], v[3] if len(v) == 4 else 1.0)
    m = re.match(r"^(rgba?|color-mix)\(", low)
    if not m:
        raise ColourError("not a colour I can read: %r" % text)
    fn = m.group(1)
    if fn == "color-mix":
        return _parse_color_mix(_func_args(s, "color-mix"))
    args = _func_args(s, fn)
    parts = [p for p in re.split(r"[\s,/]+", args.strip()) if p]
    if len(parts) not in (3, 4):
        raise ColourError("bad %s(): %r" % (fn, text))

    def chan(p: str) -> float:
        pm = _PCT_RE.match(p)
        if pm:
            return float(pm.group(1)) / 100
        if _NUM_RE.match(p):
            return float(p) / 255
        raise ColourError("bad channel %r in %r" % (p, text))

    def alpha(p: str) -> float:
        pm = _PCT_RE.match(p)
        if pm:
            return float(pm.group(1)) / 100
        if _NUM_RE.match(p):
            return float(p)
        raise ColourError("bad alpha %r in %r" % (p, text))

    return Colour(chan(parts[0]), chan(parts[1]), chan(parts[2]), alpha(parts[3]) if len(parts) == 4 else 1.0)


def _parse_color_mix(args: str) -> Colour:
    items = split_top(args)
    if len(items) != 3:
        raise ColourError("color-mix needs a space and two colours: %r" % args)
    head = items[0].split()
    if len(head) != 2 or head[0].lower() != "in":
        raise ColourError("color-mix space not understood: %r" % items[0])
    space = head[1].lower()
    parsed = []
    for item in items[1:]:
        toks = split_ws(item)
        pct = None
        if len(toks) > 1 and _PCT_RE.match(toks[-1]):
            pct = float(_PCT_RE.match(toks[-1]).group(1))
            toks = toks[:-1]
        elif len(toks) > 1 and _PCT_RE.match(toks[0]):
            pct = float(_PCT_RE.match(toks[0]).group(1))
            toks = toks[1:]
        parsed.append((parse_colour(" ".join(toks)), pct))
    (c1, p1), (c2, p2) = parsed
    return mix_colours(c1, c2, p1, p2, space)


def parse_paint(text: str) -> Union[Colour, Gradient]:
    """A colour, a linear-gradient() (kept as its colour stops), or `either(c1, c2, ...)`
    (this checker's own form for "one of these colours", see Gradient.either)."""
    s = text.strip()
    if re.match(r"^either\(", s, re.I):
        return Gradient(tuple((parse_colour(a.strip()), None) for a in split_top(_func_args(s, "either"))), either=True)
    if re.match(r"^(repeating-)?linear-gradient\(", s, re.I):
        fn = s[:s.index("(")]
        args = split_top(_func_args(s, fn))
        if args and re.match(r"^\s*(to\s|[-+]?[\d.]+(deg|turn|rad|grad))", args[0], re.I):
            args = args[1:]
        stops = []
        for a in args:
            toks = split_ws(a)
            pos = None
            if len(toks) > 1 and re.match(r"^[-+]?[\d.]+(%|px)?$", toks[-1]):
                pm = _PCT_RE.match(toks[-1])
                pos = float(pm.group(1)) / 100 if pm else None
                toks = toks[:-1]
            stops.append((parse_colour(" ".join(toks)), pos))
        if not stops:
            raise ColourError("gradient with no stops: %r" % text)
        return Gradient(tuple(stops))
    return parse_colour(s)


# =============================================================================
# 2. CSS reading and the cascade
# =============================================================================

# The one @supports condition the checker understands: assets/css/fallbacks.css puts the rules for
# browsers without color-mix() in `@supports not (color: color-mix(in oklab, red, red))`. Such rules
# apply only in fallback mode (see cascade_rules); other @supports blocks are skipped.
NO_COLOR_MIX = "not (color: color-mix(in oklab, red, red))"


@dataclass
class Rule:
    """One style rule: selector text, its custom-property declarations, the @media
    condition it sits in (None = none), the file, a global source-order number, and
    `supports` (NO_COLOR_MIX inside the fallbacks' @supports block, else None)."""
    selector: str
    decls: dict
    media: Optional[str]
    source: str
    order: int
    supports: Optional[str] = None      # NO_COLOR_MIX when the rule sits in the fallbacks' @supports block


def strip_comments(text: str) -> str:
    """Remove /* comments */, keeping newlines so line numbers stay right."""
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), text, flags=re.S)


def _matching_brace(text: str, start: int) -> int:
    """Index of the `}` closing the `{` at `start` (quotes respected)."""
    depth, quote, i, n = 0, None, start, len(text)
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def _parse_decls(body: str) -> dict:
    """{name: value} for the custom properties (--x) of a declaration block; the last one wins."""
    out = {}
    for part in split_top(body, ";"):
        if ":" not in part:
            continue
        name, _, value = part.partition(":")
        name = name.strip()
        if name.startswith("--"):
            out[name] = re.sub(r"\s*!important\s*$", "", value.strip())
    return out


def parse_css(text: str, source: str = "", media: Optional[str] = None, _counter: Optional[list] = None,
              supports: Optional[str] = None) -> list:
    """Parse CSS text into Rules (custom properties only). Understands @media nesting and the
    fallbacks' `@supports not (color: color-mix(...))` block; other at-rules are skipped."""
    text = strip_comments(text)
    counter = _counter if _counter is not None else [0]
    rules, i, n = [], 0, len(text)
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
        k = _matching_brace(text, j)
        body = text[j + 1:k]
        if prelude.lower().startswith("@media"):
            rules += parse_css(body, source, prelude[6:].strip(), counter, supports)
        elif prelude.lower().startswith("@supports"):
            if re.sub(r"\s+", " ", prelude[9:]).strip().lower() == NO_COLOR_MIX:
                rules += parse_css(body, source, media, counter, NO_COLOR_MIX)
        elif prelude.startswith("@"):
            pass
        elif prelude:
            for sel in split_top(prelude):
                sel = re.sub(r"\s+", " ", sel.strip())
                counter[0] += 1
                rules.append(Rule(sel, _parse_decls(body), media, source, counter[0], supports))
        i = k + 1
    return rules


@functools.lru_cache(maxsize=None)
def _load_rules(path: str, mtime: float) -> tuple:
    return tuple(parse_css(Path(path).read_text(encoding="utf-8"), os.path.basename(path)))


def load_rules(path) -> list:
    """Rules of one CSS file (cached by modification time)."""
    p = str(path)
    return list(_load_rules(p, os.path.getmtime(p)))


def layout_ids() -> list:
    """Layout ids, from the files in assets/css/layouts/."""
    return sorted(p.stem for p in LAYOUT_DIR.glob("*.css"))


_ATTR = r'\[\s*([\w-]+)\s*(?:=\s*"([^"]*)"\s*)?\]'
_ATTR_RE = re.compile(_ATTR)
_NOT_RE = re.compile(r":not\(\s*" + _ATTR + r"\s*\)")


def match_selector(selector: str, attrs: dict) -> Optional[tuple]:
    """Specificity (a, b, c) if `selector` matches an element with these attributes
    (a dict, absent attribute = missing), else None. Only the selector shapes tokens
    and layouts use are understood: `:root`, `[attr]`, `[attr="v"]`, `:not([attr="v"])`,
    several of them joined without spaces (each counts one attribute-level of specificity,
    a :not() counts its argument). Anything else (classes, descendants) never matches."""
    s = selector.strip()
    if s == ":root":
        return (0, 1, 0)
    pos, spec = 0, 0
    if not s:
        return None
    while pos < len(s):
        m = _NOT_RE.match(s, pos)
        if m:
            name, val = m.group(1), m.group(2)
            present = name in attrs and (val is None or attrs[name] == val)
            if present:
                return None
            spec += 1
            pos = m.end()
            continue
        m = _ATTR_RE.match(s, pos)
        if m:
            name, val = m.group(1), m.group(2)
            if name not in attrs or (val is not None and attrs[name] != val):
                return None
            spec += 1
            pos = m.end()
            continue
        return None
    return (0, spec, 0)


def media_matches(media: Optional[str], prefers_dark: bool) -> bool:
    """Does this @media condition hold? Only prefers-color-scheme is modelled."""
    if media is None:
        return True
    m = re.fullmatch(r"\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)", media.strip())
    if not m:
        return False
    return (m.group(1) == "dark") == prefers_dark


def cascade_rules(rule_lists: list, layout: str, theme: Optional[str], prefers_dark: bool = False,
                  overrides: Optional[dict] = None, custom: bool = False, fallback: bool = False) -> dict:
    """The custom properties on an element carrying data-layout=<layout>, data-theme=<theme>
    (None = attribute absent) and, if `custom`, the data-league-colour attribute, as a
    browser computes them. `prefers_dark` is the OS preference (matters for the @media
    blocks). `rule_lists` is one list of Rules per stylesheet, in load order. Every rule whose
    selector matches and whose @media holds applies; they are sorted by specificity first,
    then by stylesheet, then by source order, and the last declaration of a property wins.
    `overrides` act like an inline style (they beat every rule). `fallback` models a browser
    without color-mix(): the rules in the `@supports not (color: color-mix(...))` block apply
    (otherwise they never do, because the browser supports color-mix())."""
    attrs = {"data-layout": layout}
    if theme:
        attrs["data-theme"] = theme
    if custom:
        attrs["data-league-colour"] = ""
    matched = []
    for idx, rules in enumerate(rule_lists):
        for rule in rules:
            if rule.supports and not fallback:
                continue
            if not media_matches(rule.media, prefers_dark):
                continue
            spec = match_selector(rule.selector, attrs)
            if spec is not None:
                matched.append((spec, idx, rule.order, rule))
    matched.sort(key=lambda t: t[:3])
    decls = {}
    for _, _, _, rule in matched:
        decls.update(rule.decls)
    if overrides:
        decls.update(overrides)
    return decls


def cascade(layout: str, theme: Optional[str], prefers_dark: bool = False,
            overrides: Optional[dict] = None, css_files: Optional[list] = None,
            custom: bool = False, fallback: bool = False) -> dict:
    """`cascade_rules` over assets/css/tokens.css and layouts/<layout>.css (or `css_files`);
    with `fallback`, over tokens, the layout and fallbacks.css, the block for browsers without
    color-mix() active."""
    if css_files is None:
        css_files = [CSS_DIR / "tokens.css", LAYOUT_DIR / (layout + ".css")]
        if fallback:
            css_files.append(FALLBACKS_PATH)
    return cascade_rules([load_rules(f) for f in css_files], layout, theme, prefers_dark, overrides, custom, fallback)


def _match_paren(s: str, open_idx: int) -> int:
    """Index of the `)` that closes the `(` at open_idx (quotes respected)."""
    depth, quote = 0, None
    for i in range(open_idx, len(s)):
        ch = s[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ColourError("unbalanced parentheses in %r" % s)


def substitute(value: str, decls: dict, _stack: tuple = ()) -> str:
    """Replace every var(--x[, fallback]) in `value` by the text it stands for (recursively;
    fallbacks may hold var() too). A custom property whose own value cannot be resolved is
    invalid, so the fallback is used, as in a browser. Raises UndefinedVar otherwise."""
    out, i = [], 0
    while True:
        m = re.search(r"(?<![\w-])var\(", value[i:])
        if not m:
            out.append(value[i:])
            break
        start = i + m.start()
        out.append(value[i:start])
        end = _match_paren(value, start + 3)
        inner = value[start + 4:end]
        parts = split_top(inner)
        name = parts[0].strip()
        fallback = ",".join(parts[1:]).strip() if len(parts) > 1 else None
        text = None
        if name in decls and name not in _stack:
            try:
                text = substitute(decls[name], decls, _stack + (name,))
            except UndefinedVar:
                text = None
        if text is None:
            if fallback is None:
                raise UndefinedVar(name)
            text = substitute(fallback, decls, _stack)
        out.append(text)
        i = end + 1
    return "".join(out)


# =============================================================================
# 3. Palette: the resolved colours of one layout in one theme
# =============================================================================

COLOUR_ROLES = (
    "bg surface surface-2 line line-strong text muted link link-hover accent hot rule focus "
    "button-bg on-accent header-bg header-text header-muted header-line header-button-line tab "
    "nav-bg nav-text nav-muted panel-bg panel-text panel-muted panel-label panel-row panel-line "
    "panel-tile-bg panel-tile-text footer-bg footer-text footer-muted footer-link footer-line "
    "footer-accent mark-bg mark-text mark-line won-line blank-bg badge-bg badge-text win-bg win-text "
    "rank-bg rank-text rank-1-bg rank-1-text bar-track bar-fill bar-lead score-bg score-text "
    "score-dim score-line team-1 team-2 team-3 team-4 team-5 team-6"
).split()
LEAGUE_HELPERS = ("league-base", "layout-accent-base", "league-dim", "league-lift", "league-tint",
                  "league-wash", "layout-accent-tint", "league-ink")
OTHER_REQUIRED_ROLES = ("bg-image", "scene-image", "scene-image-footer", "team-lift")


_EXPR_PREFIXES = ("color-mix(", "either(")


class Palette:
    """Resolved colours of one layout and theme. `theme` is 'light' or 'dark' (the
    data-theme attribute), or None with prefers_dark=True for the OS-dark path. `custom` is
    custom-colour mode: the <html> carries data-league-colour (stage 4 sets it whenever the
    league sets a colour), so the layouts' [data-league-colour] blocks apply. `fallback` is a
    browser without color-mix(): fallbacks.css's @supports block applies (see cascade_rules)."""

    def __init__(self, layout: str, theme: Optional[str], prefers_dark: bool = False,
                 overrides: Optional[dict] = None, decls: Optional[dict] = None, custom: bool = False,
                 fallback: bool = False):
        self.layout = layout
        self.theme = theme
        self.prefers_dark = prefers_dark
        self.custom = custom
        self.fallback = fallback
        self.decls = decls if decls is not None else cascade(layout, theme, prefers_dark, overrides, custom=custom,
                                                              fallback=fallback)
        self._cache = {}

    @classmethod
    def from_decls(cls, decls: dict, layout: str = "test", theme: str = "light", custom: bool = False) -> "Palette":
        """A palette over an explicit {--st-name: value} dict (tests, experiments)."""
        return cls(layout, theme, decls=dict(decls), custom=custom)

    @property
    def name(self) -> str:
        return self.theme or ("dark" if self.prefers_dark else "light")

    def defined(self, role: str) -> bool:
        return "--st-" + role in self.decls

    def raw(self, role: str) -> Optional[str]:
        return self.decls.get("--st-" + role)

    def paint(self, role: str) -> Optional[Union[Colour, Gradient]]:
        """The role's colour (or Gradient); None when undefined or not resolvable. A string
        starting with `color-mix(` or `either(` is taken as a CSS expression (var(--st-*)
        allowed) instead of a role name, for colours that are not a role (a translucent
        track, a text colour at 80%, "one of these backgrounds")."""
        if role not in self._cache:
            try:
                if role.startswith(_EXPR_PREFIXES):
                    src = role
                elif self.defined(role):
                    src = self.raw(role)
                else:
                    raise UndefinedVar(role)
                self._cache[role] = parse_paint(substitute(src, self.decls))
            except ColourError:
                self._cache[role] = None
        return self._cache[role]

    def text_of(self, role: str) -> Optional[str]:
        """The role's value with var() substituted (for messages and the browser check)."""
        try:
            return substitute(self.raw(role), self.decls) if self.defined(role) else None
        except ColourError:
            return None

    def uses(self, helper: str) -> bool:
        """Does any non-league role read var(--st-<helper>) directly? (Is it used as a fill?)"""
        needle = "--st-" + helper
        return any(needle in v and not k.startswith("--st-league-") for k, v in self.decls.items())


def palette(layout: str, theme: str, overrides: Optional[dict] = None, custom: bool = False) -> Palette:
    """The palette for an explicit data-theme ('light' or 'dark'); `custom` = custom-colour mode."""
    return Palette(layout, theme, False, overrides, custom=custom)


# =============================================================================
# 4. The pairs
# =============================================================================

ROLE_WORDS = {
    "bg": "the page background", "surface": "cards", "surface-2": "shaded rows",
    "text": "text", "muted": "grey text", "link": "links", "link-hover": "hovered links",
    "accent": "big numbers", "hot": "highlight text", "rule": "table rules", "focus": "the focus ring",
    "line": "dividers", "line-strong": "strong outlines", "button-bg": "buttons",
    "on-accent": "button text", "header-bg": "the header", "header-text": "header text",
    "header-muted": "small header text", "header-line": "the header edge",
    "header-button-line": "the theme button ring", "tab": "the active tab underline",
    "nav-bg": "the nav bar", "nav-text": "nav text", "nav-muted": "small nav text",
    "panel-bg": "the next-game panel", "panel-row": "rows in the panel", "panel-text": "panel text",
    "panel-muted": "small panel text", "panel-label": "panel labels", "panel-line": "panel dividers",
    "panel-tile-bg": "the panel tile", "panel-tile-text": "text on the panel tile",
    "footer-bg": "the footer", "footer-text": "footer text", "footer-muted": "small footer text",
    "footer-link": "footer links", "footer-line": "footer dividers", "footer-accent": "the footer accent",
    "mark-bg": "highlighted cells", "mark-text": "text in highlighted cells", "mark-line": "the highlight outline",
    "won-line": "the won-period underline", "badge-bg": "badges", "badge-text": "badge text",
    "win-bg": "WIN badges", "win-text": "WIN badge text", "rank-bg": "rank numbers' background",
    "rank-text": "rank numbers", "rank-1-bg": "the first-place rank background", "rank-1-text": "the first-place rank",
    "bar-track": "bar tracks", "bar-fill": "bars", "bar-lead": "the leader's bar",
    "score-bg": "the score panel", "score-text": "scores", "score-dim": "losing scores",
    "score-line": "score dividers", "league-ink": "white text", "league-color": "the league colour",
    "league-base": "the league colour", "league-dim": "the darkened league colour",
    "league-lift": "the lightened league colour",
}


def _role_word(role: str) -> str:
    if role.startswith(_EXPR_PREFIXES):
        return "a derived colour"
    if role.startswith("team-"):
        return "team colour " + role[5:]
    return ROLE_WORDS.get(role, role.replace("-", " "))


@dataclass(frozen=True)
class Pair:
    """One foreground/background pair. `bg` is a tuple of roles painted bottom to top
    (a translucent role such as panel-row sits on the one before it). kind is text (4.5),
    large (3), ui (3) or decor (reported, never enforced; `required` is an optional target)."""
    fg: str
    bg: tuple
    kind: str
    id: str = ""
    required: Optional[float] = None
    why: str = ""
    when: Optional[str] = None      # only when this league helper is used as a fill
    only: tuple = ()                # only for these layouts (empty = all)
    not_in: tuple = ()              # not for these layouts
    plain: str = ""

    @property
    def enforced(self) -> bool:
        return self.kind != "decor"

    @property
    def need(self) -> Optional[float]:
        return REQUIRED[self.kind] if self.kind in REQUIRED else self.required


def _pair(fg, bg, kind, pid=None, **kw) -> Pair:
    bgs = (bg,) if isinstance(bg, str) else tuple(bg)
    return Pair(fg=fg, bg=bgs, kind=kind, id=pid or "%s/%s" % (fg, bgs[-1]), **kw)


_TEAM_WHY = "team chips never carry information alone (the team name is always beside them)"
_HAIR = "decorative divider; carries no information"


def _v(role: str) -> str:
    return "var(--st-%s)" % role


def _mix(role: str, pct: int, over: str = "transparent") -> str:
    """CSS for `role` at pct% over `over` (a colour or var()); a translucent colour when over is transparent."""
    return "color-mix(in oklab, %s %d%%, %s)" % (_v(role), pct, over)


def _either(*exprs: str) -> str:
    """One of several backgrounds (the same text sits on one OR the other; the worst counts)."""
    return "either(%s)" % ", ".join(exprs)


_LEAD_TRACK = _mix("panel-text", 22)                                   # parts-data.css .st-race__row--lead .st-race__bar
_LS_TINT = "color-mix(in oklab, %s 9%%, %s)" % (_v("panel-text"), _v("panel-bg"))   # --ls-bg of .st-final (basketball, classic)
_LS_BLANK = _mix("panel-text", 8)                                      # .st-final .is-blank cell on that box
_SB_BLANK = "color-mix(in oklab, %s, %s 16%%)" % (_v("score-bg"), _v("score-text"))  # scoreboard .is-blank and blank key
_RINK = _either(_mix("link", 11), _mix("hot", 11))                     # hockey .st-final::before lines behind the text


def build_pairs() -> list:
    """The full pair list. Each comment names the CSS rule that draws the pair, so a
    reviewer can check it (assets/css/parts-*.css, base.css)."""
    P = []
    # page text (base.css: .st-page, a, .st-table, .st-note, .st-card ...)
    for fg in ("text", "muted", "link", "link-hover"):
        for bg in ("bg", "surface", "surface-2"):
            P.append(_pair(fg, bg, "text"))
    for bg in ("surface", "bg", "surface-2"):
        P.append(_pair("accent", bg, "large", why="big numbers (24 px and up)"))
    for bg in ("surface", "bg", "surface-2"):
        P.append(_pair("hot", bg, "text"))
    P += [
        _pair("rule", "surface", "ui"),
        _pair("line-strong", "surface", "decor", required=3.0,
              why="outline of cards and tables and the dotted divider; what is inside them is readable without "
                  "the outline"),
        _pair("focus", "bg", "ui"),
        _pair("focus", "surface", "ui"),
        _pair("line", "surface", "decor", why=_HAIR),
        _pair("on-accent", "button-bg", "text"),
        _pair("button-bg", "bg", "decor", required=3.0,
              why="the label (on-accent on button-bg) identifies the button; the edge is reported for information"),
        # blank-end cells (parts-scores.css .st-line-score .is-blank: blank-bg, text in ls-text / ls-muted).
        # Scoreboard paints its own tile instead (see score-text/blank-tile below).
        _pair("text", ("surface", "blank-bg"), "text", "text/blank-bg", not_in=("scoreboard",),
              why="a blank-end cell (parts-scores.css .is-blank)"),
        _pair("muted", ("surface", "blank-bg"), "text", "muted/blank-bg", not_in=("scoreboard",),
              why="a blank end with an X or an ends row (.st-line-score--ends .is-blank)"),
        # hover rows and buttons
        _pair("text", "line", "text", "text/line:race-hover", only=("scoreboard",),
              why="a hovered race row (parts-data.css a.st-race__row:hover)"),
        _pair("muted", "line", "text", "muted/line:race-hover", only=("scoreboard",),
              why="the sub line of a hovered race row"),
    ]
    # header and nav (parts-shell.css)
    P += [
        _pair("header-text", "header-bg", "text"),
        _pair("header-muted", "header-bg", "text"),
        _pair("nav-text", ("header-bg", "nav-bg"), "text", "nav-text/nav-bg"),
        _pair("nav-muted", ("header-bg", "nav-bg"), "text", "nav-muted/nav-bg"),
        _pair("tab", ("header-bg", "nav-bg"), "ui", "tab/header-bg",
              plain="the active tab underline"),
        _pair("header-button-line", "header-bg", "ui"),
        _pair("header-line", "header-bg", "decor", required=3.0,
              why="decorative edge or accent bar under the header; carries no information"),
        _pair("header-text", ("header-bg", _mix("header-text", 12)), "ui", "header-text/theme-button-hover",
              plain="the theme button's icon when hovered",
              why="the sun/moon icon is a graphic (3:1); parts-shell.css .st-theme-toggle:hover (currentColor 12% over the header)"),
        # parts-shell.css .st-brand__badge: monogram in league-color on a header-text disc
        _pair("league-color", "header-text", "text", "badge-monogram", not_in=("hockey", "classic"),
              plain="the logo monogram",
              why="parts-shell.css .st-brand__badge (colour: --st-league-color on a header-text disc; "
                  "the same colour in both themes); Classic paints it league-ink on league-base"),
        _pair("header-bg", "header-text", "text", "badge-monogram-hockey", only=("hockey",),
              plain="the logo monogram",
              why="Hockey's badge colour is header-bg on a header-text disc (parts-shell.css)"),
        # parts-shell.css [data-layout=scoreboard] .st-brand__tint
        _pair("color-mix(in oklab, var(--st-header-text) 78%, var(--st-league-base))", "header-bg", "large",
              "brand-tint/header-bg", only=("scoreboard",), plain="the last word of the league name",
              why="parts-shell.css .st-brand__tint: header-text 78% with the league colour, 25 px"),
    ]
    # next-game panel (parts-data.css .st-next-game, --ng-*; parts-scores.css .st-final, hero)
    for fg in ("panel-text", "panel-muted", "panel-label"):
        P.append(_pair(fg, "panel-bg", "text"))
        P.append(_pair(fg, ("panel-bg", "panel-row"), "text", "%s/panel-row" % fg))
    P += [
        _pair("panel-tile-text", ("panel-bg", "panel-tile-bg"), "text", "panel-tile-text/panel-tile-bg",
              plain="text on the panel's tile",
              why="parts-data.css .st-game-row__surface--tile/--tag on the panel (--ng-tile-bg)"),
        _pair("panel-tile-text", ("panel-bg", "panel-row", "panel-tile-bg"), "text", "panel-tile-text/tile-on-row",
              plain="text on the panel's tile",
              why="the same tile, sitting on its translucent game row (panel-row) on the panel"),
        _pair("panel-line", "panel-bg", "decor", why=_HAIR),
        # the final panel / hero card in Basketball and Classic: line score in an inset box
        _pair("panel-text", _LS_TINT, "text", "panel-text/ls-box", only=("basketball", "classic"),
              plain="text in the final panel's score box",
              why="parts-scores.css :is(basketball, classic) .st-final: --ls-bg is panel-text 9% over panel-bg"),
        _pair("panel-muted", _LS_TINT, "text", "panel-muted/ls-box", only=("basketball", "classic"),
              plain="small text in the final panel's score box",
              why="same box: --ls-muted (loser rows, ends, column heads)"),
        _pair("panel-text", ("panel-bg", _LS_TINT, _LS_BLANK), "text", "panel-text/ls-box-blank",
              only=("classic",), plain="a blank cell in the final panel's score box",
              why="parts-scores.css .st-final .is-blank (curling's blank end, shown by Classic): panel-text 14% "
                  "over the score box"),
        _pair("panel-muted", ("panel-bg", _LS_TINT, _LS_BLANK), "text", "panel-muted/ls-box-blank",
              only=("classic",), plain="small text in a blank cell of the final panel's score box",
              why="same cell with --ls-muted text (an ends row: .st-line-score--ends tbody td)"),
        # the hero card's board look (every layout) and Scoreboard's final panel
        _pair(_mix("panel-text", 80), "panel-bg", "text", "panel-text-80/panel-bg", plain="the losing team's name",
              why="parts-scores.css .st-final__head--board .st-final__team:not(.is-winner) .st-final__name "
                  "(panel-text at opacity .8)"),
        _pair("panel-muted", "score-bg", "text", "panel-muted/score-bg", not_in=("slopitch", "curling"),
              plain="a period tile's label",
              why="parts-scores.css .st-period-tile__label on the tile (score-bg), hero card of a quarters or "
                  "periods sport (not Slo-pitch or Curling, which have no period tiles)"),
    ]
    # footer (parts-shell.css)
    for fg in ("footer-text", "footer-muted", "footer-link"):
        P.append(_pair(fg, "footer-bg", "text"))
    P += [
        _pair("footer-accent", "footer-bg", "ui"),
        _pair("footer-line", "footer-bg", "decor", why=_HAIR),
        _pair("score-text", "footer-bg", "text", "score-text/footer-bg", only=("scoreboard",),
              plain="the ticker's status tag",
              why="parts-shell.css .st-ticker__tag (score-text on the ticker strip, footer-bg)"),
    ]
    # marks, badges, ranks (parts-scores.css .is-mark, .st-legend__key--mark/--limit; base.css .st-badge)
    P += [
        _pair("mark-text", ("surface", "mark-bg"), "text", "mark-text/mark-bg", not_in=("scoreboard",)),
        _pair("mark-text", "surface", "text", "mark-text/surface", not_in=("scoreboard",),
              why="a mark drawn with text and no tint (Slo-pitch's circled number, the underlined legend key)"),
        _pair("mark-line", "surface", "ui", not_in=("scoreboard",),
              why="the outline of a stolen end or run-limit inning against the card (it carries the meaning "
                  "together with the text colour)"),
        _pair("mark-line", ("surface", "mark-bg"), "ui", "mark-line/mark-bg", not_in=("scoreboard",),
              why="the same outline against the tint it encloses"),
        _pair("mark-line", "score-bg", "ui", "mark-line/score-bg", only=("scoreboard",),
              why="parts-scores.css [scoreboard] .st-line-score td.is-mark: 2 px outline on the black digit tile"),
        _pair("won-line", "surface", "ui", only=("curling", "hockey", "slopitch"),
              why="the won-period underline on the card surface (parts-scores.css); Basketball and Classic cards underline in `accent` (covered by accent/surface), Scoreboard draws it elsewhere"),
        _pair("won-line", "panel-bg", "ui", "won-line/panel-bg", only=("basketball", "classic"),
              why="the underline on the coloured final panel"),
        _pair("won-line", "score-bg", "ui", only=("scoreboard",),
              why="the underline on Scoreboard's black digit tiles"),
        _pair("badge-text", ("surface", "badge-bg"), "text", "badge-text/badge-bg"),
        _pair("win-text", ("surface", "win-bg"), "text", "win-text/win-bg"),
        _pair("rank-text", ("surface", "rank-bg"), "text", "rank-text/rank-bg"),
        _pair("rank-1-text", ("surface", "rank-1-bg"), "text", "rank-1-text/rank-1-bg"),
        _pair("score-text", "score-bg", "text"),
        _pair("score-dim", "score-bg", "text"),
        _pair("score-line", "score-bg", "decor", why=_HAIR),
        _pair("panel-text", "score-bg", "text", "panel-text/score-bg", only=("scoreboard",),
              plain="the total column", why="parts-scores.css [scoreboard] .st-line-score td.st-line-score__total"),
        _pair("score-text", "panel-bg", "text", "score-text/panel-bg", only=("scoreboard",),
              plain="the dates and ranks on the black bars",
              why="parts-data.css [scoreboard] .st-next-game__date, .st-race__row--lead .st-race__rank, "
                  "parts-scores.css [scoreboard] .st-roster__link (all on panel-bg)"),
        _pair("score-text", _SB_BLANK, "text", "score-text/blank-tile", only=("scoreboard",),
              plain="a blank end's tile", why="parts-scores.css [scoreboard] .is-blank: the tile is score-bg with "
              "score-text 16% mixed in"),
        _pair("score-dim", _SB_BLANK, "text", "score-dim/blank-tile", only=("scoreboard",),
              plain="a blank end's dimmed tile text", why="same tile with the ends-row text (score-dim)"),
        _pair("bar-fill", "bar-track", "ui"),
        _pair("bar-lead", ("panel-bg", _LEAD_TRACK), "ui", "bar-lead/lead-track", only=("scoreboard",),
              why="Scoreboard's race draws the leader's bar on the lead row (panel-bg with a panel-text "
                  "track at 22%, parts-data.css)"),
        _pair("bar-lead", "bar-track", "ui", not_in=("scoreboard",)),
        _pair("accent", ("either(%s, %s)" % (_v("surface"), _v("surface-2")),), "text", "accent-small/slopitch-total",
              only=("slopitch",), plain="the winner's total",
              why="parts-scores.css [slopitch] tr.is-winner td.st-line-score__total: accent at 17 px (card) on "
                  "surface, 24 px (full) on surface-2"),
        # Hockey's rink lines sit behind the final panel's text (parts-scores.css [hockey] .st-final::before)
        _pair("muted", ("surface", _RINK), "text", "muted/rink", only=("hockey",),
              plain="small text over the rink lines",
              why="parts-scores.css [hockey] .st-final::before: link 24% and hot 30% lines behind the text"),
        _pair(_mix("text", 80), ("surface", _RINK), "text", "text-80/rink", only=("hockey",),
              plain="the losing team's name",
              why="parts-scores.css [hockey] .st-final__team:not(.is-winner) .st-final__name (text at .8, over the lines)"),
    ]
    # team colours
    for n in range(1, 7):
        for bg in ("surface", "bg"):
            P.append(_pair("team-%d" % n, bg, "decor", required=3.0, why=_TEAM_WHY))
    # league colour: white text on the colour and its derived fills
    P += [
        _pair("league-ink", "league-base", "text", plain="white text on it"),
        _pair("league-ink", "league-dim", "text", when="league-dim",
              plain="white text on the darkened version of it"),
        _pair("league-ink", "league-lift", "text", when="league-lift",
              plain="white text on the lightened version of it"),
    ]
    return P


PAIRS = build_pairs()

# Pairs the design accepts although they miss their target. Keyed on layout, theme (None =
# both) and pair id. Reported in docs/contrast.md under "Accepted exceptions".
ACCEPTED_EXCEPTIONS = [
    {"layout": "curling", "theme": "light", "pair": "header-line/header-bg",
     "reason": "The curling header's red line under the ink header (house red #C8102E on #0E2233, "
               "2.76:1) is the approved decorative edge. It carries no information (nothing is "
               "written in it, and the page is readable without it), so it is kept as drawn in "
               "the approved mockup. The dark theme's lifted red passes."},
]


# A header gradient can end in scenery that no text sits on (basketball: hills over the last
# stops). {layout: fraction of the header height below which text can sit}. Empty = the strict
# rule: text and UI must pass on EVERY colour stop. Adding an entry is a design decision;
# the colour at the edge of the zone (interpolated between its two stops) is checked as well.
GRADIENT_TEXT_ZONE: dict = {"basketball": 0.76}  # text sits in the top 76%; the hills scene covers the rest


@dataclass
class Result:
    layout: str
    theme: str
    pair: Pair
    status: str                 # pass FAIL decor decor-miss accepted skip
    ratio: Optional[float] = None
    need: Optional[float] = None
    fg_hex: str = ""
    bg_hex: str = ""
    worst: str = ""             # which gradient stop / layer was worst, if there is more than one
    note: str = ""              # why skipped / the exception reason
    missing: tuple = ()         # undefined roles that made it skip


def _zone_stops(stops: tuple, zone: Optional[float]) -> list:
    """[(colour, pos)] of a gradient limited to positions <= zone, plus the interpolated
    colour at the zone edge. Without a zone, all stops."""
    if zone is None:
        return list(stops)
    kept = [(c, p) for c, p in stops if p is None or p <= zone + 1e-9]
    after = [(c, p) for c, p in stops if p is not None and p > zone + 1e-9]
    if kept and after and kept[-1][1] is not None and kept[-1][1] < zone:
        (c0, p0), (c1, p1) = kept[-1], after[0]
        t = (zone - p0) / (p1 - p0)
        edge = Colour(*(getattr(c0, ch) * (1 - t) + getattr(c1, ch) * t for ch in "rgba"))
        kept.append((edge, zone))
    return kept


def backdrops(pal: Palette, roles: tuple, zone: Optional[float] = None) -> Optional[list]:
    """The opaque backgrounds a pair's foreground can sit on: the `roles` painted bottom to
    top, a gradient fanning out into one backdrop per colour stop (limited to `zone`, see
    GRADIENT_TEXT_ZONE) and an `either(...)` into one per alternative. [(label, Colour)], or
    None if a role is undefined. The first role must be opaque."""
    cur = [("", None)]
    for role in roles:
        paint = pal.paint(role)
        if paint is None:
            return None
        nxt = []
        for label, base in cur:
            if isinstance(paint, Gradient):
                stops = list(paint.stops) if paint.either else _zone_stops(paint.stops, zone)
                for i, (c, pos) in enumerate(stops):
                    where = "%s %d of %d (%s%s)" % (
                        "case" if paint.either else "stop", i + 1, len(stops), to_hex(c),
                        " @%d%%" % round(pos * 100) if pos is not None else "")
                    nxt.append(((label + "; " if label else "") + where,
                                composite(c, base) if base else _need_opaque(c)))
            else:
                nxt.append((label, composite(paint, base) if base else _need_opaque(paint)))
        cur = nxt
    return cur


def _need_opaque(c: Colour) -> Colour:
    if c.a < 1:
        raise ColourError("the bottom layer of a pair must be opaque (got %s)" % to_hex(c))
    return c


def evaluate_pair(pal: Palette, pair: Pair) -> Result:
    """Measure one pair on one palette."""
    res = Result(pal.layout, pal.name, pair, "skip", need=pair.need)
    if (pair.only and pal.layout not in pair.only) or pal.layout in pair.not_in:
        res.note = "not used in this layout"
        return res
    missing = tuple(r for r in (pair.fg,) + pair.bg if pal.paint(r) is None)
    if missing:
        res.missing = missing
        res.note = "undefined: " + ", ".join("--st-" + r for r in missing)
        return res
    fg = pal.paint(pair.fg)
    if isinstance(fg, Gradient):
        res.note = "foreground is a gradient"
        return res
    if fg.a <= 0:
        res.note = "transparent (nothing drawn)"
        return res
    if pair.when and not pal.uses(pair.when):
        res.note = "--st-%s is not used as a fill in this layout" % pair.when
        return res
    worst = None
    layers = backdrops(pal, pair.bg, GRADIENT_TEXT_ZONE.get(pal.layout))
    for label, bg in layers:
        f = composite(fg, bg)
        r = contrast_ratio(f, bg)
        if worst is None or r < worst[0]:
            worst = (r, label, f, bg)
    res.ratio, res.worst, res.fg_hex, res.bg_hex = worst[0], worst[1], to_hex(worst[2]), to_hex(worst[3])
    if len(layers) == 1:
        res.worst = ""
    need = pair.need
    if pair.enforced:
        res.status = "pass" if res.ratio + 1e-9 >= need else "FAIL"
    elif need is None:
        res.status = "decor"
    else:
        res.status = "decor" if res.ratio + 1e-9 >= need else "decor-miss"
    if res.status in ("FAIL", "decor-miss"):
        for ex in ACCEPTED_EXCEPTIONS:
            if ex["layout"] == pal.layout and ex["pair"] == pair.id and ex["theme"] in (None, pal.name):
                res.status, res.note = "accepted", ex["reason"]
    if not res.note and pair.why:
        res.note = pair.why
    return res


def evaluate_palette(pal: Palette) -> list:
    return [evaluate_pair(pal, p) for p in PAIRS]


# =============================================================================
# 5. League colour examples (also stage 4's data check)
# =============================================================================

@dataclass
class Problem:
    """One contrast failure caused by a league colour setting."""
    layout: str
    theme: str
    pair: str
    ratio: float
    required: float
    message: str
    setting: str = ""


_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")


def _norm_hex(value: Optional[str], what: str) -> Optional[str]:
    if value is None:
        return None
    if not _HEX6.match(value.strip()):
        raise ValueError("league.yml %s must be a #RRGGBB colour, got %r" % (what, value))
    return value.strip().upper()


def league_overrides(hex_: str, hex_dark: Optional[str] = None) -> dict:
    """The inline-style custom properties a league's colour setting becomes on <html>
    (stage 4 also sets the data-league-colour attribute there: custom-colour mode)."""
    o = {"--st-league-color": hex_}
    if hex_dark:
        o["--st-league-color-dark"] = hex_dark
    return o


def _shift(hex_: str, toward: str, amount: float = 0.12) -> str:
    c = mix_colours(parse_colour(hex_), parse_colour(toward), 100 * (1 - amount), 100 * amount)
    return to_hex(c)


def _ratio_for(layout: str, theme: str, pair_id: str, overrides: dict) -> Optional[float]:
    for r in evaluate_palette(palette(layout, theme, overrides, custom=True)):
        if r.pair.id == pair_id:
            return r.ratio
    return None


def check_league_colour(layout: str, hex: str, hex_dark: Optional[str] = None) -> list:
    """Stage 4's data check. Run every pair for `layout` in custom-colour mode (the league's
    colour inline as --st-league-color, `hex_dark` as --st-league-color-dark if given, and the
    layout's [data-league-colour] blocks active), in both themes. Returns a list of Problem
    (empty = fine): one per foreground role and theme (at its worst background), for enforced
    pairs that pass with the layout's own colours and fail with the league's. That includes
    "white text on the colour" (league-ink on league-base, and on league-dim / league-lift where
    the layout uses them as fills). Pairs that already fail with the layout's own colours are
    the design's business, reported by the main run, not the league's.
    Each Problem.message names the league.yml setting (`colour` or `colour_dark`) and says
    whether to pick a lighter or a darker colour."""
    hex = _norm_hex(hex, "colour")
    hex_dark = _norm_hex(hex_dark, "colour_dark")
    over = league_overrides(hex, hex_dark)
    problems = []
    for theme in THEMES:
        base = {r.pair.id: r for r in evaluate_palette(palette(layout, theme))}
        worst = {}      # (foreground role) -> the lowest-ratio failure, so one fix is one message
        for r in evaluate_palette(palette(layout, theme, over, custom=True)):
            if r.status != "FAIL" or base[r.pair.id].status == "FAIL":
                continue
            if r.pair.fg not in worst or r.ratio < worst[r.pair.fg].ratio:
                worst[r.pair.fg] = r
        for r in worst.values():
            problems.append(_make_problem(layout, theme, r, over, hex, hex_dark))
    return problems


def _responsible(layout, theme, r, over, hex_, hex_dark):
    """(setting name, its value, direction word) for the league input that fixes this pair:
    `colour` in the light theme; in the dark theme `colour_dark` if the league sets it, else
    `colour` (the value in use; the advice is then to set `colour_dark`). The direction is found
    by moving that value 12% toward white and toward black and seeing which raises the ratio."""
    if theme == "light":
        setting, prop, value = "colour", "--st-league-color", hex_
    else:
        setting = "colour_dark" if hex_dark else "colour"
        prop, value = "--st-league-color-dark", hex_dark or hex_
    ratios = {}
    for toward in ("#FFFFFF", "#000000"):
        o = dict(over)
        o[prop] = _shift(value, toward)
        ratios[toward] = _ratio_for(layout, theme, r.pair.id, o)
    if ratios["#FFFFFF"] is None or ratios["#000000"] is None:
        return setting, value, "darker"
    return setting, value, "lighter" if ratios["#FFFFFF"] > ratios["#000000"] else "darker"


def _make_problem(layout, theme, r, over, hex_, hex_dark) -> Problem:
    setting, value, direction = _responsible(layout, theme, r, over, hex_, hex_dark)
    shown = floor2(r.ratio)
    plain = r.pair.plain or "%s on %s" % (_role_word(r.pair.fg), _role_word(r.pair.bg[-1]))
    need = r.need
    if theme == "light":
        fix = "Pick a %s colour." % direction
    elif hex_dark:
        fix = "Change colour_dark: pick a %s one." % direction
    else:
        fix = "Set colour_dark to a %s colour (the dark theme uses colour until you do)." % direction
    msg = "league.yml %s %s: %s is %s:1 in the %s theme (needs %s:1). %s" % (
        setting, value, plain, ("%.2f" if round(shown, 1) >= need else "%.1f") % shown, theme,
        ("%g" % need), fix)
    return Problem(layout, theme, r.pair.id, round(r.ratio, 3), need, msg, setting)


def alt_league_colours() -> list:
    """[{name, hex, expected_fail}] from scripts/design_system/sample.py (ALT_LEAGUE_COLOURS).
    `expected_fail` colours are the deliberate hard cases (white text on them fails AA)."""
    sys.path.insert(0, str(ROOT))
    try:
        from scripts.design_system.sample import ALT_LEAGUE_COLOURS
        return [{"name": c["name"], "hex": c["hex"], "expected_fail": bool(c.get("expected_fail"))}
                for c in ALT_LEAGUE_COLOURS]
    except Exception:       # keep the checker usable if the sample module is missing
        return [{"name": n, "hex": h, "expected_fail": n == "Gold"} for n, h in (
            ("Navy", "#1D3A6E"), ("Deep red", "#9E1B32"), ("Forest green", "#2F6B3A"), ("Gold", "#C98A12"))]


# =============================================================================
# 6. Dark-block parity
# =============================================================================

_NOT_LIGHT = ':not([data-theme="light"])'
_CUSTOM_ATTR = "[data-league-colour]"


def _norm_value(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip()


def dark_parity_errors(rules: list, name: str) -> list:
    """Check one stylesheet's dark blocks. (1) Each `@media (prefers-color-scheme: dark)`
    block (selector `X:not([data-theme="light"])`) must declare exactly what the `X[data-theme="dark"]`
    block does (whitespace aside). (2) For the custom-colour blocks (X ends in
    `[data-league-colour]`): the dark blocks must restate every property the light block `X` sets,
    because the light block, which comes after the normal dark block and has the same specificity,
    would otherwise win in dark mode. Returns error strings."""
    media, explicit, light, errors = {}, {}, {}, []
    not_light = _NOT_LIGHT.replace(" ", "")
    for rule in rules:
        sel = rule.selector.replace(" ", "")
        decls = {k: _norm_value(v) for k, v in rule.decls.items()}
        if rule.media and rule.media.replace(" ", "") == "(prefers-color-scheme:dark)" and sel.endswith(not_light):
            media.setdefault(sel[:-len(not_light)], {}).update(decls)
        elif rule.media is None and sel.endswith('[data-theme="dark"]'):
            explicit.setdefault(sel[:-len('[data-theme="dark"]')], {}).update(decls)
        elif rule.media is None and sel.endswith(_CUSTOM_ATTR):
            light.setdefault(sel, {}).update(decls)
    for base in sorted(set(media) | set(explicit)):
        a, b = media.get(base), explicit.get(base)
        if a is None or b is None:
            errors.append("%s: the dark block for %s exists only as %s" % (
                name, base, "[data-theme=\"dark\"]" if a is None else "the prefers-color-scheme media query"))
            continue
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                errors.append("%s: dark blocks of %s differ at %s: media query has %s, "
                              "[data-theme=\"dark\"] has %s" % (name, base, k, a.get(k, "(missing)"), b.get(k, "(missing)")))
    for base, props in sorted(light.items()):
        if not props:
            continue
        dark = media.get(base)
        if dark is None:
            dark = explicit.get(base)
        if dark is None:
            errors.append("%s: %s sets %s but there is no dark custom block for it (the dark blocks must restate "
                          "every property of the light custom block)" % (name, base, ", ".join(sorted(props))))
            continue
        for k in sorted(set(props) - set(dark)):
            errors.append("%s: the dark custom blocks of %s do not restate %s, which the light custom block "
                          "sets: in dark mode the light value would win" % (name, base, k))
    return errors


def check_dark_parity(css_files: Optional[list] = None, layouts: Optional[list] = None) -> list:
    """`dark_parity_errors` for tokens.css and every layout file."""
    if css_files is None:
        css_files = [CSS_DIR / "tokens.css"] + [LAYOUT_DIR / (i + ".css") for i in (layouts or layout_ids())]
    errors = []
    for f in css_files:
        name = os.path.relpath(str(f), ROOT) if str(f).startswith(str(ROOT)) else str(f)
        errors += dark_parity_errors(load_rules(f), name)
    return errors


def check_dark_equivalence(layout: str) -> list:
    """The resolved palette via the OS preference equals the one via data-theme="dark"
    (and the same for light), with and without custom-colour mode. Returns error strings."""
    errs = []
    for custom in (False, True):
        for a, b, label in ((Palette(layout, None, True, custom=custom), Palette(layout, "dark", custom=custom), "dark"),
                            (Palette(layout, None, False, custom=custom), Palette(layout, "light", custom=custom), "light")):
            for k in sorted(set(a.decls) | set(b.decls)):
                if a.decls.get(k) != b.decls.get(k):
                    errs.append("%s: %s differs between the OS preference and data-theme=\"%s\"%s" % (
                        layout, k, label, " (data-league-colour on)" if custom else ""))
    return errs


# =============================================================================
# 7. Token lint
# =============================================================================

@dataclass
class Finding:
    level: str      # ERROR or WARNING
    where: str      # file:line or file
    message: str


# Custom properties set outside CSS: by stage 4 (inline style from league.yml / teams.yml) or
# by class rules; reading them without a definition is fine. (There is no second league colour:
# --st-layout-accent is the layout's own, set in the layout file, never by a league.)
INLINE_INPUTS = {"--st-league-color", "--st-league-color-dark", "--st-team-hex"}

# Raw colour in a parts file
_RAW_PATTERNS = [
    (re.compile(r"#[0-9a-fA-F]{3,8}\b"), "hex colour"),
    (re.compile(r"%23[0-9a-fA-F]{3,8}\b"), "hex colour in a data URI"),
    (re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\s*\("), "colour function"),
    (re.compile(r"\b(?:fill|stroke|stop-color|flood-color)\s*=\s*['\"]?(?:white|black)\b", re.I), "named colour in an SVG attribute"),
    (re.compile(r"(?<![\w.#-])(?:white|black|red|green|blue|gray|grey|yellow|orange|purple|navy|silver|gold)(?![\w-])", re.I), "named colour"),
]


def find_var_reads(text: str) -> list:
    """[(name, offset, optional)] for every var(--name[, fallback]) in `text`. `optional` is
    True if the read has a fallback or sits inside another var()'s fallback."""
    out = []

    def scan(s: str, base: int, in_fallback: bool):
        i = 0
        while True:
            m = re.search(r"(?<![\w-])var\(", s[i:])
            if not m:
                return
            start = i + m.start()
            try:
                end = _match_paren(s, start + 3)
            except ColourError:
                return
            inner = s[start + 4:end]
            parts = split_top(inner)
            name = parts[0].strip()
            has_fb = len(parts) > 1
            out.append((name, base + start, in_fallback or has_fb))
            if has_fb:
                fb_text = ",".join(parts[1:])
                fb_off = base + start + 4 + len(parts[0]) + 1
                scan(fb_text, fb_off, True)
            i = end + 1

    scan(text, 0, False)
    return out


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def lint_tokens(css_dir: Path = CSS_DIR) -> list:
    """Token lint over assets/css: (1) roles read but undefined for some layout (ERROR),
    (2) contract roles a layout leaves out (ERROR), (3) roles defined in layouts but read
    nowhere (WARNING), (4) raw colours in base.css / parts-*.css (ERROR)."""
    findings = []
    css_dir = Path(css_dir)
    files = sorted(css_dir.glob("*.css")) + sorted((css_dir / "layouts").glob("*.css"))
    rel = lambda p: os.path.relpath(str(p), ROOT) if str(p).startswith(str(ROOT)) else str(p)
    layouts = sorted(p.stem for p in (css_dir / "layouts").glob("*.css"))

    # --- what is defined where
    global_defined = set(INLINE_INPUTS)
    for f in sorted(css_dir.glob("*.css")):
        for rule in load_rules(f):
            global_defined.update(rule.decls)
    defined = {}
    for lid in layouts:
        names = set(global_defined)
        files_for = [css_dir / "tokens.css", css_dir / "layouts" / (lid + ".css")]
        for theme, osdark in (("light", False), ("dark", False), (None, True), (None, False)):
            names.update(cascade(lid, theme, osdark, css_files=files_for))
        layout_names = set()
        for rule in load_rules(css_dir / "layouts" / (lid + ".css")):
            layout_names.update(rule.decls)
        defined[lid] = (names, layout_names)

    # --- every read
    reads = []                  # (name, file, line, optional)
    for f in files:
        text = strip_comments(f.read_text(encoding="utf-8"))
        for name, off, optional in find_var_reads(text):
            if name.startswith("--st-"):
                reads.append((name, rel(f), _line_of(text, off), optional))
    read_names = {r[0] for r in reads}

    # (1) read but undefined
    seen = {}
    for name, f, line, optional in reads:
        if optional:
            continue
        missing = [lid for lid in layouts if name not in defined[lid][0]]
        if missing:
            seen.setdefault((name, tuple(missing)), (f, line))
    for (name, missing), (f, line) in sorted(seen.items()):
        findings.append(Finding("ERROR", "%s:%d" % (f, line),
                                "%s is read here with no fallback but is not defined for layout%s %s"
                                % (name, "s" if len(missing) > 1 else "", ", ".join(missing))))

    # (2) contract roles a layout leaves out (tokens.css supplies a few defaults)
    contract = ["--st-" + r for r in COLOUR_ROLES + list(OTHER_REQUIRED_ROLES)]
    token_names = set()
    for rule in load_rules(css_dir / "tokens.css"):
        token_names.update(rule.decls)
    for lid in layouts:
        absent = [c for c in contract if c not in defined[lid][1] and c not in token_names]
        if absent:
            findings.append(Finding("ERROR", rel(css_dir / "layouts" / (lid + ".css")),
                                    "contract roles not defined: " + ", ".join(absent)))

    # (3) defined in layouts, read nowhere
    unused = {}
    for lid in layouts:
        for name in defined[lid][1]:
            if name.startswith("--st-") and name not in read_names and name not in INLINE_INPUTS:
                unused.setdefault(name, []).append(lid)
    for name in sorted(unused):
        findings.append(Finding("WARNING", "layouts/*.css",
                                "%s is defined (%s) but read nowhere in assets/css" % (name, ", ".join(unused[name]))))

    # (4) raw colours in the parts
    for f in sorted(css_dir.glob("parts-*.css")) + [css_dir / "base.css"]:
        if not f.exists():
            continue
        text = strip_comments(f.read_text(encoding="utf-8"))
        for ln, line in enumerate(text.splitlines(), 1):
            for rx, what in _RAW_PATTERNS:
                for m in rx.finditer(line):
                    if rx is _RAW_PATTERNS[-1][0] and _is_selector_or_ident(line, m):
                        continue
                    findings.append(Finding("ERROR", "%s:%d" % (rel(f), ln),
                                            "raw colour (%s) `%s`: use a --st-* role" % (what, m.group().strip())))
    return findings


def _is_selector_or_ident(line: str, m: re.Match) -> bool:
    """A bare word like `red` that is part of a class name, a custom-property name or a
    quoted font name rather than a colour value."""
    before, after = line[:m.start()], line[m.end():]
    if before.rstrip().endswith(("--", ".", "#", "$")) or after.lstrip().startswith(":"):
        return True
    return ("{" not in before and ":" not in before)


# =============================================================================
# 8. Checking everything
# =============================================================================

@dataclass
class Report:
    results: dict = field(default_factory=dict)       # (layout, theme) -> [Result]
    league: dict = field(default_factory=dict)        # (layout, colour name, hex) -> [Problem]
    parity: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    layouts: list = field(default_factory=list)
    colours: list = field(default_factory=list)       # [{name, hex, expected_fail}]
    fallback: Optional["FallbackReport"] = None       # browsers without color-mix(); None = not run

    @property
    def failures(self) -> list:
        return [r for rs in self.results.values() for r in rs if r.status == "FAIL"]

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.level == "ERROR"]

    def league_problems(self, colour: dict) -> list:
        return [p for lid in self.layouts for p in self.league.get((lid, colour["name"], colour["hex"]), [])]

    @property
    def league_failures(self) -> list:
        """(layout, colour name, Problem) for example colours that must pass but do not."""
        return [(lid, c["name"], p) for c in self.colours if not c["expected_fail"]
                for lid in self.layouts for p in self.league.get((lid, c["name"], c["hex"]), [])]

    @property
    def expected_fail_passes(self) -> list:
        """Example colours marked expected_fail that nevertheless raise no problem anywhere."""
        return [c["name"] for c in self.colours if c["expected_fail"] and self.league and not self.league_problems(c)]

    @property
    def ok(self) -> bool:
        return not (self.failures or self.parity or self.errors or self.league_failures or self.expected_fail_passes
                    or (self.fallback is not None and not self.fallback.ok))


# =============================================================================
# 8b. Browsers without color-mix(): assets/css/fallbacks.css
# =============================================================================

@dataclass
class FallbackReport:
    """The whole pair list run on every layout x theme x {default, data-league-colour attribute}
    with fallbacks.css's `@supports not (color: color-mix(...))` block active and color-mix()
    treated as missing (the league colour itself is not set: such a browser shows the layout's
    default look)."""
    results: dict = field(default_factory=dict)     # (layout, theme, custom) -> [Result]
    errors: list = field(default_factory=list)      # color-mix still reachable, OS/data-theme mismatch, stale file ...
    layouts: list = field(default_factory=list)

    @property
    def failures(self) -> list:
        return [r for rs in self.results.values() for r in rs if r.status == "FAIL"]

    @property
    def n_pairs(self) -> int:
        return sum(1 for rs in self.results.values() for r in rs if r.status != "skip")

    @property
    def ok(self) -> bool:
        return not (self.failures or self.errors)


def color_mix_reachable(pal: Palette) -> list:
    """Messages for every --st-* property that still resolves through color-mix() in this
    palette (a browser without color-mix() would drop it)."""
    out = []
    for name, raw in sorted(pal.decls.items()):
        if not name.startswith("--st-"):
            continue
        try:
            text = raw if "color-mix(" in raw else substitute(raw, pal.decls)
        except ColourError:
            continue
        if "color-mix(" in text:
            out.append("%s %s%s: %s still resolves through color-mix(), which this browser does not have "
                       "(run python scripts/build_css_fallbacks.py)" % (
                           pal.layout, pal.name, " (data-league-colour)" if pal.custom else "", name))
    return out


def check_fallbacks(layouts: Optional[list] = None, freshness: bool = True) -> FallbackReport:
    """Run the pairs in fallback mode (see FallbackReport). With `freshness`, also report a stale
    assets/css/fallbacks.css and a color-mix() in the parts that has no override."""
    rep = FallbackReport(layouts=layouts or layout_ids())
    if not FALLBACKS_PATH.exists():
        rep.errors.append("assets/css/fallbacks.css does not exist: run python scripts/build_css_fallbacks.py")
        return rep
    if freshness and layouts is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from scripts import build_css_fallbacks as gen
        rep.errors += gen.problems()
    # the team colour rule is a class rule, outside the cascade model: look at it directly
    team = [r for r in load_rules(FALLBACKS_PATH) if r.selector == ".st-team--custom"]
    if not team or "color-mix(" in team[-1].decls.get("--st-team", "color-mix("):
        rep.errors.append("fallbacks.css has no color-mix-free `.st-team--custom { --st-team }` rule")
    for lid in rep.layouts:
        for custom in (False, True):
            pals = {}
            for theme in THEMES:
                pal = Palette(lid, theme, custom=custom, fallback=True)
                pals[theme] = pal
                rep.errors += color_mix_reachable(pal)
                rep.results[(lid, theme, custom)] = evaluate_palette(pal)
            for osp, attr, label in ((Palette(lid, None, True, custom=custom, fallback=True), pals["dark"], "dark"),
                                     (Palette(lid, None, False, custom=custom, fallback=True), pals["light"], "light")):
                for k in sorted(set(osp.decls) | set(attr.decls)):
                    if osp.decls.get(k) != attr.decls.get(k):
                        rep.errors.append("%s: %s differs between the OS preference and data-theme=\"%s\" in fallback mode%s" % (
                            lid, k, label, " (data-league-colour on)" if custom else ""))
    return rep


def fallback_summary(rep: FallbackReport) -> str:
    return ("Browsers without color-mix() (assets/css/fallbacks.css active, %d layouts x 2 themes x default / "
            "data-league-colour): %d pairs checked, %d fail, %d problem(s)" % (
                len(rep.layouts), rep.n_pairs, len(rep.failures), len(rep.errors)))


def run_checks(layouts: Optional[list] = None, with_league: bool = True, with_fallbacks: bool = True) -> Report:
    """Run the pairs, the parity check, the league colour examples, the lint and (with_fallbacks) the
    pairs again for browsers without color-mix()."""
    rep = Report(layouts=layouts or layout_ids())
    rep.colours = alt_league_colours()
    for lid in rep.layouts:
        for theme in THEMES:
            rep.results[(lid, theme)] = evaluate_palette(palette(lid, theme))
        rep.parity += check_dark_equivalence(lid)
        if with_league:
            for c in rep.colours:
                rep.league[(lid, c["name"], c["hex"])] = check_league_colour(lid, c["hex"])
    rep.parity += check_dark_parity(layouts=rep.layouts)
    rep.findings = lint_tokens()
    if with_fallbacks:
        rep.fallback = check_fallbacks(layouts)
    return rep


# =============================================================================
# 9. docs/contrast.md
# =============================================================================

def _fmt_ratio(r: Optional[float]) -> str:
    return "" if r is None else "%.2f" % floor2(r)


def _status_label(r: Result) -> str:
    return {"pass": "pass", "FAIL": "**FAIL**", "decor": "decor", "decor-miss": "decor, below target",
            "accepted": "accepted", "skip": "skipped"}[r.status]


def _kind_label(p: Pair) -> str:
    return {"text": "text 4.5", "large": "large 3", "ui": "ui 3"}.get(p.kind, "decor")


def _need_label(r: Result) -> str:
    return "" if r.need is None else "%g" % r.need


def render_markdown(rep: Report) -> str:
    L = []
    add = L.append
    add("<!-- GENERATED by scripts/check_contrast.py. Do not edit by hand: run `python scripts/check_contrast.py`. -->")
    add("")
    add("# Contrast report")
    add("")
    add("*Generated by `scripts/check_contrast.py` from `assets/css/tokens.css` and `assets/css/layouts/*.css`. "
        "Never edit this file by hand; change a layout and run the script again.*")
    add("")
    add("## How to read this")
    add("")
    add("* Every colour role is resolved the way a browser does it: every rule that matches the element "
        "(tokens, the layout, the dark block, and with a league colour the layout's `[data-league-colour]` "
        "blocks) is applied in order of specificity, then source order (var() with fallbacks, `color-mix()` "
        "in oklab, gradients). Translucent colours are composited over what they sit on before they are "
        "measured. A gradient is measured on every colour stop and the worst stop is shown; a text colour "
        "that sits on one of several backgrounds is measured on each and the worst is shown.")
    add("* **text** pairs need 4.5:1, **large** (24 px and up, or 18.66 px bold) and **ui** (borders of "
        "controls, the focus ring, bar fills, the outline of a marked cell, which carry meaning) need 3:1 "
        "(WCAG 2.1 AA).")
    add("* **decor** pairs are reported but never fail the run. `decor, below target` means a decorative "
        "pair (team chips, dividers, header edge) is below the 3:1 a meaningful one would need; the "
        "reason is in the Note column.")
    add("* Ratios are rounded down to two decimals, so a failing pair never shows as the required number.")
    add("* A pair is **skipped** when a role it needs is undefined or fully transparent for that layout "
        "(listed at the end).")
    add("* The colour maths was compared with real Chromium by `python scripts/check_contrast.py "
        "--verify-browser` (needs Playwright; skipped without it).")
    add("")

    # summary
    add("## Summary")
    add("")
    add("| Layout | Theme | Pairs checked | Pass | Fail | Accepted | Decor below target |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for (lid, theme), rs in rep.results.items():
        checked = [r for r in rs if r.status != "skip"]
        n = lambda s: sum(1 for r in checked if r.status == s)
        add("| %s | %s | %d | %d | %d | %d | %d |" % (
            lid, theme, len(checked), n("pass") + n("decor"), n("FAIL"), n("accepted"), n("decor-miss")))
    add("")
    add("Pairs that need no enforcement (decor) count as passing unless they miss their target.")
    add("")
    status = ("**All enforced pairs pass.**" if not rep.failures else "**%d enforced pair(s) fail.**" % len(rep.failures))
    add(status + (" The two dark blocks of every file are identical, and the dark custom-colour blocks "
                  "restate everything their light block sets." if not rep.parity else
                  " **The dark blocks differ: see Failures.**"))
    add("")
    if rep.fallback is not None:
        fb = rep.fallback
        add("Browsers without `color-mix()`: " + ("**all %d enforced and decor pairs pass**" % fb.n_pairs if fb.ok else
            "**%d pair(s) fail and %d problem(s)**" % (len(fb.failures), len(fb.errors))) +
            " (%d pairs over %d layouts x 2 themes x default / `data-league-colour`, `fallbacks.css` active)." % (
                fb.n_pairs, len(fb.layouts)))
        add("")
        add("## Browsers without color-mix()")
        add("")
        add("Safari/iOS before 16.2, Chrome before 111 and Firefox before 113 do not know `color-mix()`. A custom "
            "property that holds `var()` plus `color-mix()` is then dropped, and backgrounds go transparent. "
            "`assets/css/fallbacks.css` (generated by `scripts/build_css_fallbacks.py`, loaded last) is one "
            "`@supports not (color: color-mix(in oklab, red, red))` block that gives every colour role of every "
            "layout, in light, OS-dark and `[data-theme=\"dark\"]`, with and without `data-league-colour`, its "
            "literal value for the layout's default colour, and a literal for each part rule that mixes colours "
            "itself. Such a browser therefore shows the layout's default look: a league loses its own colour (and "
            "a custom team colour loses its dark-theme lift) but nothing becomes unreadable. This checker runs the "
            "whole pair list on that cascade (`fallbacks.css` active, any `color-mix()` still reachable is an "
            "error, the league colour not set) for every layout and theme, with and without the attribute, and "
            "fails if `fallbacks.css` is stale (`python scripts/check_contrast.py --fallbacks` runs only this part).")
        add("")

    # failures first
    add("## Failures")
    add("")
    if rep.ok:
        add("None.")
        add("")
    for e in rep.parity:
        add("* **Dark blocks:** %s" % e)
    if rep.fallback is not None:
        for e in rep.fallback.errors:
            add("* **Without color-mix():** %s" % e)
        for r in rep.fallback.failures:
            add("* **Without color-mix(), %s, %s theme, `%s`** (%s): %s on %s = **%s:1**, needs %s:1." % (
                r.layout, r.theme, r.pair.id, _kind_label(r.pair), r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio), _need_label(r)))
    for r in rep.failures:
        add("* **%s, %s theme, `%s`** (%s): %s on %s = **%s:1**, needs %s:1%s." % (
            r.layout, r.theme, r.pair.id, _kind_label(r.pair), r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio),
            _need_label(r), (" (worst: %s)" % r.worst) if r.worst else ""))
    for f in rep.errors:
        add("* **Lint ERROR** `%s`: %s" % (f.where, f.message))
    seen = {}
    for lid, name, p in rep.league_failures:
        seen.setdefault(name, {}).setdefault(lid, set()).add(p.theme)
    for name, by_layout in seen.items():
        add("* **League colour example %s** fails (see League colour examples for the messages): %s." % (
            name, "; ".join("%s (%s)" % (lid, ", ".join(t for t in THEMES if t in th)) for lid, th in by_layout.items())))
    for name in rep.expected_fail_passes:
        add("* **League colour example %s** is marked expected_fail but raises no problem: unmark it." % name)
    if not rep.ok:
        add("")

    # per layout / theme
    add("## Every pair")
    add("")
    for lid in rep.layouts:
        for theme in THEMES:
            rs = rep.results[(lid, theme)]
            add("### %s, %s" % (lid, theme))
            add("")
            add("| Pair | Kind | Foreground | Background | Ratio | Required | Result | Note |")
            add("|---|---|---|---|---:|---:|---|---|")
            for r in rs:
                if r.status == "skip":
                    continue
                note = r.note
                if r.worst:
                    note = ("worst: %s. " % r.worst) + note if note else "worst: %s" % r.worst
                add("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
                    r.pair.id, r.pair.kind, r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio), _need_label(r),
                    _status_label(r), note.replace("|", "/")))
            add("")

    # league colours
    add("## League colour examples")
    add("")
    add("A league sets ONE colour (`colour`, optionally `colour_dark`) in `league.yml`. Stage 4 writes it as an "
        "inline `--st-league-color` (and `--st-league-color-dark`) on `<html>` and adds the attribute "
        "`data-league-colour` next to `data-layout`; each layout's `[data-league-colour]` blocks then re-derive "
        "everything that depends on the colour. The table below runs every pair of every layout in that "
        "mode, in both themes, with each example colour (no `colour_dark`, so the dark theme derives from the "
        "same colour). Failures here are information, not failures of the layouts: they are what a league "
        "picking that colour would be told. Only the example colours not marked as expected failures must pass.")
    add("")
    cols = rep.colours
    if rep.league:
        for c in cols:
            ok_in = [lid for lid in rep.layouts if not rep.league.get((lid, c["name"], c["hex"]))]
            bad_in = [lid for lid in rep.layouts if lid not in ok_in]
            if not bad_in:
                add("* **%s %s** passes in every layout, light and dark." % (c["name"], c["hex"]))
            elif not ok_in:
                add("* **%s %s** fails in every layout%s." % (
                    c["name"], c["hex"], " (expected: the deliberate hard case)" if c["expected_fail"] else ""))
            else:
                add("* **%s %s** passes in %s; fails in %s%s." % (
                    c["name"], c["hex"], ", ".join(ok_in), ", ".join(bad_in),
                    " (expected)" if c["expected_fail"] else ""))
        for c in cols:
            if not c["expected_fail"]:
                continue
            ink = [p for lid in rep.layouts for p in rep.league.get((lid, c["name"], c["hex"]), [])
                   if p.pair == "league-ink/league-base" and p.theme == "light"]
            add("* **%s is an expected failure**: white text on it fails AA, so stage 4 stops with %s"
                % (c["name"], ("`%s`" % ink[0].message) if ink else "a message naming `colour`"))
        add("* There is no second league colour: `colour_2` is not a league setting. A layout's own second "
            "accent (`--st-layout-accent`) is fixed by the layout and never set by a league.")
        add("")
        add("Failing roles per layout and theme (`pass`, or the number of foreground roles that fail; "
            "one message per role, at its worst background):")
        add("")
        head = ["Colour"] + ["%s %s" % (lid, th) for lid in rep.layouts for th in THEMES]
        add("| " + " | ".join(head) + " |")
        add("|---|" + "---:|" * (len(head) - 1))
        for c in cols:
            cells = []
            for lid in rep.layouts:
                ps = rep.league.get((lid, c["name"], c["hex"]), [])
                for th in THEMES:
                    n = sum(1 for p in ps if p.theme == th)
                    cells.append("pass" if not n else "**%d**" % n)
            add("| %s %s%s | %s |" % (c["name"], c["hex"], " (expected fail)" if c["expected_fail"] else "", " | ".join(cells)))
        add("")
        for lid in rep.layouts:
            for c in cols:
                ps = rep.league.get((lid, c["name"], c["hex"]), [])
                if not ps:
                    continue
                add("**%s with %s (%s)**" % (lid, c["name"], c["hex"]))
                add("")
                for p in ps:
                    add("* %s `%s`" % (p.message, p.pair))
                add("")
    else:
        add("(Not run.)")
        add("")

    # stage 4
    add("## How stage 4 calls this")
    add("")
    add("```python")
    add("from scripts.check_contrast import check_league_colour")
    add("problems = check_league_colour(layout_id, league[\"colour\"], league.get(\"colour_dark\"))")
    add("# [] = fine. Otherwise stop the build and print problem.message for each: every message names")
    add("# league.yml `colour` or `colour_dark` and says whether to pick a lighter or darker colour.")
    add("```")
    add("")
    add("* The data check runs only when the league sets a colour. It runs the layout in custom-colour mode (the "
        "league's colour inline, the layout's `[data-league-colour]` blocks active) in both themes and reports "
        "the pairs that pass with the layout's own colours and fail with the league's (white text on the colour "
        "itself included).")
    add("* The page must carry the attribute `data-league-colour` on the same `<html>` element as `data-layout` "
        "exactly when the league sets a colour (with `style=\"--st-league-color:#RRGGBB\"`, plus "
        "`--st-league-color-dark` when `colour_dark` is set). Without the attribute a layout is exactly the "
        "approved mockup look; with it, the layout's override blocks apply. A league that sets no colour gets "
        "no attribute and no inline style.")
    add("")

    # lint
    add("## Token lint")
    add("")
    errs = [f for f in rep.findings if f.level == "ERROR"]
    warns = [f for f in rep.findings if f.level == "WARNING"]
    add("%d error(s), %d warning(s). Errors fail the run." % (len(errs), len(warns)))
    add("")
    if errs:
        add("### Errors")
        add("")
        for f in errs:
            add("* `%s`: %s" % (f.where, f.message))
        add("")
    if warns:
        add("### Warnings")
        add("")
        for f in warns:
            add("* `%s`: %s" % (f.where, f.message))
        add("")

    # exceptions
    add("## Accepted exceptions")
    add("")
    for lid, zone in sorted(GRADIENT_TEXT_ZONE.items()):
        add("* **%s header gradient**: text and UI are checked only down to %d%% of the header height "
            "(and the colour at that edge); the last stops are scenery." % (lid, round(zone * 100)))
    for ex in ACCEPTED_EXCEPTIONS:
        add("* **%s, %s theme, `%s`**: %s" % (ex["layout"], ex["theme"] or "both", ex["pair"], ex["reason"]))
    add("")

    # skipped / undefined
    add("## Undefined roles and skipped pairs")
    add("")
    undefined, transparent = {}, {}
    for (lid, theme), rs in rep.results.items():
        for r in rs:
            if r.status == "skip" and r.missing:
                undefined.setdefault(lid, set()).update(r.missing)
            elif r.status == "skip" and r.note.startswith("transparent"):
                transparent.setdefault(lid, set()).add(r.pair.id)
    if undefined:
        for lid in sorted(undefined):
            add("* **%s**: undefined role(s) %s (their pairs were skipped)" % (
                lid, ", ".join("`--st-%s`" % x for x in sorted(undefined[lid]))))
    else:
        add("No pair was skipped for an undefined role.")
    add("")
    if transparent:
        add("Pairs skipped because the foreground is fully transparent (nothing is drawn):")
        add("")
        for lid in sorted(transparent):
            add("* **%s**: %s" % (lid, ", ".join("`%s`" % x for x in sorted(transparent[lid]))))
        add("")
    return "\n".join(L).rstrip() + "\n"


# =============================================================================
# 10. Optional: compare the maths with real Chromium
# =============================================================================

def _find_chromium() -> Optional[str]:
    for pat in (os.environ.get("CHROMIUM_PATH", ""), "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell"):
        for hit in sorted(glob.glob(pat)) if pat else []:
            if os.access(hit, os.X_OK):
                return hit
    return None


_VERIFY_JS = r"""
() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  function px(css, base) {
    cx.fillStyle = '#010203';
    cx.fillStyle = css;
    if (cx.fillStyle === '#010203' && css.replace(/\s/g,'').toLowerCase() !== '#010203') return null;
    cx.fillStyle = base; cx.fillRect(0,0,1,1);
    cx.fillStyle = css; cx.fillRect(0,0,1,1);
    const d = cx.getImageData(0,0,1,1).data; return [d[0], d[1], d[2]];
  }
  window.__px = px;
  const out = [];
  for (const w of document.querySelectorAll('.wrap')) {
    const rec = {id: w.dataset.id, roles: {}, grad: {}};
    for (const p of w.querySelectorAll('.probe')) {
      const css = getComputedStyle(p).backgroundColor;
      rec.roles[p.dataset.role] = [px(css, '#ffffff'), px(css, '#000000'), css];
    }
    rec.grad['header-bg'] = getComputedStyle(w).getPropertyValue('--st-header-bg');
    out.push(rec);
  }
  return out;
}
"""

_STOPS_JS = r"""
(list) => list.map(css => [window.__px(css, '#ffffff'), window.__px(css, '#000000')])
"""


# A throwaway layout, to prove that this module's cascade orders rules the way a browser does:
# specificity first, then source order; the OS-dark media block versus [data-theme]; and the
# custom-colour blocks (--st-g is the deliberate trap: set in the light custom block but not
# restated in the dark one, so in dark mode the light custom block beats the normal dark block).
_SYNTHETIC_CSS = """
[data-layout="zz"] { --st-a: #101010; --st-b: #202020; --st-c: #303030; --st-d: #404040; --st-e: #505050;
  --st-f: color-mix(in oklab, var(--st-league-color, #123456) 50%, white); --st-g: #707070; --st-h: #808080; }
@media (prefers-color-scheme: dark) {
  [data-layout="zz"]:not([data-theme="light"]) { --st-a: #A01010; --st-b: #B02020; --st-g: #C07070; --st-h: #C08080; }
}
[data-layout="zz"][data-theme="dark"] { --st-a: #A01010; --st-b: #B02020; --st-g: #C07070; --st-h: #C08080; }
[data-layout="zz"][data-league-colour] { --st-a: #1010A0; --st-c: #10A010; --st-d: var(--st-league-color); --st-g: #1070A0; --st-h: #1080A0; }
@media (prefers-color-scheme: dark) {
  [data-layout="zz"][data-league-colour]:not([data-theme="light"]) {
    --st-a: #2020D0; --st-c: #20D020; --st-d: var(--st-league-color-dark, #FFFFFF); --st-h: #2080D0; }
}
[data-layout="zz"][data-league-colour][data-theme="dark"] {
  --st-a: #2020D0; --st-c: #20D020; --st-d: var(--st-league-color-dark, #FFFFFF); --st-h: #2080D0; }
[data-layout] { --st-a: #FFFFFF; --st-e: #606060; }
[data-layout="zz"] { --st-e: #707070; }
"""
_SYNTHETIC_ROLES = ["a", "b", "c", "d", "e", "f", "g", "h"]


def _probe_page(browser, tmp: str, name: str, scheme: str, css_files: list, cases: list):
    """Render one wrapper per case (data-layout / data-theme / data-league-colour / inline style),
    one probe per role, and read back each probe's painted colour over white and over black.
    Returns (page, {case id: record})."""
    html = ["<!doctype html><meta charset=utf-8>"]
    for f in css_files:
        html.append('<link rel=stylesheet href="file://%s">' % f)
    for c in cases:
        style = ";".join("%s:%s" % (k, v) for k, v in c["over"].items())
        html.append('<div class=wrap data-id="%s" data-layout="%s"%s%s style="%s">' % (
            c["id"], c["layout"], (' data-theme="%s"' % c["attr"]) if c["attr"] else "",
            " data-league-colour" if c["custom"] else "", style))
        for role in c["roles"]:
            html.append('<div class=probe data-role="%s" style="background-color:var(--st-%s)"></div>' % (role, role))
        if c.get("team"):
            html.append('<div class="probe st-team--custom" data-role="team-custom" style="--st-team-hex:#D9621A;'
                        'background-color:var(--st-team)"></div>')
        html.append("</div>")
    path = Path(tmp) / ("probe-%s-%s.html" % (name, scheme))
    path.write_text("\n".join(html), encoding="utf-8")
    ctx = browser.new_context(color_scheme=scheme)
    page = ctx.new_page()
    page.goto("file://%s" % path)
    return ctx, page, {r["id"]: r for r in page.evaluate(_VERIFY_JS)}


def verify_browser(layouts: Optional[list] = None, verbose: bool = False) -> tuple:
    """Compare this module's cascade and colour maths with Chromium: every layout x theme
    (light, dark, none) x OS scheme x league-colour variant (none, each example colour with and
    without `colour_dark`, in custom-colour mode and, for one colour, without it), plus a
    synthetic throwaway layout that exercises specificity, source order, the OS-dark block
    versus [data-theme] and the custom-colour blocks. Returns (status, max_channel_diff, lines)
    where status is 'ok', 'fail' or 'skipped'."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return "skipped", 0, ["Playwright is not installed: browser comparison skipped."]
    layouts = layouts or layout_ids()
    exe = _find_chromium()
    colours = alt_league_colours()
    # (name, custom-colour mode?, inline overrides)
    variants = [("default", False, {})]
    variants += [(c["name"], True, {"--st-league-color": c["hex"]}) for c in colours]
    variants.append(("colour+dark", True, {"--st-league-color": "#9E1B32", "--st-league-color-dark": "#E58A9A"}))
    variants.append(("inline, no attribute", False, {"--st-league-color": colours[-1]["hex"]}))
    roles = list(COLOUR_ROLES) + list(LEAGUE_HELPERS)
    real, synth = [], []
    for lid in layouts:
        for vname, custom, o in variants:
            for scheme in ("light", "dark"):
                for attr in (None, "light", "dark"):
                    real.append({"id": "%s|%s|%s|%s" % (lid, vname, scheme, attr or "-"), "layout": lid, "attr": attr,
                                 "scheme": scheme, "custom": custom, "over": o, "roles": roles, "team": True})
    syn_over = [("none", {}), ("light only", {"--st-league-color": "#2F6B3A"}),
                ("light+dark", {"--st-league-color": "#2F6B3A", "--st-league-color-dark": "#7FC08A"})]
    for custom in (False, True):
        for oname, o in syn_over:
            for scheme in ("light", "dark"):
                for attr in (None, "light", "dark"):
                    synth.append({"id": "zz|%s|%s|%s|%s" % ("custom" if custom else "plain", oname, scheme, attr or "-"),
                                  "layout": "zz", "attr": attr, "scheme": scheme, "custom": custom, "over": o,
                                  "roles": _SYNTHETIC_ROLES, "team": False})
    lines, max_diff, worst, compared = [], 0, None, 0
    tmp = tempfile.TemporaryDirectory()
    syn_path = Path(tmp.name) / "synthetic.css"
    syn_path.write_text(_SYNTHETIC_CSS, encoding="utf-8")
    syn_rules = [parse_css(_SYNTHETIC_CSS, "synthetic.css")]
    real_css = [CSS_DIR / "tokens.css"] + [LAYOUT_DIR / (i + ".css") for i in layouts]
    try:
        with sync_playwright() as pw:
            launch = {"args": ["--no-sandbox"]}
            if exe:
                launch["executable_path"] = exe
            try:
                browser = pw.chromium.launch(**launch)
            except Exception as e:      # no browser binary
                return "skipped", 0, ["Chromium could not be started (%s): browser comparison skipped." % str(e).splitlines()[0]]
            lines.append("Chromium %s" % browser.version)
            for scheme in ("light", "dark"):
                for name, files, cases in (("real", real_css, real), ("synthetic", [syn_path], synth)):
                    sub = [c for c in cases if c["scheme"] == scheme]
                    ctx, page, data = _probe_page(browser, tmp.name, name, scheme, files, sub)
                    stop_jobs = []
                    for c in sub:
                        rec = data[c["id"]]
                        if name == "real":
                            pal = Palette(c["layout"], c["attr"], prefers_dark=(scheme == "dark"), overrides=c["over"],
                                          custom=c["custom"])
                        else:
                            pal = Palette.from_decls(cascade_rules(syn_rules, "zz", c["attr"], scheme == "dark", c["over"], c["custom"]),
                                                     "zz", c["attr"] or scheme)
                        exp_roles = {r: pal.paint(r) for r in c["roles"]}
                        if c.get("team"):
                            lift = pal.text_of("team-lift")
                            try:
                                exp_roles["team-custom"] = parse_colour("color-mix(in oklab, #D9621A, white %s)" % lift)
                            except ColourError:
                                pass
                        for role, paint in exp_roles.items():
                            got = rec["roles"].get(role)
                            if paint is None or isinstance(paint, Gradient) or got is None or got[0] is None:
                                continue
                            for k, base in ((0, WHITE), (1, BLACK)):
                                exp = rgb8(composite(paint, base))
                                diff = max(abs(a - b) for a, b in zip(exp, got[k]))
                                compared += 1
                                if diff > max_diff or worst is None:
                                    if diff >= max_diff:
                                        max_diff = diff
                                        worst = "%s %s (%s): mine %s, Chromium %s, css %s" % (
                                            c["id"], role, "over white" if k == 0 else "over black", exp, tuple(got[k]), got[2])
                        grad = pal.paint("header-bg") if name == "real" else None
                        if isinstance(grad, Gradient):
                            text = rec["grad"]["header-bg"].strip()
                            parts = split_top(text[text.index("(") + 1:text.rindex(")")]) if "gradient" in text else []
                            if parts and re.match(r"^\s*(to\s|[-+]?[\d.]+(deg|turn))", parts[0]):
                                parts = parts[1:]
                            css_stops = []
                            for a in parts:
                                toks = split_ws(a)
                                if len(toks) > 1 and re.match(r"^[-+]?[\d.]+(%|px)?$", toks[-1]):
                                    toks = toks[:-1]
                                css_stops.append(" ".join(toks))
                            stop_jobs.append((c["id"], css_stops, grad))
                    for cid, css_stops, grad in stop_jobs:
                        got = page.evaluate(_STOPS_JS, css_stops)
                        if len(got) != len(grad.stops):
                            lines.append("gradient stop count differs for %s: mine %d, Chromium %d" % (cid, len(grad.stops), len(got)))
                            max_diff = 255
                            continue
                        for (col, _), g in zip(grad.stops, got):
                            for k, base in ((0, WHITE), (1, BLACK)):
                                if g[k] is None:
                                    continue
                                diff = max(abs(a - b) for a, b in zip(rgb8(composite(col, base)), g[k]))
                                compared += 1
                                if diff > max_diff:
                                    max_diff, worst = diff, "%s header-bg stop" % cid
                    ctx.close()
            browser.close()
    finally:
        tmp.cleanup()
    lines.append("compared %d colour samples (%d layout wrappers x %d roles, %d synthetic-layout wrappers x %d roles, "
                 "plus gradient stops)" % (compared, len(real), len(roles) + 1, len(synth), len(_SYNTHETIC_ROLES)))
    lines.append("max channel difference: %d/255%s" % (max_diff, (" at " + worst) if worst and max_diff > 0 else ""))
    return ("ok" if max_diff <= 1 else "fail"), max_diff, lines



def trace_custom(layout: str, hex_: str, hex_dark: Optional[str] = None) -> list:
    """Lines showing how every colour role resolves for `layout` in custom-colour mode: the
    cascade's raw value, the value with var() substituted, and the colour it paints."""
    hex_, hex_dark = _norm_hex(hex_, "colour"), _norm_hex(hex_dark, "colour_dark")
    over = league_overrides(hex_, hex_dark)
    out = ["%s in custom-colour mode, %s%s" % (layout, hex_, " / dark " + hex_dark if hex_dark else "")]
    for theme in THEMES:
        pal = palette(layout, theme, over, custom=True)
        out += ["", "[%s theme]" % theme]
        for role in list(LEAGUE_HELPERS) + COLOUR_ROLES:
            if not pal.defined(role):
                out.append("  --st-%-20s (undefined)" % role)
                continue
            paint = pal.paint(role)
            shown = ("gradient" if isinstance(paint, Gradient) else to_hex(paint)) if paint is not None else "(unresolved)"
            out.append("  --st-%-20s %-9s %s" % (role, shown, pal.raw(role)))
    return out


# =============================================================================
# 11. Command line
# =============================================================================

def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="WCAG contrast check and token lint for the design system.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write docs/contrast.md (the default)")
    mode.add_argument("--check", action="store_true", help="do not write; fail if docs/contrast.md is out of date")
    mode.add_argument("--tokens", action="store_true", help="token lint only")
    ap.add_argument("--fallbacks", action="store_true",
                    help="only the browsers-without-color-mix() run: every pair on the cascade with fallbacks.css active")
    ap.add_argument("--verify-browser", action="store_true", help="also compare the colour maths with Chromium (needs Playwright)")
    ap.add_argument("--trace", nargs="+", metavar=("LAYOUT", "HEX"),
                    help="print how every colour role resolves in custom-colour mode: --trace LAYOUT HEX [HEX_DARK]")
    ap.add_argument("--out", default=str(DOC_PATH), help="where --write puts the report")
    args = ap.parse_args(argv)

    code = 0
    if args.trace:
        if len(args.trace) not in (2, 3):
            ap.error("--trace takes LAYOUT HEX [HEX_DARK]")
        for ln in trace_custom(args.trace[0], args.trace[1], args.trace[2] if len(args.trace) == 3 else None):
            print(ln)
        return 0
    if args.fallbacks:
        fb = check_fallbacks()
        for e in fb.errors:
            print("FALLBACK", e)
        for r in fb.failures:
            print("FALLBACK-FAIL %s %s %s: %s on %s = %s (needs %s)" % (
                r.layout, r.theme, r.pair.id, r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio), _need_label(r)))
        print(fallback_summary(fb))
        code = 0 if fb.ok else 1
    elif args.tokens:
        findings = lint_tokens()
        for f in findings:
            print("%s %s: %s" % (f.level, f.where, f.message))
        errs = sum(1 for f in findings if f.level == "ERROR")
        print("token lint: %d error(s), %d warning(s)" % (errs, len(findings) - errs))
        code = 1 if errs else 0
    else:
        rep = run_checks()
        text = render_markdown(rep)
        for e in rep.parity:
            print("PARITY", e)
        for r in rep.failures:
            print("FAIL %s %s %s: %s on %s = %s (needs %s)%s" % (
                r.layout, r.theme, r.pair.id, r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio), _need_label(r),
                (" worst: " + r.worst) if r.worst else ""))
        for f in rep.findings:
            print("%s %s: %s" % (f.level, f.where, f.message))
        for lid, name, p in rep.league_failures:
            print("LEAGUE-COLOUR %s %s %s: %s" % (lid, name, p.theme, p.message))
        for name in rep.expected_fail_passes:
            print("LEAGUE-COLOUR %s is marked expected_fail but raises no problem" % name)
        if rep.fallback is not None:
            for e in rep.fallback.errors:
                print("FALLBACK", e)
            for r in rep.fallback.failures:
                print("FALLBACK-FAIL %s %s %s: %s on %s = %s (needs %s)" % (
                    r.layout, r.theme, r.pair.id, r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio), _need_label(r)))
            print(fallback_summary(rep.fallback))
        n_pairs = sum(1 for rs in rep.results.values() for r in rs if r.status != "skip")
        print("%d pairs checked across %d layouts x 2 themes: %d fail, %d dark-block mismatch, %d lint error(s), %d lint warning(s); "
              "%d league-colour example problem(s) that must not occur" % (
                  n_pairs, len(rep.layouts), len(rep.failures), len(rep.parity), len(rep.errors),
                  len(rep.findings) - len(rep.errors), len(rep.league_failures)))
        if not rep.ok:
            code = 1
        out = Path(args.out)
        if args.check:
            current = out.read_text(encoding="utf-8") if out.exists() else ""
            if current != text:
                print("%s is out of date: run python scripts/check_contrast.py" % os.path.relpath(str(out), ROOT))
                code = 1
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print("wrote %s" % os.path.relpath(str(out), ROOT))
    if args.verify_browser:
        status, diff, lines = verify_browser()
        for ln in lines:
            print(ln)
        print("browser comparison: %s" % status)
        if status == "fail":
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
