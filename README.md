# scorers-table

A free website template for a small recreational league: standings, schedule,
results, player stats and past seasons, kept from the league's own paper score
sheets. Made for volunteer-run leagues of older players, where one person keeps
the numbers and most people check them on a phone.

Sports: basketball, curling, hockey and slo-pitch (more later). Six layouts,
light and dark. No ads, no trackers, players shown as "First L." only.

**Status: the core works, and basketball and curling are real sports** (stage 5, both merged); hockey and slo-pitch
come next, one at a time. The template ships set up for basketball with made-up sample seasons. A made-up test sport
(`stub`) stays for the core's own tests. This repository's own website is a **showcase**: a landing page that shows
each sport's demo league (the pull request for it is in review; see [The showcase front page](#the-showcase-front-page)).
What it is: [`BRIEF.md`](BRIEF.md); how it gets built: [`PLAN.md`](PLAN.md); the designs and design system:
[`docs/design.md`](docs/design.md); how the core works: [`docs/stage-4-spec.md`](docs/stage-4-spec.md); the data
files, for the person who keeps the numbers: [`docs/data.md`](docs/data.md); adding a sport:
[`docs/sports.md`](docs/sports.md); each sport's game file, box by box: [`sports/basketball/README.md`](sports/basketball/README.md),
[`sports/curling/README.md`](sports/curling/README.md);
what the league still has to decide: [`docs/open-questions.md`](docs/open-questions.md).

## Try it

Python 3.12+, Ruby 3.3+:

```
pip install -r requirements.txt
bundle install
python scripts/build.py --sample      # checks the data, works out the numbers, writes _data/computed/ and the page stubs
bundle exec jekyll serve              # http://localhost:4000/
```

`league.yml` is the one file a setup person edits. Until a league has its own games, the site shows a
made-up sample season with a banner (`sample_data: true`).

