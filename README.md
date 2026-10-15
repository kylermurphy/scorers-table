# scorers-table

A free website template for a small recreational league: standings, schedule,
results, player stats and past seasons, kept from the league's own paper score
sheets. Made for volunteer-run leagues of older players, where one person keeps
the numbers and most people check them on a phone.

Sports: basketball, curling, hockey and slo-pitch (more later). Six layouts,
light and dark. No ads, no trackers, players shown as "First L." only.

**Status: being designed.** Nothing to install yet. What it will be:
[`BRIEF.md`](BRIEF.md); how it gets built: [`PLAN.md`](PLAN.md); the designs and design system:
[`docs/design.md`](docs/design.md). Stage 3 (the design system) is in review.

**See the design system.** Clone the repository and open `docs/design-system/index.html` in a browser (GitHub
shows HTML as source, not as a page). For one self-contained file, run
`python scripts/build_design_system.py --inline --out design-system-inline.html`.

**Run the checks** (Python 3; the scripts use only the standard library, the tests need `pip install pytest`):

```
python scripts/check_contrast.py      # WCAG AA for every colour pair; writes docs/contrast.md; must pass
python -m pytest                      # tests
python scripts/build_design_system.py # rebuild the design-system page after changing the CSS
```

It grows out of the website of a real masters basketball league, which has
run this way since October 2026.

Licence: MIT ([`LICENSE`](LICENSE)).
