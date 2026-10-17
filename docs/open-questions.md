# Open questions

Things the template does not decide for a league, and decisions still waiting for the owner. Every
`[placeholder]` shown on the site is listed here, as `CLAUDE.md` asks. Nothing here is invented as a
fact: where a rule is unknown the page shows the text in square brackets.

## 1. Placeholders visible in the sample data

These appear on the design-system page (`docs/design-system/index.html`) because the sample leagues are
made up. A real league replaces each one in its own files.

| Placeholder | Where it shows | Sample league | Who decides |
|---|---|---|---|
| `[Gym name]` | footer line, next-game panel, game page date line | Riverside Masters Basketball | the league: the venue |
| `[playoff format]` | standings note: "2 points a win. Playoffs: [playoff format]." | Riverside Masters Basketball | the league: how many teams, how many rounds, when |
| `[Club address]` | next-game panel | Pine Lake Curling Club | the league: the club's address |
| `[Arena name]` | footer line ("Sunday nights at [Arena name]"), next-game panel, game page venue line | Northside Old-Timers Hockey | the league: the rink |
| `[Park name]` | next-game panel, game page venue line | Maple Park Slo-Pitch | the league: the park |
| `[placeholder]` after "Tiebreakers:" | standings note ("2 points a win, 1 a tie. Tiebreakers: [placeholder].") | Pine Lake Curling, Northside Hockey, Maple Park Slo-Pitch | the league: the order of tiebreakers |

