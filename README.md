# scorers-table

A free website template for a small recreational league: standings, schedule,
results, player stats and past seasons, kept from the league's own paper score
sheets. Made for volunteer-run leagues of older players, where one person keeps
the numbers and most people check them on a phone.

Sports: basketball, curling, hockey and slo-pitch (more later). Six layouts,
light and dark. No ads, no trackers, players shown as "First L." only.

**Status: the core works, and basketball and curling are real sports** (stage 5: basketball is merged, curling is in
review as a pull request); hockey and slo-pitch come next, one at a time. The template ships set up for basketball with made-up
sample seasons. A made-up test sport (`stub`) stays for the core's own tests.
What it is: [`BRIEF.md`](BRIEF.md); how it gets built: [`PLAN.md`](PLAN.md); the designs and design system:
[`docs/design.md`](docs/design.md); how the core works: [`docs/stage-4-spec.md`](docs/stage-4-spec.md); the data
files, for the person who keeps the numbers: [`docs/data.md`](docs/data.md); adding a sport:
[`docs/sports.md`](docs/sports.md); each sport's game file, box by box: [`sports/basketball/README.md`](sports/basketball/README.md),
[`sports/curling/README.md`](sports/curling/README.md);
what the league still has to decide: [`docs/open-questions.md`](docs/open-questions.md).

**Try it** (Python 3.12+, Ruby 3.3+):

```
pip install -r requirements.txt
bundle install
python scripts/build.py --sample      # checks the data, works out the numbers, writes _data/computed/ and the page stubs
bundle exec jekyll serve              # http://localhost:4000/
```

`league.yml` is the one file a setup person edits. Until a league has its own games, the site shows a
made-up sample season with a banner (`sample_data: true`).

**Choosing a sport.** `sport:` in `league.yml` names a folder in `sports/`. It ships as `basketball`. A curling club
writes `sport: curling` (and its own `name`, `timezone` and `rules:`); the site then uses the Curling look, rinks,
ends and the hammer, and the data files are the curling ones (`sports/curling/README.md` has the score card box by
box, `docs/data.md` the files around it). To see it before switching, run `python scripts/make_sample.py` with
`sport: curling` in `league.yml` (it rewrites the made-up `data/sample-*` for that sport; the template's own
copies are basketball's), then `python scripts/build.py --sample`, or just open the `/curling/` preview below. The
settings a curling league decides (ends, extra end, ties, forfeit, tiebreakers) show as `[placeholder]` until it
sets them; the build lists them (`docs/open-questions.md`, section 6).

**Previews.** Two settings in `league.yml` publish made-up copies of the site beside the real one. Neither is linked
from the league's own pages, and every page of both says `noindex`.

| Address | What it shows | Setting |
|---|---|---|
| `/preview/` | the league's own site (its name, colours, logo, look) filled with made-up games | `preview: true` (the default); built only while the real data is showing (`sample_data: false`) |
| `/basketball/`, `/curling/` (later `/hockey/`, `/slopitch/`) | the template's own made-up league for that sport (Riverside Masters Basketball, Pine Lake Curling Club), in the sport's look, with the sport's usual rules | `sport_previews: true` (shipped on); `false` turns them all off, or list the ones you want, like `[curling]` |

The banner at the top of each copy says what it is and links back to the live site (and across to the other
sport previews). To turn them off, set `preview: false` and `sport_previews: false`. To build them on your own
computer, run `bundle exec jekyll build` and then `scripts/build_preview.sh`: it writes `_site/preview/` and
`_site/<sport>/`, then puts your own data back. Details: [`docs/data.md`](docs/data.md#sample-data-and-the-preview-copies).

**Publish it** (the full setup guide comes in stage 8). The site is built and published by the GitHub Actions
workflow in `.github/workflows/build.yml`; nothing in `_config.yml` needs editing.

1. In the repository's **Settings > Pages**, set **Source** to **GitHub Actions**. Do this before the first push
   to `main`: until then the workflow's "Set up Pages" step fails.
2. Push to `main` (or use **Actions > Build and deploy > Run workflow**). The site appears at
   `https://<owner>.github.io/<repository>/`, or at the custom domain set on the same Settings page.
3. Every pull request runs the same checks without publishing, and a nightly run (at `nightly_hour` in `league.yml`) keeps "next game day" and the
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

A league that used to keep its numbers on the Masters basketball site can convert that data folder with
`python sports/basketball/convert_masters.py --from <masters>/data --to <new folder>` (it prints the
`league.yml` lines for the Masters rules; see `sports/basketball/README.md`).

It grows out of the website of a real masters basketball league, which has
run this way since October 2026.

Licence: MIT ([`LICENSE`](LICENSE)).
