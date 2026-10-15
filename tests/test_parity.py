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
        pytest.skip("parity needs Ruby, Bundler and the gems: run `bundle install` (the Gemfile is in the repo "
                    "root); CI always runs this test")
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
