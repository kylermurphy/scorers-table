#!/usr/bin/env python3
"""Simulate a browser without color-mix() in Chromium, and compare it with the real render.

A temp copy of the site CSS is made twice:
  modern   the CSS as it is (fallbacks.css never applies: Chromium has color-mix()).
  old      every `color-mix(` outside fallbacks.css is renamed to `color-mix-x(` (an unknown function:
           a declaration with var() inside is then valid at parse time and invalid at computed-value
           time, exactly what an old browser does; one without var() is dropped at parse time, also
           the same), and `@supports not (color: color-mix(in oklab, red, red))` in fallbacks.css is
           rewritten to `@supports (color: red)` (always true), so the fallbacks apply.
Both are loaded in the generated design-system page (every part, every layout, light and dark) and the
computed colours of every element are compared.

    python tests/old_browser_sim.py                   # print the comparison
    python tests/old_browser_sim.py --shots DIR       # also screenshot frames of the old render
Needs Playwright and Chromium (the test skips without them). Standard library + Playwright.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORTS = "@supports not (color: color-mix(in oklab, red, red))"
SHOT_PARTS = ("header", "next-game", "standings", "result-card", "final-panel")


def make_site(dest: Path, old: bool) -> Path:
    """Copy assets/ and the design-system page into dest; with old=True simulate the old browser.
    Returns the page path."""
    shutil.copytree(ROOT / "assets", dest / "assets")
    ds = dest / "docs" / "design-system"
    ds.mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "design-system" / "ds.css", ds / "ds.css")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_design_system.py"), "--out", str(ds / "index.html")],
                   check=True, capture_output=True)
    if old:
        for f in (dest / "assets" / "css").rglob("*.css"):
            text = f.read_text(encoding="utf-8")
            if f.name == "fallbacks.css":
                assert SUPPORTS in text
                text = text.replace(SUPPORTS, "@supports (color: red)")
            else:
                text = text.replace("color-mix(", "color-mix-x(")
            f.write_text(text, encoding="utf-8")
    return ds / "index.html"


def find_chromium() -> str | None:
    for pat in (os.environ.get("CHROMIUM_PATH", ""), "/opt/pw-browsers/chromium-*/chrome-linux/chrome"):
        for hit in sorted(glob.glob(pat)) if pat else []:
            if os.access(hit, os.X_OK):
                return hit
    return None


# One record per element of every frame: where it is, and its painted colours.
_COLLECT = r"""
() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const cache = {};
  // computed colours of color-mix() are oklab(...) strings: paint them and read rgb back
  function one(css) {
    if (/^rgba?\(/.test(css) || css === 'transparent') return css;
    if (cache[css]) return cache[css];
    cx.clearRect(0,0,1,1); cx.fillStyle = '#000'; cx.fillStyle = css; cx.fillRect(0,0,1,1);
    const d = cx.getImageData(0,0,1,1).data;
    const a = d[3] ? Math.round(d[3] / 255 * 1000) / 1000 : 0;
    return cache[css] = a === 1 ? `rgb(${d[0]}, ${d[1]}, ${d[2]})` : `rgba(${d[0]}, ${d[1]}, ${d[2]}, ${a})`;
  }
  const norm = css => css.replace(/(oklab|oklch|lab|lch|color)\([^)]*\)/g, m => one(m)).replace(/\s+/g, ' ');
  const out = [];
  document.querySelectorAll('.ds-frame').forEach((fr, fi) => {
    const cap = fr.querySelector('.ds-cap').textContent;
    let part = '';
    for (let x = fr.closest('.ds-pair') || fr; x; x = x.previousElementSibling)
      if (x.tagName === 'H3' && x.id.startsWith('part-')) { part = x.id.slice(5); break; }
    const cs0 = getComputedStyle(fr);
    const rec = {frame: fi, cap, part, layout: fr.dataset.layout, theme: fr.dataset.theme,
                 custom: fr.hasAttribute('data-league-colour'), els: []};
    fr.querySelectorAll('.st-page *').forEach((e, i) => {
      const raw = getComputedStyle(e);
      const c = {backgroundColor: norm(raw.backgroundColor), color: norm(raw.color), borderTopColor: norm(raw.borderTopColor),
                 backgroundImage: norm(raw.backgroundImage), borderTopWidth: raw.borderTopWidth, visibility: raw.visibility, display: raw.display};
      const direct = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      rec.els.push([e.tagName.toLowerCase() + '.' + [...e.classList].join('.'), c.backgroundColor,
                    c.color, c.backgroundImage === 'none' ? '' : c.backgroundImage.replace(/data:[^)]*/g, 'data'),
                    c.borderTopColor, c.borderTopWidth, direct ? 1 : 0, c.visibility, c.display]);
    });
    out.push(rec);
  });
  return out;
}
"""


_PROBE_JS = r"""
(roles) => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const res = {};
  document.querySelectorAll('[data-layout]').forEach(w => {
    for (const r of roles) {
      const p = w.querySelector('[data-role="' + r + '"]');
      const c = getComputedStyle(p).backgroundColor;
      cx.clearRect(0,0,1,1); cx.fillStyle = '#fff'; cx.fillRect(0,0,1,1); cx.fillStyle = c; cx.fillRect(0,0,1,1);
      const d = cx.getImageData(0,0,1,1).data;
      cx.clearRect(0,0,1,1); cx.fillStyle = '#000'; cx.fillRect(0,0,1,1); cx.fillStyle = c; cx.fillRect(0,0,1,1);
      const e = cx.getImageData(0,0,1,1).data;
      res[w.dataset.layout + '|' + w.dataset.mode + '|' + r] = [d[0], d[1], d[2], e[0], e[1], e[2]];
    }
  });
  return res;
}
"""


def probe_page(site: Path, layouts: list, roles: list) -> Path:
    """A page of bare [data-layout] wrappers (no data-theme: the OS preference decides) with one
    probe per role, loading the same CSS as the design-system page."""
    css = sorted((site / "assets" / "css" / "layouts").glob("*.css"))
    links = ["tokens.css"] + ["layouts/" + f.name for f in css] + ["base.css", "parts-shell.css", "parts-scores.css",
                                                                   "parts-data.css", "fallbacks.css"]
    html = ["<!doctype html><meta charset=utf-8>"] + ['<link rel=stylesheet href="assets/css/%s">' % l for l in links]
    for lid in layouts:
        for mode, attr in (("plain", ""), ("league", " data-league-colour")):
            html.append('<div data-layout="%s" data-mode="%s"%s>' % (lid, mode, attr))
            html += ['<div data-role="%s" style="height:4px;background-color:var(--st-%s)"></div>' % (r, r) for r in roles]
            html.append("</div>")
    path = site / "probe.html"
    path.write_text("\n".join(html), encoding="utf-8")
    return path


def alpha(css: str) -> float:
    m = re.match(r"rgba?\(([^)]*)\)", css)
    if not m:
        return 1.0
    parts = [p for p in re.split(r"[\s,/]+", m.group(1).strip()) if p]
    return float(parts[3]) if len(parts) == 4 else 1.0


def rgb(css: str):
    m = re.match(r"rgba?\(([^)]*)\)", css)
    if not m:
        return None
    return tuple(float(p) for p in re.split(r"[\s,/]+", m.group(1).strip())[:3])


def collect(page_path: Path, browser, scheme: str):
    ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1500, "height": 900})
    page = ctx.new_page()
    page.goto("file://" + str(page_path), wait_until="load")
    page.wait_for_timeout(300)
    data = page.evaluate(_COLLECT)
    return ctx, page, data


def close_text(a: str, b: str) -> bool:
    """Two gradient strings equal apart from colour channels off by 1 (8-bit rounding) or alpha by 0.01."""
    num = re.compile(r"-?\d+\.?\d*")
    if num.sub("#", a) != num.sub("#", b):
        return False
    return all(abs(float(x) - float(y)) <= 1.01 for x, y in zip(num.findall(a), num.findall(b)))


def compare(modern: list, old: list) -> dict:
    """Differences between the two renders. Frames with a league colour (data-league-colour) are
    reported separately: there the old browser loses the league's colour by design."""
    res = {"frames": len(modern), "elements": 0, "bg_lost": [], "diffs": {}, "diffs_custom": {}}
    for m, o in zip(modern, old):
        assert (m["cap"], len(m["els"])) == (o["cap"], len(o["els"])), "different pages: %s" % m["cap"]
        for em, eo in zip(m["els"], o["els"]):
            res["elements"] += 1
            sel = em[0]
            # a league's own team colour loses its dark-theme lift (known, documented); a league colour is lost
            bucket = (res["diffs_custom"] if m["custom"] or "st-team--custom" in sel else res["diffs"])
            if em[8] == "none":
                continue
            for k, name in ((1, "background-color"), (2, "color"), (3, "background-image"), (4, "border-top-color")):
                if em[k] == eo[k] or (k == 3 and close_text(em[k], eo[k])):
                    continue
                if k in (1, 2, 4):
                    a, b = rgb(em[k]), rgb(eo[k])
                    if a and b and alpha(em[k]) == alpha(eo[k]) and max(abs(x - y) for x, y in zip(a, b)) <= 1:
                        continue
                    if a and b and abs(alpha(em[k]) - alpha(eo[k])) < 0.01 and max(abs(x - y) for x, y in zip(a, b)) <= 1.5:
                        continue
                key = (m["part"], m["layout"], m["theme"], sel, name)
                bucket.setdefault(key, (em[k], eo[k]))
                if name == "background-color" and alpha(em[k]) > 0 and alpha(eo[k]) == 0:
                    res["bg_lost"].append((m["cap"], m["part"], sel, em[k]))
                if name == "color" and em[6] and alpha(eo[k]) == 0:
                    res["bg_lost"].append((m["cap"], m["part"], sel, "text colour transparent"))
    return res


