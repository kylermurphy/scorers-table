"""A long game's line score keeps a minimum cell width and scrolls in its own box (assets/css/parts-scores.css)
instead of squeezing the digits together; a short game still fits with no scroll."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.parity.site import skip_unless_ci  # noqa: E402

CSS = ROOT / "assets" / "css"


def _page(innings: int) -> str:
    head = "".join(f"<th scope='col'>{i}</th>" for i in range(1, innings + 1))
    row = lambda who: f"<tr><th scope='row' class='st-line-score__team'>{who}</th>" + "".join("<td>0</td>" for _ in range(innings)) + \
        "<td class='st-line-score__total'>1</td><td class='st-line-score__extra'>2</td><td class='st-line-score__extra'>0</td></tr>"
    links = "".join(f"<link rel='stylesheet' href='file://{CSS}/{f}'>" for f in
                    ("tokens.css", "layouts/slopitch.css", "base.css", "parts-shell.css", "parts-scores.css"))
    return (f"<html data-layout='slopitch' data-theme='light'><head>{links}</head><body style='margin:0;width:326px'>"
            "<div class='st-line-scroll'><table class='st-line-score st-line-score--innings st-line-score--full'>"
            f"<thead><tr><th scope='col' class='st-line-score__team'>Inning</th>{head}<th class='st-line-score__total'>R</th>"
            "<th class='st-line-score__extra'>H</th><th class='st-line-score__extra'>E</th></tr></thead>"
            f"<tbody>{row('A')}{row('B')}</tbody></table></div></body></html>")


def test_a_long_line_score_scrolls_instead_of_squeezing(tmp_path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip_unless_ci("Playwright is not installed")
        return
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as err:  # noqa: BLE001
            skip_unless_ci(f"Chromium is not available: {err}")
            return
        out = {}
        for n in (7, 10):
            f = tmp_path / f"{n}.html"
            f.write_text(_page(n), encoding="utf-8")
            pg = browser.new_page(viewport={"width": 360, "height": 600})
            pg.goto(f.as_uri())
            out[n] = pg.evaluate("""() => { const s = document.querySelector('.st-line-scroll');
                const w = [...document.querySelectorAll('tbody tr:first-child td')].slice(0, -3).map(c => c.getBoundingClientRect().width);
                return {scrolls: s.scrollWidth > s.clientWidth, min: Math.min(...w)}; }""")
        browser.close()
    assert out[10]["scrolls"] and out[10]["min"] >= 20, out
    assert not out[7]["scrolls"], out
