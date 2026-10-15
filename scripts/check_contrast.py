#!/usr/bin/env python3
"""WCAG contrast check and token lint for the scorers-table design system.

What it does
------------
1. Reads assets/css/tokens.css and assets/css/layouts/<id>.css and works out, for every
   layout and both themes, the value of every --st-* custom property by running the
   cascade the way a browser does (specificity, then source order; var() with
   fallbacks; color-mix() in oklab/srgb; hex and rgb(); linear-gradient()).
2. Measures every text / background / UI pair the design needs (PAIRS below), with
   alpha colours composited over what they sit on, and gradients checked on every
   stop. Writes docs/contrast.md (generated).
3. Runs the league colour examples (--st-league-color overridden) through the same
   pairs. `check_league_colour()` is the function stage 4's data check calls.
4. Lints the tokens (roles read but undefined, roles never read, raw colours in the
   parts CSS) and checks that each layout's two dark blocks (the media query and the
   [data-theme="dark"] one) are identical.
5. `--verify-browser` compares the colour maths with real Chromium (optional).

Usage (from the repo root)
--------------------------
    python scripts/check_contrast.py                 # run everything, write docs/contrast.md
    python scripts/check_contrast.py --check         # same, but fail if docs/contrast.md is stale
    python scripts/check_contrast.py --tokens        # token lint only
    python scripts/check_contrast.py --verify-browser  # also compare the maths with Chromium
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
    """A linear-gradient: a list of (Colour, position 0..1 or None)."""
    stops: tuple


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
    """A colour, or a linear-gradient() (kept as its colour stops)."""
    s = text.strip()
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

@dataclass
class Rule:
    """One style rule: selector text, its custom-property declarations, the @media
    condition it sits in (None = none), the file, and a global source-order number."""
    selector: str
    decls: dict
    media: Optional[str]
    source: str
    order: int


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


def parse_css(text: str, source: str = "", media: Optional[str] = None, _counter: Optional[list] = None) -> list:
    """Parse CSS text into Rules (custom properties only). Understands @media nesting;
    other at-rules are skipped."""
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
            rules += parse_css(body, source, prelude[6:].strip(), counter)
        elif prelude.startswith("@"):
            pass
        elif prelude:
            for sel in split_top(prelude):
                sel = re.sub(r"\s+", " ", sel.strip())
                counter[0] += 1
                rules.append(Rule(sel, _parse_decls(body), media, source, counter[0]))
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
    several of them joined without spaces. Anything else (classes, descendants) never matches."""
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
                  overrides: Optional[dict] = None) -> dict:
    """The custom properties on an element carrying data-layout=<layout> and
    data-theme=<theme> (None = attribute absent), as a browser computes them. `rule_lists`
    is one list of Rules per stylesheet, in load order: specificity first, source order
    second. `overrides` act like an inline style (they win)."""
    attrs = {"data-layout": layout}
    if theme:
        attrs["data-theme"] = theme
    matched = []
    for idx, rules in enumerate(rule_lists):
        for rule in rules:
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
            overrides: Optional[dict] = None, css_files: Optional[list] = None) -> dict:
    """`cascade_rules` over assets/css/tokens.css and layouts/<layout>.css (or `css_files`)."""
    if css_files is None:
        css_files = [CSS_DIR / "tokens.css", LAYOUT_DIR / (layout + ".css")]
    return cascade_rules([load_rules(f) for f in css_files], layout, theme, prefers_dark, overrides)


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
LEAGUE_HELPERS = ("league-base", "league-2-base", "league-dim", "league-lift", "league-tint",
                  "league-wash", "league-2-tint", "league-ink")
OTHER_REQUIRED_ROLES = ("bg-image", "scene-image", "scene-image-footer", "team-lift")