That is a league's site, at `http://localhost:4000/`. This repository itself ships as a showcase, with a landing page
at the front instead: see [The showcase front page](#the-showcase-front-page) for how to see it.

## Choosing a sport

`sport:` in `league.yml` names a folder in `sports/`. It ships as `basketball`. A curling club
writes `sport: curling` (and its own `name`, `timezone` and `rules:`); the site then uses the Curling look, rinks,
ends and the hammer, and the data files are the curling ones (`sports/curling/README.md` has the score card box by
box, `docs/data.md` the files around it). To see it before switching, run `python scripts/make_sample.py` with
`sport: curling` in `league.yml` (it rewrites the made-up `data/sample-*` for that sport; the template's own
copies are basketball's), then `python scripts/build.py --sample`, or just open the `/curling/` preview below. The
settings a curling league decides (ends, extra end, ties, forfeit, tiebreakers) show as `[placeholder]` until it
sets them; the build lists them (`docs/open-questions.md`, section 6).

## Previews

Two settings in `league.yml` publish made-up copies of the site beside the real one. Neither is linked
from the league's own pages, and every page of both says `noindex`. (A third setting, `landing_page`, decides what
is at the front page: the next section.)

| Address | What it shows | Setting |
|---|---|---|
| `/preview/` | the league's own site (its name, colours, logo, look) filled with made-up games | `preview: true` (the default); built only while the real data is showing (`sample_data: false`) and not while `landing_page: true` |
| `/basketball/`, `/curling/` (later `/hockey/`, `/slopitch/`) | the template's own made-up league for that sport (Riverside Masters Basketball, Pine Lake Curling Club), in the sport's look, with the sport's usual rules | `sport_previews: true` (shipped on); `false` turns them all off, or list the ones you want, like `[curling]` |

The banner at the top of each copy says what it is and links back to the live site (on the showcase the link
reads "All sports") and across to the other sport previews. To turn them off, set `preview: false` and `sport_previews: false` (a showcase
needs its demos, so with `landing_page: true` the second is an error: set `landing_page: false` first). To build them on your own
computer, run `bundle exec jekyll build` and then `scripts/build_preview.sh`: it writes `_site/preview/` and
`_site/<sport>/`, then puts your own data back. Details: [`docs/data.md`](docs/data.md#sample-data-and-the-preview-copies).

## The showcase front page

This repository is the template and also the template's own website. With `landing_page: true` in `league.yml`
(**the shipped value**), the front page `/` is a **landing page**, in the Basketball look, that shows what the
template does:

* a card for every sport that has a demo (today Basketball and Curling): the sport's name, a one-line description,
  a small live preview in the sport's own look (the top 3 of its standings and its latest result, from its made-up
  league) and a button to the demo, `/basketball/` or `/curling/`;
* a "Coming soon" card, with no link, for each sport planned but not built (Hockey and Slo-pitch);
* "Get started": a link to the setup guide (for now the [Publish it](#publish-it) steps below, until the written
  guide of stage 8 exists), a link to this repository on GitHub, and what every league gets.

The preview numbers are worked out on every build the same way the demo itself is, so a card always agrees with the
demo it links to; nothing on it is typed in. The page works on a 360 px phone, in light and dark, with JavaScript off,
and says `noindex` unless `search_engines: true`. The design-system page is not linked from it. Each demo's banner
says "All sports" and links back to the landing page.

**A league that copies this template sets `landing_page: false`** in `league.yml` (the line sits at the top, beside
`name`, `sport` and `timezone`, and the landing page and every build say so). Then the front page is the league's
own site, as in "Try it" above. Until you do, your copy shows this landing page, not your league.

| `landing_page` | `sport_previews` | What is at `/` |
|---|---|---|
| `false`, or the line left out | anything | the league's own site (`/schedule/`, `/stats/`, `/teams/`, `/archive/`, `/rules/`...) |
| `true` | `true` or a list of sports | the landing page, with a card for each sport listed (`true` = every sport with a demo) |
| `true` | `false` or left out | an error: there would be no demos to show |

With the landing page on, the root holds only the landing page and the "page not found" page. The league's own pages
(`/schedule/`, `/stats/`...) are not built there at all, so those old addresses do not exist on a showcase site, the
sample league is at `/basketball/` only, and `/preview/` is not built (`preview` and `sample_data` do nothing at the
root). Your league's data is still loaded and checked on every build. Details:
[`docs/data.md`](docs/data.md#the-front-page-landing_page-and-the-two-preview-settings).

**The words** are in two places. `landing.yml` (next to `league.yml`; read only while the landing page is on, and a
league that turns it off can delete it) holds the page's own text: the header name, badge and tagline, the title and
intro, the two menu items, the links, the "What every league gets" list and the **coming-soon list**. A sport's
one-line description is the `blurb:` in its own `sports/<id>/sport.yml` (at most 100 characters). The build checks
both and names the line to fix.

**Adding a sport's card.** It appears by itself: give the sport a `sample.py` (a demo league) and a `blurb:` in its
`sport.yml`, and the next build adds its card, the preview in its look, and its link. Nothing else changes. Then take
the sport off `coming_soon` in `landing.yml`; until you do, the build warns that the sport "has a demo now, so it
gets a real card" and drops the coming-soon card itself. A sport you only plan goes on `coming_soon` (an `id`, a
`name` and a `blurb`). Hockey and slo-pitch switch from "Coming soon" to live this way when those stages land
(`docs/sports.md`, "Sport previews and the landing page").

**See it on your computer** (after `pip install` and `bundle install`):

```
python scripts/build.py                                              # writes landing.json and _config.landing.yml, then prints the note below
bundle exec jekyll build --config _config.yml,_config.landing.yml     # the landing page, into _site/
scripts/build_preview.sh                                              # adds the demos its buttons open: _site/basketball/ and _site/curling/
python -m http.server 4000 --directory _site                          # http://localhost:4000/
```

Each Jekyll build empties `_site/` first, so run `build_preview.sh` after the last Jekyll build, and look at `_site/`
with a plain file server as above rather than `jekyll serve` (which would rebuild and delete the demos). For the
landing page alone, `bundle exec jekyll serve --config _config.yml,_config.landing.yml` works, and its two demo
buttons then lead nowhere.

Every plain `python scripts/build.py` run while the switch is on prints "The front page is the scorers-table landing
page. For your league's own site, set landing_page: false in league.yml." The landing page itself says it too.
`_config.landing.yml` is written by the build (git-ignored; never edit it). While the switch is off it holds the
single line `landing_page: false` and changes nothing.

## Publish it

The full setup guide comes in stage 8; this is the short version. The site is built and published by the GitHub
Actions workflow in `.github/workflows/build.yml`; nothing in `_config.yml` needs editing.

1. In `league.yml`, set `name`, `sport` and `timezone`, and **`landing_page: false`** so your league's own site is
   the front page (the template ships with the showcase landing page on). Add your seasons' data as
   [`docs/data.md`](docs/data.md) describes.
2. In the repository's **Settings > Pages**, set **Source** to **GitHub Actions**. Do this before the first push
   to `main`: until then the workflow's "Set up Pages" step fails.
3. Push to `main` (or use **Actions > Build and deploy > Run workflow**). The site appears at
   `https://<owner>.github.io/<repository>/`, or at the custom domain set on the same Settings page.
4. Every pull request runs the same checks without publishing, and a nightly run (at `nightly_hour` in `league.yml`) keeps "next game day" and the
   calendar files current. GitHub pauses scheduled runs in a repository with no activity for 60 days; the
   Actions tab has a button to turn them back on.

## See the design system

Clone the repository and open `docs/design-system/index.html` in a browser (GitHub
shows HTML as source, not as a page). For one self-contained file, run
`python scripts/build_design_system.py --inline --out design-system-inline.html`.

## Run the checks

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
