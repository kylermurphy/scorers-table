"""Parity: the Jekyll includes print the same markup as the stage 3 specimens (docs/stage-4-spec.md 5.4).

For every part the design-system page shows (scripts/design_system/specimens_*.py), in every layout and sport
it is shown for, light and dark, this renders the specimen function in Python and the matching includes in a
throwaway Jekyll site, and compares the two. The site is built ONCE for all cases (tests/parity/site.py): the
repo's _includes/shell and _includes/parts, the sample leagues converted to the computed-JSON shapes by
scripts/design_system/contract.py, and one page per (layout, sport). A difference fails the test with the part,
layout, sport, theme, the path to the first differing node and both snippets.

THE COMPARISON RULES (tests/parity/htmlcompare.py has the code; nothing else is relaxed):
  1. Tags, child order and child counts must match exactly.
  2. Every attribute is compared, except: `class` as a set; `style` ignoring spaces around `:` and `;`;
     `href` by presence only (specimens use "#", includes use site paths); `id`, `hidden` and
     `aria-labelledby` ignored (ids exist to be pointed at; the theme button is rendered `hidden`).
  3. Text is compared with whitespace collapsed; a space counts only between two inline neighbours.
  4. In the dark-theme header the theme button's `aria-label` and contents are ignored (the specimen shows the
     sun; the include always renders the moon and site.js swaps it).
  Light and dark use the same include output, so one render is compared with both specimens.

WHAT IS COVERED: every generic part in every layout and sport it is shown for (header, nav, theme button,
ticker, footer, page title, section heading, banner, skip link, result card, hero, final panel, line score,
standings and the race, leader tiles and lists, game row, next-game panel, team card, team colours) and, as a
fragment, the generic stat table and note blocks (basketball's box scores).
WHAT IS SKIPPED, and why: tests/parity/cases.py SKIPPED (event log, roster and the sport game tables are stage 5
parts, built with their sports).

The test needs Ruby, Bundler and the gems (`bundle install`); without them it is skipped with a message. Mark:
`jekyll` (pytest.ini registers it).
"""
from __future__ import annotations

import pytest

from scripts.design_system import sample
from scripts.design_system.model import Ctx
from tests.parity import cases as cases_mod
from tests.parity import htmlcompare, site

pytestmark = pytest.mark.jekyll


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    command = site.jekyll_command()
    if command is None:
        site.skip_unless_ci("parity needs Ruby, Bundler and the gems: run `bundle install` (the Gemfile is in the "
                            "repo root); CI always runs this test")
    return site.build_site(tmp_path_factory.mktemp("parity"), command)


def _expected(part, layout: str, sport: str, theme: str) -> str:
    lay = sample.LAYOUT_BY_ID[layout]
    ctx = Ctx(layout=layout, theme=theme, sport=sport, league=sample.LEAGUES[sport], layout_meta=lay)
    return part.render(ctx)


CASES = cases_mod.all_cases()


@pytest.mark.parametrize("case,part", CASES, ids=[c.id for c, _ in CASES])
def test_includes_match_specimen(rendered, case, part):
    failures = []
    checked = 0
    for layout, sport in cases_mod.combos(part, case.sports):
        actual = rendered[(layout, sport)][case.id]
        for theme in ("light", "dark"):
            expected = _expected(part, layout, sport, theme)
            diff = htmlcompare.compare_fragments(
                expected, actual, mask_toggle=(part.id == "header" and theme == "dark"), drop_expected=case.drop)
            checked += 1
            if diff:
                path, message, snip_exp, snip_act = diff
                failures.append(f"{part.id} / {layout} / {sport} / {theme}\n  at {path}\n  {message}\n"
                                f"  specimen: {snip_exp}\n  include:  {snip_act}")
    assert checked, f"{case.id}: no (layout, sport) combination was compared"
    assert not failures, (f"{len(failures)} of {checked} comparisons differ. First difference:\n"
                          + "\n".join(failures[:3]))


@pytest.mark.parametrize("part_id,reason", sorted(cases_mod.SKIPPED.items()))
def test_skipped_parts_are_listed(part_id, reason):
    """The parts the parity test leaves out are named with their reason (shown by `pytest -rs`)."""
    parts = {p.id for p in cases_mod.load_parts()}
    assert part_id in parts, f"{part_id} is skipped but is not a specimen part any more"
    pytest.skip(f"{part_id}: {reason}")