class Palette:
    """Resolved colours of one layout and theme. `theme` is 'light' or 'dark' (the
    data-theme attribute), or None with prefers_dark=True for the OS-dark path."""

    def __init__(self, layout: str, theme: Optional[str], prefers_dark: bool = False,
                 overrides: Optional[dict] = None, decls: Optional[dict] = None):
        self.layout = layout
        self.theme = theme
        self.prefers_dark = prefers_dark
        self.decls = decls if decls is not None else cascade(layout, theme, prefers_dark, overrides)
        self._cache = {}

    @classmethod
    def from_decls(cls, decls: dict, layout: str = "test", theme: str = "light") -> "Palette":
        """A palette over an explicit {--st-name: value} dict (tests, experiments)."""
        return cls(layout, theme, decls=dict(decls))

    @property
    def name(self) -> str:
        return self.theme or ("dark" if self.prefers_dark else "light")

    def defined(self, role: str) -> bool:
        return "--st-" + role in self.decls

    def raw(self, role: str) -> Optional[str]:
        return self.decls.get("--st-" + role)

    def paint(self, role: str) -> Optional[Union[Colour, Gradient]]:
        """The role's colour (or Gradient); None when undefined or not resolvable. A string
        starting with `color-mix(` is taken as a CSS expression (var(--st-*) allowed) instead
        of a role name, for backgrounds that are not a role (a translucent track)."""
        if role not in self._cache:
            try:
                if role.startswith("color-mix("):
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


def palette(layout: str, theme: str, overrides: Optional[dict] = None) -> Palette:
    """The palette for an explicit data-theme ('light' or 'dark')."""
    return Palette(layout, theme, False, overrides)


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
    "score-line": "score dividers", "league-ink": "white text",
    "league-base": "the league colour", "league-dim": "the darkened league colour",
    "league-lift": "the lightened league colour",
}


def _role_word(role: str) -> str:
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
_LEAD_TRACK = "color-mix(in oklab, var(--st-panel-text) 22%, transparent)"


def build_pairs() -> list:
    """The full pair list."""
    P = []
    # page text
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
              why="decorative outline and dotted divider; the content inside carries the information"),
        _pair("focus", "bg", "ui"),
        _pair("focus", "surface", "ui"),
        _pair("line", "surface", "decor", why=_HAIR),
        _pair("on-accent", "button-bg", "text"),
        _pair("button-bg", "bg", "decor", required=3.0,
              why="the label (on-accent on button-bg) identifies the button; the edge is reported for information"),
    ]
    # header and nav
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
    ]
    # next-game panel
    for fg in ("panel-text", "panel-muted", "panel-label"):
        P.append(_pair(fg, "panel-bg", "text"))
        P.append(_pair(fg, ("panel-bg", "panel-row"), "text", "%s/panel-row" % fg))
    P += [
        _pair("panel-tile-text", ("panel-bg", "panel-tile-bg"), "text", "panel-tile-text/panel-tile-bg"),
        _pair("panel-line", "panel-bg", "decor", why=_HAIR),
    ]
    # footer
    for fg in ("footer-text", "footer-muted", "footer-link"):
        P.append(_pair(fg, "footer-bg", "text"))
    P += [
        _pair("footer-accent", "footer-bg", "ui"),
        _pair("footer-line", "footer-bg", "decor", why=_HAIR),
    ]
    # marks, badges, ranks
    P += [
        _pair("mark-text", ("surface", "mark-bg"), "text", "mark-text/mark-bg"),
        _pair("mark-line", "surface", "ui", only=("slopitch",),
              why="slo-pitch draws the run-limit circle with it"),
        _pair("mark-line", "surface", "decor", required=3.0, not_in=("slopitch",),
              why="outline of a tinted cell; the cell text colour (mark-text) and a visually-hidden label carry the meaning"),
        _pair("won-line", "surface", "ui", only=("basketball", "curling", "hockey", "slopitch"),
              why="the won-period underline on the card surface (parts-scores.css); Classic and Scoreboard draw it elsewhere"),
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
        _pair("bar-fill", "bar-track", "ui"),
        _pair("bar-lead", ("panel-bg", _LEAD_TRACK), "ui", "bar-lead/lead-track", only=("scoreboard",),
              why="Scoreboard's race draws the leader's bar on the lead row (panel-bg with a panel-text "
                  "track at 22%, parts-data.css)"),
        _pair("bar-lead", "bar-track", "ui", not_in=("scoreboard",)),
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
    GRADIENT_TEXT_ZONE). [(label, Colour)], or None if a role is undefined. The first role
    must be opaque."""
    cur = [("", None)]
    for role in roles:
        paint = pal.paint(role)
        if paint is None:
            return None
        nxt = []
        for label, base in cur:
            if isinstance(paint, Gradient):
                stops = _zone_stops(paint.stops, zone)
                for i, (c, pos) in enumerate(stops):
                    where = "stop %d of %d (%s%s)" % (
                        i + 1, len(stops), to_hex(c), " @%d%%" % round(pos * 100) if pos is not None else "")
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


def league_overrides(hex_: str, hex_dark=None, hex_2=None, hex_2_dark=None) -> dict:
    """The inline-style custom properties a league's colours become."""
    o = {"--st-league-color": hex_}
    if hex_dark:
        o["--st-league-color-dark"] = hex_dark
    if hex_2:
        o["--st-layout-accent"] = hex_2
    if hex_2_dark:
        o["--st-layout-accent-dark"] = hex_2_dark
    return o