def run(shots: Path | None = None, verbose: bool = True) -> dict:
    from playwright.sync_api import sync_playwright
    exe = find_chromium()
    tmp = Path(tempfile.mkdtemp(prefix="oldsim-"))
    try:
        modern_page = make_site(tmp / "modern", old=False)
        old_page = make_site(tmp / "old", old=True)
        with sync_playwright() as pw:
            kw = {"args": ["--no-sandbox"]}
            if exe:
                kw["executable_path"] = exe
            browser = pw.chromium.launch(**kw)
            result = {"schemes": {}, "osdark": {}}
            sys.path.insert(0, str(ROOT))
            from scripts import check_contrast as cc
            layouts = cc.layout_ids()
            roles = list(cc.COLOUR_ROLES) + list(cc.LEAGUE_HELPERS)
            pm = probe_page(modern_page.parent.parent.parent, layouts, roles)
            po = probe_page(old_page.parent.parent.parent, layouts, roles)
            for scheme in ("light", "dark"):
                got = []
                for pth in (pm, po):
                    ctx = browser.new_context(color_scheme=scheme)
                    pg = ctx.new_page()
                    pg.goto("file://" + str(pth), wait_until="load")
                    got.append(pg.evaluate(_PROBE_JS, roles))
                    ctx.close()
                # the plain (no data-league-colour) wrappers must match the real page; the league ones must be
                # color-mix free and equal the plain ones in the old render
                diffs = [(k, a, b) for (k, a), b in zip(got[0].items(), got[1].values())
                         if k.split("|")[1] == "plain" and max(abs(x - y) for x, y in zip(a, b)) > 1]
                league_vs_plain = [(k, a) for k, a in got[1].items() if k.split("|")[1] == "league"
                                   and max(abs(x - y) for x, y in zip(a, got[1][k.replace("|league|", "|plain|")])) > 0]
                result["osdark"][scheme] = {"diffs": diffs, "league_vs_plain": league_vs_plain, "n": len(got[0])}
            for scheme in ("light",):               # frames force their own theme: one pass is enough
                c1, p1, modern = collect(modern_page, browser, scheme)
                c2, p2, old = collect(old_page, browser, scheme)
                result["schemes"][scheme] = compare(modern, old)
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    for page, label in ((p2, "old"), (p1, "modern")):
                        frames = page.query_selector_all(".ds-frame")
                        for rec in modern:
                            if rec["part"] in SHOT_PARTS:
                                name = "%s-%s-%s-%s%s.png" % (label, rec["part"], rec["layout"], rec["theme"],
                                                               "-leaguecolour" if rec["custom"] else "")
                                # one sport per layout is enough: skip repeats
                                if (shots / name).exists():
                                    continue
                                frames[rec["frame"]].screenshot(path=str(shots / name))
                c1.close()
                c2.close()
            browser.close()
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = run(args.shots)
    if args.json:
        print(json.dumps({k: {kk: (len(vv) if isinstance(vv, (list, dict)) else vv) for kk, vv in v.items()}
                          for k, v in res["schemes"].items()}))
    for scheme, r in res["schemes"].items():
        print("%s scheme: %d frames, %d elements; default-look differences: %d; league-colour frames differences: %d; "
              "lost fills/text: %d" % (scheme, r["frames"], r["elements"], len(r["diffs"]), len(r["diffs_custom"]), len(r["bg_lost"])))
        for key, (a, b) in list(r["diffs"].items())[:40]:
            print("  DIFF", key, a, "->", b)
        for item in r["bg_lost"][:20]:
            print("  LOST", item)
    for scheme, r in res["osdark"].items():
        print("OS %s preference (no data-theme): %d role probes; plain differs from modern: %d; "
              "data-league-colour differs from plain: %d" % (scheme, r["n"], len(r["diffs"]), len(r["league_vs_plain"])))
        for d in r["diffs"][:20] + r["league_vs_plain"][:10]:
            print("  DIFF", d)
    bad = sum(len(r["diffs"]) + len(r["bg_lost"]) for r in res["schemes"].values())
    bad += sum(len(r["diffs"]) + len(r["league_vs_plain"]) for r in res["osdark"].values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
