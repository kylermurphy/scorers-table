# scorers-table

A free website template for a small recreational league: standings, schedule,
results, player stats and past seasons, kept from the league's own paper score
sheets. Made for volunteer-run leagues of older players, where one person keeps
the numbers and most people check them on a phone.

Sports: basketball, curling, hockey and slo-pitch (more later). Six layouts,
light and dark. No ads, no trackers, players shown as "First L." only.

**Status: the core works with one made-up test sport (`stub`).** The four real sports come next (stage 5).
What it is: [`BRIEF.md`](BRIEF.md); how it gets built: [`PLAN.md`](PLAN.md); the designs and design system:
[`docs/design.md`](docs/design.md); how the core works: [`docs/stage-4-spec.md`](docs/stage-4-spec.md); the data
files, for the person who keeps the numbers: [`docs/data.md`](docs/data.md); adding a sport:
[`docs/sports.md`](docs/sports.md).

**Try it** (Python 3.12+, Ruby 3.3+):

```
pip install -r requirements.txt
bundle install
python scripts/build.py --sample      # checks the data, works out the numbers, writes _data/computed/ and the stub pages
bundle exec jekyll serve              # http://localhost:4000/
```

`league.yml` is the one file a setup person edits. Until a league has its own games, the site shows a
made-up sample season with a banner (`sample_data: true`).

**Publish it** (the full setup guide comes in stage 8). The site is built and published by the GitHub Actions
workflow in `.github/workflows/build.yml`; nothing in `_config.yml` needs editing.

1. In the repository's **Settings > Pages**, set **Source** to **GitHub Actions**. Do this before the first push
   to `main`: until then the workflow's "Set up Pages" step fails.
2. Push to `main` (or use **Actions > Build and deploy > Run workflow**). The site appears at
   `https://<owner>.github.io/<repository>/`, or at the custom domain set on the same Settings page.
3. Every pull request runs the same checks without publishing, and a nightly run keeps "next game day" and the
   calendar files current. GitHub pauses scheduled runs in a repository with no activity for 60 days; the
   Actions tab has a button to turn them back on.

**See the design system.** Clone the repository and open `docs/design-system/index.html` in a browser (GitHub
shows HTML as source, not as a page). For one self-contained file, run
`python scripts/build_design_system.py --inline --out design-system-inline.html`.

**Run the checks:**

```
python -m pytest                      # every test (the Jekyll tests need `bundle install`)
python scripts/check_contrast.py      # WCAG AA for every colour pair; writes docs/contrast.md; must pass
python scripts/build.py --check       # validate the data only; writes nothing
```

It grows out of the website of a real masters basketball league, which has
run this way since October 2026.

Licence: MIT ([`LICENSE`](LICENSE)).