def _shift(hex_: str, toward: str, amount: float = 0.12) -> str:
    c = mix_colours(parse_colour(hex_), parse_colour(toward), 100 * (1 - amount), 100 * amount)
    return to_hex(c)


def _ratio_for(layout: str, theme: str, pair_id: str, overrides: dict) -> Optional[float]:
    for r in evaluate_palette(palette(layout, theme, overrides)):
        if r.pair.id == pair_id:
            return r.ratio
    return None


def check_league_colour(layout: str, hex: str, hex_dark: Optional[str] = None,
                        hex_2: Optional[str] = None, hex_2_dark: Optional[str] = None) -> list:
    """Run every pair for `layout` with the league's colours in place of the layout's
    defaults, in both themes. Returns a list of Problem (empty = fine): one per foreground
    role and theme (the worst background), for enforced pairs that pass with the layout's own
    colours and fail with the league's. (Pairs that already fail with the layout's own colours
    are the design's business, reported by the main run, not the league's.)
    Each Problem.message names the league.yml setting and what to do."""
    hex = _norm_hex(hex, "colour")
    hex_dark = _norm_hex(hex_dark, "colour_dark")
    hex_2 = _norm_hex(hex_2, "colour_2")
    hex_2_dark = _norm_hex(hex_2_dark, "colour_2_dark")
    over = league_overrides(hex, hex_dark, hex_2, hex_2_dark)
    problems = []
    for theme in THEMES:
        base = {r.pair.id: r for r in evaluate_palette(palette(layout, theme))}
        worst = {}      # (foreground role) -> the lowest-ratio failure, so one fix is one message
        for r in evaluate_palette(palette(layout, theme, over)):
            if r.status != "FAIL" or base[r.pair.id].status == "FAIL":
                continue
            if r.pair.fg not in worst or r.ratio < worst[r.pair.fg].ratio:
                worst[r.pair.fg] = r
        for r in worst.values():
            problems.append(_make_problem(layout, theme, r, over, hex, hex_dark, hex_2, hex_2_dark))
    return problems


def _responsible(layout, theme, r, over, hex_, hex_dark, hex_2, hex_2_dark):
    """(setting name, its value, direction word) for the league input that moves this pair's ratio."""
    if theme == "light":
        cands = [("colour", "--st-league-color", hex_), ("colour_2", "--st-layout-accent", hex_2)]
    else:
        cands = [("colour_dark" if hex_dark else "colour", "--st-league-color-dark" if hex_dark else "--st-league-color",
                  hex_dark or hex_),
                 ("colour_2_dark" if hex_2_dark else "colour_2",
                  "--st-layout-accent-dark" if hex_2_dark else "--st-layout-accent", hex_2_dark or hex_2)]
    for setting, prop, value in cands:
        if value is None:
            # colour 2 not set by the league: the layout's own colour 2 is in use
            value = palette(layout, theme).text_of("league-2-base") if "2" in prop else None
            if value is None:
                continue
            value = to_hex(parse_colour(value))
        ratios = {}
        for toward in ("#FFFFFF", "#000000"):
            o = dict(over)
            o[prop] = _shift(value, toward)
            ratios[toward] = _ratio_for(layout, theme, r.pair.id, o)
        if ratios["#FFFFFF"] is None or ratios["#000000"] is None:
            continue
        if abs(ratios["#FFFFFF"] - r.ratio) < 0.005 and abs(ratios["#000000"] - r.ratio) < 0.005:
            continue
        direction = "lighter" if ratios["#FFFFFF"] > ratios["#000000"] else "darker"
        return setting, value, direction
    return "colour", hex_, "darker"