def test_every_specimen_part_is_a_case_or_skipped():
    """A new specimen part must get a case (or an explicit skip), so the includes cannot silently fall behind."""
    covered = {c.part for c, _ in CASES} | set(cases_mod.SKIPPED)
    missing = [p.id for p in cases_mod.load_parts() if p.id not in covered]
    assert not missing, f"specimen parts without a parity case or a listed skip: {missing}"


# ---------------------------------------------------------------- what no specimen draws

def test_logo_replaces_the_monogram(rendered):
    html = rendered[("extras", "extras-logo")]["x-logo"]
    assert html.count("<img ") == 2
    assert 'src="/assets/league/logo.svg"' in html
    assert 'role="img"' not in html                      # no monogram badge any more
    assert 'alt=""' in html                              # the footer's copy is decoration


def test_plain_stat_table_unknown_block_and_no_line_score(rendered):
    page = rendered[("extras", "extras-plain")]
    blocks = page["x-blocks"]
    assert '<table class="st-table"><caption' in blocks and "st-table--box" not in blocks
    assert "<td>Total</td>" in blocks and 'class="st-player"' in blocks and ">#4 " not in blocks
    assert "mystery" not in blocks and "End of blocks." in blocks     # an unknown block type is left out
    card = page["x-card"]                                              # lines=true without a line score: two rows
    assert "st-result-card--lines" not in card and "st-result-card__score" in card


def test_top_performer_tiles_link_a_player_with_a_page_and_use_a_span_without_one(rendered):
    blocks = rendered[("extras", "extras-plain")]["x-blocks"]
    first, second = blocks.split('</span></p></div>')[:2]                 # two tiles, one per tied player
    assert first.count("st-top-scorer__name") == 1 and second.count("st-top-scorer__name") == 1
    assert '<a class="st-top-scorer__name" href="/players/dave-m/">#23 Dave M.</a>' in first
    assert '<p class="st-top-scorer__detail">Rapids · 6-7 free throws</p>' in first
    assert '<span class="st-top-scorer__name">#9 Rob K.</span>' in second and "<a " not in second
    assert "st-top-scorer__detail" not in second                          # no detail, no empty line
    assert '<span class="st-top-scorer__num">24</span><span class="st-top-scorer__unit">Points' in second


def test_ticker_lists_every_bye_and_ends_without_a_separator(rendered):
    html = rendered[("extras", "extras-plain")]["x-ticker"]
    assert html.count("st-ticker__item--quiet") == 2 and "FOX bye" in html and "HER bye" in html
    assert html.count("st-ticker__sep") == html.count("st-ticker__tag")   # one after each score, none after the byes


def test_every_rendered_link_has_a_target(rendered):
    import re
    for combo, blocks in rendered.items():
        for case_id, html in blocks.items():
            for tag in re.findall(r"<a [^>]*>", html):
                m = re.search(r'href="([^"]*)"', tag)
                assert m and m.group(1), f"{combo} {case_id}: link without a target: {tag}"


# ---------------------------------------------------------------- source checks (no Jekyll needed)

@pytest.mark.parametrize("name", ["league.sport", "sport ==", "sport_name"])
def test_includes_never_test_the_sport(name):
    """Sport differences arrive as data (spec 5.2); an include may branch on the layout, never on the sport."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "_includes"
    hits = [str(p.relative_to(root)) for p in root.rglob("*.html") if name in p.read_text()]
    assert not hits, f"{name!r} found in {hits}"


def test_includes_do_not_write_a_root_relative_path():
    """Every internal path goes through relative_url (CLAUDE.md); a leading '/' in an href or src is a bug."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "_includes"
    bad = []
    for p in root.rglob("*.html"):
        for m in re.finditer(r'(?:href|src)="/[^"]*"', p.read_text()):
            bad.append((p.name, m.group(0)))
    assert not bad, bad


def test_no_liquid_error_message_reached_a_page(rendered):
    for combo, blocks in rendered.items():
        for case_id, html in blocks.items():
            assert "Liquid error" not in html and "Liquid syntax" not in html, (combo, case_id)