Basketball is the shipped sport now (stage 5), so the built basketball site shows its own placeholders:
see [section 5](#5-stage-5-basketball-placeholders-and-decisions). Curling's are in
[section 6](#6-stage-5-curling-placeholders-and-decisions).

## 2. Rules a league has to decide

`BRIEF.md` gives "typical club rules" as defaults. These are the choices behind them. Each one is a
setting later (stages 4 and 5) and shows as a `[placeholder]` until the league answers.

**Every sport**
* Tiebreakers for standings, in order.
* Playoff format and which games count as playoffs.
* Whether ties are allowed in the regular season, and how a forfeit is scored.

**Basketball** (built; the settings are in [section 5](#5-stage-5-basketball-placeholders-and-decisions))
* Points for a win (the default is 2) or the Masters rule (1 per quarter won and 3 per win, a README preset).
* Whether overtime is played, whether ties are allowed, and how a forfeit is scored.
* How many personal fouls a player may have in a game.
* Whether a minimum number of games or free throws is needed to be ranked.

**Curling** (built; the settings are in [section 6](#6-stage-5-curling-placeholders-and-decisions))
* 8 or 6 ends (any number from 4 to 10); whether an extra end is played when tied or the game is a tie.
* Whether a team may concede early: built as "after any complete end, while behind, no minimum" (the sample shows
  "Shook hands after 6"); not a setting.
* The order of tiebreakers: head-to-head, then points for and against.
* Ties, and how a forfeit is scored.

**Hockey**
* Ties, overtime or a shootout, and whether an overtime loss gets a point.
* Goal caps per player per game, where a league uses them.

**Slo-pitch**
* The run limit per inning (the sample uses 5, with an open last inning), the mercy rule and the time limit.
* Home-run limits and co-ed batting-order rules.
* The score recorded for a forfeit (such as 7-0).
* Whether the league keeps batting stats at all, and the minimum at-bats for the batting average.

**Leaderboard minimums.** The sample shows "Minimum 15 at-bats to qualify for average" (slo-pitch) and "Goalies
need 4 games played to rank" (hockey). These numbers are invented. They should become league settings
or `[placeholder]`s.

## 3. Decisions

The stage 3 decisions are written out in `docs/design.md`, under "Decisions made in stage 3", and were
**confirmed by the owner on 15 October 2026** (team palettes follow the layout; the team card design; the
changed mockup colours; the curling header line exception; the structure the mockups did not draw; the
old-browser floor; fixed scenes; the "Scored with hammer" 3 of 5 correction). The three open items from
`BRIEF.md` were settled the same day: search engines default **off** (noindex); setup help is a **written
guide** only; **desktop** layouts wait for stage 9.

Nothing is waiting for the owner at the end of stage 3.

## 4. Stage 4: placeholders the built site shows

With the stage 4 `league.yml` (sport `stub`, sample data on; the stub is still the core's test sport), the build prints a "Still to decide" list and the
site shows these until a league fills them in. None of them is a league fact the template invents.

| Placeholder | Where it shows | Who fills it in |
|---|---|---|
| `[Gym name]` | `venue` of the real season in `data/seasons.yml`: footer line, next-game panel, game pages | the league: where it plays |
| `[Venue]` | the same places in the sample seasons | nobody: sample data |
| `[League rules]` | the Rules page (`rules/index.md`) | the league: its written rules |
| `[placeholder]` for Overtime, Forfeit, Tiebreakers, minimum games for the points-per-game leaders | standings note, Rules page, leaderboard notes | the league, in `league.yml` (`rules`, `standings`, `stats.minimums`) |

A real sport (stage 5) brings its own `decide: true` settings; each is listed by the build the same way.

## 5. Stage 5, basketball: placeholders and decisions

### 5.1 What the build lists

`league.yml` now ships with `sport: basketball` and `sample_data: true`. `python scripts/build.py --sample` prints
this list, and the site shows `[placeholder]` for each until a league sets it (even to the usual value). A sport
preview (`/basketball/`) always shows them, because it uses the sport's own defaults.

| Setting in `league.yml` | The default the site uses meanwhile | Where `[placeholder]` shows | Who decides |
|---|---|---|---|
| `rules.overtime` (Overtime) | `overtime`: a game level after Q4 must have its OT boxes filled in | the Rules page's "Still to decide" list (no page shows the setting itself) | the league: overtime, or none (a gym with a hard stop) |
| `rules.foul_limit` (Most personal fouls one player can have in a game) | 5 (FIBA; the owner chose it, see 5.2, question A) | the Rules page's list (no page shows the number itself) | the league |
| `standings.ties` (Ties) | `false`: a level regular-season game is an error at the Final box | the Rules page's list; "Ties are allowed [placeholder]." in the standings note where the default allows them | the league: may a regular-season game end level? |
| `standings.forfeit` (Forfeit) | 20-0 | the standings note ("A forfeit counts as 20–0 [placeholder]." while the table holds a forfeit), the forfeit's game page (a note under the score) and result card ("score [placeholder]"), and the Rules page's list | the league, and **the owner for the default** (decision 6) |
| `standings.tiebreakers` (Tiebreakers) | head-to-head, then point difference, then points for; still level share a rank | the standings note ("[placeholder] The league has not decided its tiebreakers yet..."), on Home, an archive season page and the Rules page | the league |
| `stats.minimums.ppg_min_games` (Minimum games for the points per game leaders) | 0 | "Minimum [placeholder] games played." under the PPG leaders | the league |
| `stats.minimums.ft_min_attempts` (Minimum free throw attempts for the free throw % leaders) | 10 | "Minimum [placeholder] free throw attempts." under the FT% leaders | the league |

Also left for the league, as in stage 4: `[Gym name]` (the real season's `venue`) and `[League rules]` (the Rules
page). `[Venue]` in the sample seasons is the sample's own and nobody
fills it in. The standings points for a win (2) and the columns (GP W L PTS DIFF; add `T` where ties are allowed)
are the sport's usual rule, not a placeholder; the Masters rule is a preset in `sports/basketball/README.md`.

### 5.2 Decisions for the owner

The decisions are in `docs/stage-5-basketball-spec.md`, section 10. **Decided by the owner** (October 2026): 1
(default standings: 2 points a win, ranked by points, columns GP W L PTS DIFF), 2 (overtime when level after
Q4, no ties, both shown as `[placeholder]`), 5 (personal fouls only in the box score; technical fouls count the
whole season; flagrant fouls named on the game page with the quarter, never the Notes text; no flagrant page) and
7 (the template ships with basketball; the stub stays the core's test sport).

**Built as recommended, confirmed by the owner (October 2026):**

| # | Decision | Built as |
|---|---|---|
| 3 | Quarters or halves | quarters only. The Masters sheet had halves until October 2026, so some leagues will want them; that needs period words chosen by an option (a core change) |
| 4 | Free-throw stats optional | always kept. A league that never fills in the circles sees 0-0 and dashes in the FT columns and an empty FT% board |
| 6 | Default forfeit score | 20-0, shown as `[placeholder]`. A big margin moves the point differential, which is a tiebreaker; a league can cap the differential (`{diff: {cap: 15}}`) |
| 8 | When the rules get a JavaScript copy | stage 7 with the entry page, its only user. This stage commits the shared fixtures it will be tested against |
| 9 | Sport previews in the shipped template | `league.yml` ships `sport_previews: true`, so the template's own site is the per-sport demo (`/basketball/` and `/curling/` now; `/hockey/`, `/slopitch/` as those sports land). The setting's default when the line is left out is `false`. The trade-off: a league that never reads that line publishes unlinked, noindex demo leagues, and its deploys take a little longer for each |

**A question that came up while building**

A. **The foul limit's default: 5 or 6?** *Answered by the owner (October 2026): 5, the FIBA number* (the NBA's is 6).
   `rules.foul_limit` is the most personal fouls one player can have in a game (a row with more is a check error).
   The template starts from 5 and lists it under "Still to decide" until the league sets its own number; setting it
   (even to 5) removes the placeholder.

## 6. Stage 5, curling: placeholders and decisions

### 6.1 What the build lists

A league that writes `sport: curling` in `league.yml` sees this list after every build, and the site shows
`[placeholder]` for each until the league sets it (even to the usual value). The sport preview (`/curling/`) always
shows them, because it uses the sport's own defaults. (To see the list yourself: `python scripts/build.py --sample`
with `sport: curling` in `league.yml`, or `python scripts/preview_root.py curling <folder>` and
`python scripts/build.py --root <folder> --sport-preview curling`.)

```
Still to decide (the site shows [placeholder] until you set these in league.yml):
  - Ends in a game (rules.ends)
  - Extra end when a game is level after the last end (rules.extra_end)
  - Ties (standings.ties)
  - Forfeit (standings.forfeit)
  - Tiebreakers (standings.tiebreakers)
```

| Setting in `league.yml` | The default the site uses meanwhile | Where `[placeholder]` shows | Who decides |
|---|---|---|---|
| `rules.ends` (Ends in a game) | 8 (4 to 10 are allowed; a game file has exactly this many end boxes) | the Rules page's list only (no page prints the number as a rule; the game page just has the boxes) | the league: 8, or 6 for a daytime or senior league. A season can differ (`overrides: {rules: {ends: 6}}` in `data/seasons.yml`) |
| `rules.extra_end` (Extra end when a game is level after the last end) | `playoffs`: a level regular-season game is a tie, a level playoff game goes to an extra end (`always`: every level game does) | the Rules page's list only | the league |
| `standings.ties` (Ties) | `true`: a level regular-season game is a tie, worth 1 point each | the Rules page's list; "Ties are allowed [placeholder]." in the standings note | the league. A league that never allows ties sets `extra_end: always` **and** `ties: false` |
| `standings.forfeit` (Forfeit) | 1-0 (so a forfeit barely moves the points difference that breaks ties) | the standings note ("A forfeit counts as 1–0 [placeholder]." while the table holds a forfeit), the forfeit's game page (a note under the score) and result card ("score [placeholder]"), and the Rules page's list | the league. Alternatives: `{score: [8, 0]}`, or `{score: per_period}` (1-0 in every end, which also counts 8 ends won) |
| `standings.tiebreakers` (Tiebreakers) | head-to-head, then score difference; still level share a rank | the standings note ("[placeholder] The league has not decided its tiebreakers yet..."), on Home, an archive season page and the Rules page's list | the league. Alternatives: `points_for`, or `periods_won` (ends won in the scheduled ends; an extra end is not counted there, though it is in the "Ends won" board) |

Not placeholders: standings points (2 for a win, 1 for a tie, 0 for a loss, ranked by points) and the columns
(GP W L T PTS PF PA) are the sport's usual rule; `rules.lineups` (`recorded` or `none`, whether game files list the
players) is a choice with a default, not a league decision. There are no leaderboard minimums in curling. Also left
for the league, as in every sport: the real season's `venue` (`[Gym name]` in the shipped `data/seasons.yml`; a
curling club will want to write its club name there) and `[League rules]` on the Rules page. A last-stone draw
total (a tiebreaker in competitive curling) is not on a score card and is not supported.

### 6.2 Decisions for the owner

The 13 decisions are in `docs/stage-5-curling-spec.md`, section 10. **All 13 were decided by the owner as
recommended (October 2026).** What was built:

| # | Decision | Built as |
|---|---|---|
| 1 | Ends in a game | an `ends` option, 4 to 10, default 8, `[placeholder]`. A league whose playoffs play more sets it per season only; a separate playoff number waits for a league that asks |
| 2 | Level after the last end | a tie in the regular season and extra ends in the playoffs (`extra_end: playoffs`, `ties: true`, both `[placeholder]`); `always` for leagues that play an extra end every game. An extra-end win counts as a full win (2 points). A league that never allows ties must set two things (`extra_end: always`, `ties: false`) |
| 3 | Standings points and columns | 2 for a win, 1 for a tie, 0 for a loss, ranked by points, columns GP W L T PTS PF PA. Team stats (stolen ends...) are not columns by default, to keep the table narrow at 360 px; a league can add them |
| 4 | Tiebreakers | head-to-head, then points difference, `[placeholder]`. `points_for` and `periods_won` are the alternatives |
| 5 | Forfeit score | 1-0, `[placeholder]` |
| 6 | Hammer | the first-end hammer box (LSFE) is required in a finished file; every later hammer is worked out from the scores (a blank end keeps it). A league whose cards never note it must start doing so. Without it there would be no stolen ends |
| 7 | Concessions and time | a rink may shake hands after any complete end, while behind; the score stands and the ends left show X; it is a normal win and loss. A game may also stop when time is called (`time_called`), with the same X marks and a tie if level. No minimum number of ends |
| 8 | Lineups and positions | recorded per game (`rules.lineups: recorded`; `none` for a league whose cards have no names), 3 or 4 players in throwing order, positions lead, second, vice, skip. With `none` there are no games played, no lineups block, and the Stats page's player list stays on its empty-state line |
| 9 | Player stats | games played and position only, no player leaderboards |
| 10 | Team stats and boards | ends won, stolen, blank, big (3+), ends with hammer and scored with hammer, per game and per season; boards Stolen ends and Ends won (tiles) and Big ends (list), as counts with "in 5 games". "Scored with hammer" counts any score, not the analysts' 2+ "hammer efficiency". The mockup's "Ends won 50%" needs team rates (a core change), later if wanted. "Games" there means games with a score sheet: a forfeit is not a game on those boards |
| 11 | How the line score shows things | as the approved design: a stolen end tinted and framed with the hidden words "stolen end"; a blank end's column shaded; X for an end not played; the hammer marker in each end and after the rink with the hammer in end 1 (cards); extra ends as `EE` columns. The club-scoreboard style waits for a specimen |
| 12 | Schedule words | "Draw 7" for a league night; sheets as letters in `schedule.csv` (`A`), shown as "Sheet A"; a blank sheet column shows no tile. (Strictly a draw is one start time: an evening with a 6:30 and an 8:45 draw is one "Draw 7" here.) |
| 13 | Rink names | `sports/curling/README.md` and `docs/data.md` say to use a made-up name or "Gail R.'s rink", never a surname; the build does not try to detect surnames |

Left for later (named in the spec, not built): the club-scoreboard line score, team rates ("ends won %"), a
different number of ends for playoffs, a printable curling score card and the photo-reading prompt, and the entry
page and JavaScript copy of the rules (stage 7).