def _make_problem(layout, theme, r, over, hex_, hex_dark, hex_2, hex_2_dark) -> Problem:
    setting, value, direction = _responsible(layout, theme, r, over, hex_, hex_dark, hex_2, hex_2_dark)
    shown = floor2(r.ratio)
    plain = r.pair.plain or "%s on %s" % (_role_word(r.pair.fg), _role_word(r.pair.bg[-1]))
    need = r.need
    if theme == "light":
        fix = "Pick a %s colour%s." % (direction, "" if setting == "colour" else " for " + setting)
    elif setting in ("colour_dark", "colour_2_dark"):
        fix = "Change %s: pick a %s one." % (setting, direction)
    elif setting == "colour_2":
        fix = "Set colour_2_dark to a %s colour (the dark theme uses colour_2 until you do)." % direction
    else:
        fix = "Set colour_dark to a %s colour (the dark theme uses colour until you do)." % direction
    msg = "league.yml %s %s: %s is %s:1 in the %s theme (needs %s:1). %s" % (
        setting, value, plain, ("%.2f" if round(shown, 1) >= need else "%.1f") % shown, theme,
        ("%g" % need), fix)
    return Problem(layout, theme, r.pair.id, round(r.ratio, 3), need, msg, setting)


def alt_league_colours() -> list:
    """[(name, hex)] from scripts/design_system/sample.py (ALT_LEAGUE_COLOURS)."""
    sys.path.insert(0, str(ROOT))
    try:
        from scripts.design_system.sample import ALT_LEAGUE_COLOURS
        return [(c["name"], c["hex"]) for c in ALT_LEAGUE_COLOURS]
    except Exception:       # keep the checker usable if the sample module is missing
        return [("Navy", "#1D3A6E"), ("Deep red", "#9E1B32"), ("Forest green", "#2F6B3A"), ("Gold", "#C98A12")]


# =============================================================================
# 6. Dark-block parity
# =============================================================================

_NOT_LIGHT = ':not([data-theme="light"])'


def _norm_value(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip()


def dark_parity_errors(rules: list, name: str) -> list:
    """Compare, in one stylesheet's Rules, each `@media (prefers-color-scheme: dark)` block
    (selector `X:not([data-theme="light"])`) with the `X[data-theme="dark"]` block: the
    declarations must be identical (whitespace aside). Returns error strings."""
    media, explicit, errors = {}, {}, []
    not_light = _NOT_LIGHT.replace(" ", "")
    for rule in rules:
        sel = rule.selector.replace(" ", "")
        if rule.media and rule.media.replace(" ", "") == "(prefers-color-scheme:dark)" and sel.endswith(not_light):
            media.setdefault(sel[:-len(not_light)], {}).update({k: _norm_value(v) for k, v in rule.decls.items()})
        elif rule.media is None and sel.endswith('[data-theme="dark"]'):
            explicit.setdefault(sel[:-len('[data-theme="dark"]')], {}).update(
                {k: _norm_value(v) for k, v in rule.decls.items()})
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
    (and the same for light). Returns error strings."""
    errs = []
    for a, b, label in ((Palette(layout, None, True), Palette(layout, "dark"), "dark"),
                        (Palette(layout, None, False), Palette(layout, "light"), "light")):
        for k in sorted(set(a.decls) | set(b.decls)):
            if a.decls.get(k) != b.decls.get(k):
                errs.append("%s: %s differs between the OS preference and data-theme=\"%s\"" % (layout, k, label))
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
# by class rules; reading them without a definition is fine.
INLINE_INPUTS = {"--st-league-color", "--st-league-color-dark", "--st-layout-accent",
                 "--st-layout-accent-dark", "--st-team-hex"}

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
    league: dict = field(default_factory=dict)        # (layout, name, hex) -> [Problem]
    parity: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    layouts: list = field(default_factory=list)
    colours: list = field(default_factory=list)

    @property
    def failures(self) -> list:
        return [r for rs in self.results.values() for r in rs if r.status == "FAIL"]

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.level == "ERROR"]

    @property
    def ok(self) -> bool:
        return not (self.failures or self.parity or self.errors)


def run_checks(layouts: Optional[list] = None, with_league: bool = True) -> Report:
    """Run the pairs, the parity check, the league colour examples and the lint."""
    rep = Report(layouts=layouts or layout_ids())
    rep.colours = alt_league_colours()
    for lid in rep.layouts:
        for theme in THEMES:
            rep.results[(lid, theme)] = evaluate_palette(palette(lid, theme))
        rep.parity += check_dark_equivalence(lid)
        if with_league:
            for name, hx in rep.colours:
                rep.league[(lid, name, hx)] = check_league_colour(lid, hx)
    rep.parity += check_dark_parity(layouts=rep.layouts)
    rep.findings = lint_tokens()
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
    add("* Every colour role is resolved the way a browser does it: tokens, then the layout, then the dark "
        "block (var() with fallbacks, `color-mix()` in oklab, gradients). Translucent colours are "
        "composited over what they sit on before they are measured. A gradient is measured on every "
        "colour stop and the worst stop is shown.")
    add("* **text** pairs need 4.5:1, **large** (24 px and up, or 18.66 px bold) and **ui** (borders of "
        "controls, the focus ring, bar fills, marks that carry meaning) need 3:1 (WCAG 2.1 AA).")
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
    add(status + (" The two dark blocks of every file are identical." if not rep.parity else
                  " **The dark blocks differ: see Failures.**"))
    add("")

    # failures first
    add("## Failures")
    add("")
    if not (rep.failures or rep.parity or rep.errors):
        add("None.")
        add("")
    for e in rep.parity:
        add("* **Dark blocks:** %s" % e)
    for r in rep.failures:
        add("* **%s, %s theme, `%s`** (%s): %s on %s = **%s:1**, needs %s:1%s." % (
            r.layout, r.theme, r.pair.id, _kind_label(r.pair), r.fg_hex, r.bg_hex, _fmt_ratio(r.ratio),
            _need_label(r), (" (worst: %s)" % r.worst) if r.worst else ""))
    for f in rep.errors:
        add("* **Lint ERROR** `%s`: %s" % (f.where, f.message))
    if rep.failures or rep.parity or rep.errors:
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
    add("Each layout with the league's own colour in place of the layout's default "
        "(`--st-league-color` set inline, as stage 4 does from `league.yml`; no `colour_dark`, "
        "so the dark theme derives from the same colour). Failures here are information, not "
        "failures of the run: they are what a league picking that colour would be told. "
        "Gold is the deliberate hard case.")
    add("")
    cols = rep.colours
    add("| Layout | " + " | ".join("%s %s" % (n, h) for n, h in cols) + " |")
    add("|---|" + "---|" * len(cols))
    for lid in rep.layouts:
        cells = []
        for n, h in cols:
            ps = rep.league.get((lid, n, h), [])
            cells.append("ok" if not ps else "%d problem%s" % (len(ps), "" if len(ps) == 1 else "s"))
        add("| %s | %s |" % (lid, " | ".join(cells)))
    add("")
    for lid in rep.layouts:
        for n, h in cols:
            ps = rep.league.get((lid, n, h), [])
            if not ps:
                continue
            add("**%s with %s (%s)**" % (lid, n, h))
            add("")
            for p in ps:
                add("* %s" % p.message)
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


def verify_browser(layouts: Optional[list] = None, verbose: bool = False) -> tuple:
    """Compare this module's colour maths with Chromium for every layout x theme x
    league-colour override x (data-theme / OS scheme) combination. Returns
    (status, max_channel_diff, lines) where status is 'ok', 'fail' or 'skipped'."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return "skipped", 0, ["Playwright is not installed: browser comparison skipped."]
    layouts = layouts or layout_ids()
    exe = _find_chromium()
    overrides = [("default", {})]
    overrides += [(n, {"--st-league-color": h}) for n, h in alt_league_colours()]
    overrides.append(("two-colour set", {"--st-league-color": "#C98A12", "--st-league-color-dark": "#E3B341",
                                         "--st-layout-accent": "#2F6B3A", "--st-layout-accent-dark": "#7FC08A"}))
    roles = list(COLOUR_ROLES) + list(LEAGUE_HELPERS)
    cases = []     # (id, layout, attr theme or None, scheme, override name, overrides)
    for lid in layouts:
        for oname, o in overrides:
            for scheme in ("light", "dark"):
                for attr in (None, "light", "dark"):
                    cases.append(("%s|%s|%s|%s" % (lid, oname, scheme, attr or "-"), lid, attr, scheme, oname, o))
    lines, max_diff, worst, compared = [], 0, None, 0
    tmp = tempfile.TemporaryDirectory()
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
                sub = [c for c in cases if c[3] == scheme]
                html = ["<!doctype html><meta charset=utf-8>"]
                for f in [CSS_DIR / "tokens.css"] + [LAYOUT_DIR / (i + ".css") for i in layouts]:
                    html.append('<link rel=stylesheet href="file://%s">' % f)
                for cid, lid, attr, _, _, o in sub:
                    style = ";".join("%s:%s" % (k, v) for k, v in o.items())
                    html.append('<div class=wrap data-id="%s" data-layout="%s"%s style="%s">' % (
                        cid, lid, (' data-theme="%s"' % attr) if attr else "", style))
                    for role in roles:
                        html.append('<div class=probe data-role="%s" style="background-color:var(--st-%s)"></div>' % (role, role))
                    html.append('<div class="probe st-team--custom" data-role="team-custom" style="--st-team-hex:#D9621A;'
                                'background-color:var(--st-team)"></div></div>')
                path = Path(tmp.name) / ("probe-%s.html" % scheme)
                path.write_text("\n".join(html), encoding="utf-8")
                ctx = browser.new_context(color_scheme=scheme)
                page = ctx.new_page()
                page.goto("file://%s" % path)
                data = {r["id"]: r for r in page.evaluate(_VERIFY_JS)}
                stop_jobs = []
                for cid, lid, attr, _, oname, o in sub:
                    rec = data[cid]
                    theme = attr or scheme
                    pal = Palette(lid, attr, prefers_dark=(scheme == "dark"), overrides=o)
                    exp_roles = {r: pal.paint(r) for r in roles}
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
                                    worst = "%s %s (%s): mine %s, Chromium %s, css %s" % (cid, role, "over white" if k == 0 else "over black", exp, tuple(got[k]), got[2])
                    grad = pal.paint("header-bg")
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
                        stop_jobs.append((cid, css_stops, grad))
                for cid, css_stops, grad in stop_jobs:
                    got = page.evaluate(_STOPS_JS, css_stops)
                    if len(got) != len(grad.stops):
                        lines.append("gradient stop count differs for %s: mine %d, Chromium %d" % (cid, len(grad.stops), len(got)))
                        max_diff = 255
                        continue
                    for (c, _), g in zip(grad.stops, got):
                        for k, base in ((0, WHITE), (1, BLACK)):
                            if g[k] is None:
                                continue
                            diff = max(abs(a - b) for a, b in zip(rgb8(composite(c, base)), g[k]))
                            compared += 1
                            if diff > max_diff:
                                max_diff, worst = diff, "%s header-bg stop" % cid
                ctx.close()
            browser.close()
    finally:
        tmp.cleanup()
    lines.append("compared %d colour samples (%d wrappers x %d roles + gradient stops)" % (
        compared, len(cases), len(roles) + 1))
    lines.append("max channel difference: %d/255%s" % (max_diff, (" at " + worst) if worst and max_diff > 0 else ""))
    return ("ok" if max_diff <= 1 else "fail"), max_diff, lines


# =============================================================================
# 11. Command line
# =============================================================================

def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="WCAG contrast check and token lint for the design system.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write docs/contrast.md (the default)")
    mode.add_argument("--check", action="store_true", help="do not write; fail if docs/contrast.md is out of date")
    mode.add_argument("--tokens", action="store_true", help="token lint only")
    ap.add_argument("--verify-browser", action="store_true", help="also compare the colour maths with Chromium (needs Playwright)")
    ap.add_argument("--out", default=str(DOC_PATH), help="where --write puts the report")
    args = ap.parse_args(argv)

    code = 0
    if args.tokens:
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
        n_pairs = sum(1 for rs in rep.results.values() for r in rs if r.status != "skip")
        print("%d pairs checked across %d layouts x 2 themes: %d fail, %d dark-block mismatch, %d lint error(s), %d lint warning(s)" % (
            n_pairs, len(rep.layouts), len(rep.failures), len(rep.parity), len(rep.errors),
            len(rep.findings) - len(rep.errors)))
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
