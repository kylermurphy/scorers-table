# Stage 5, part 4: slo-pitch

Status: **draft for the owner's review**. Nothing is built yet. Section 10 lists the decisions: until one is
answered, the build follows the recommendation, and every rule a league decides shows as `[placeholder]`.
Slo-pitch is the last sport of stage 5. The references are `BRIEF.md` ("Slo-pitch (rec / masters, often co-ed)"), the
approved slo-pitch mockups (Slopitch-Home, Slopitch-Game, Scoreboard-Slopitch-Home) and the slo-pitch specimens on the
design-system page (`scripts/design_system/sample.py`, Maple Park Slo-Pitch: the R/H line score, the facts list and the
batting tables).

Read first: `BRIEF.md`, `PLAN.md` ("Still to come, with the sport that needs it"), `docs/stage-4-spec.md` section 3
(the sport interface), `docs/stage-5-hockey-spec.md` (the model for this document), `docs/sports.md` (what the code
does today), `docs/design.md` (the Slo-pitch look: scorebook line score, facts, batting tables).

Slo-pitch words used here: a game has seven **innings**; each inning has a **top half** (the visitors bat) and a
**bottom half** (the home team bats). A team's runs in a half-inning are capped by the **run limit** (often 5); an
inning with no cap is an **open inning** (usually the last one). The **mercy rule** (run rule) ends a game early when
one team leads by a set number of runs after a set number of innings. A game stopped early (mercy, time, weather,
darkness) is a **called game**. A tie after seven may go to **extra innings**. A **walk-off** is when the home team
takes the lead in its last half-inning: the game ends there. The scorebook's **R/H/E** boxes are runs, hits and errors
(errors are charged to the fielding team). A **batting line** is a player's AB (at-bats), R (runs), H (hits), RBI (runs
batted in), HR (home runs) and BB (walks); PA (plate appearances) is AB + BB here. AVG (batting average) = H / AB,
written `.333`; OBP (on-base percentage) = (H + BB) / (AB + BB).

---

## 1. Scope

**In this pull request**

| What | Where |
|---|---|
| The slo-pitch sport folder | `sports/slopitch/`: `sport.yml`, `rules.py` (`check`, `read`, `present`, `derive`), `sample.py`, `README.md` (the score sheet box by box, for the volunteer) |
| Shared test files | `sports/slopitch/fixtures/`: one game per case with the expected problems and numbers (section 8), for the stage 7 JavaScript port |
| One new display part | `facts` (the "Home runs / 3+ hits / Limit innings" list), plus `stat_table` `heading: plain` for the batting tables (section 6, E21-E22) |
| Core extensions | R/H/E columns in the line score, stats and boards shown only when an option is on, a per-team-game minimum, the result card's status line, visitors listed first, a legend key from an option (section 6, E20-E27) |
| Sample seasons | two made-up slo-pitch seasons for the golden files, the `/slopitch/` sport preview and its landing card (section 7) |
| Docs | `docs/sports.md`, `docs/open-questions.md` (section 9: slo-pitch's placeholders and section 10 here), `docs/data.md`, `README.md` (`/slopitch/`), `CLAUDE.md`, `PLAN.md` status, `landing.yml` (`coming_soon: []`) |

**Not in this pull request**

- The JavaScript copy of the rules and the entry page: stage 7. The fixtures are written now so the port can be
  tested against them.
- A printable slo-pitch score sheet and the photo-reading prompt: later (`PLAN.md`).
- Period words chosen by an option ("Half") and team rates ("ends won %", team AVG): slo-pitch does not need them
  (innings are always "Inning", and no approved page shows a team rate). They stay on the "Later" list (decision 20).
- Pitching stats, fielding positions, 2B/3B, sacrifice flies, strikeouts, spray charts: not on a typical rec sheet, or
  not wanted (decision 13).
- Co-ed batting-order rules and any gender field (decision 17).
- Six layouts per sport and the screenshot sweep: stage 6. This PR screenshots the slo-pitch sample in the Slo-pitch
  layout only. The shipped `league.yml` stays `sport: basketball`; the committed `data/sample-*` stay basketball.

## 2. The game file

### 2.1 What a rec score sheet holds, and how it maps

A rec slo-pitch scorebook page (one per team, or both teams on one sheet) has: the date, diamond and teams, with
"Visitors" and "Home" marked; a batting order (one row per batter, often 10 to 12 in rec, with substitutes written
under the starter); per batter, boxes per inning with the result of each trip to the plate, and on the right the
batting line totals (AB, R, H, RBI, often HR and BB); per team the runs in each inning (a circled 5 when the run limit
ended it, an X when a bottom half was not needed); the R, H and E boxes; signatures. The game file copies the parts a
page needs, box for box, in the core envelope (`docs/data.md`), with the sport's part under `sheet:`. The per-inning
plate-appearance boxes are **not** copied (no page needs them; the batting line totals are what the sheet sums them to).

| On the sheet | In the file | Notes |
|---|---|---|
| date, time, park, diamond | the schedule row (`schedule.csv`: `date`, `time`, `venue`, `surface` = `1`) | the core's, as for every sport |
| visitors and home | the envelope's `away` and `home` | **home is the team that bats last** (the scorebook's "Home" line); pages list the visitors first, "Mudcats at Sluggers" (decision 1, E26) |
| who batted first | `sheet.bats_first`, left out when the visitors did | only after a coin toss (decision 2) |
| scorekeeper, notes | the envelope (`scorekeeper`, `checked_by`, `notes`) | umpires' names are not copied |
| a forfeit | the envelope's `forfeit: <team id>`, no `sheet` | the core's |
| runs by inning | `sheet.runs.<side>`: one box per inning played, a whole number or `X` | as written; the line score, the run limit and the mercy rule all come from these |
| R, H, E boxes | `sheet.totals.<side>`: `{r, h, e}` | `h` only when the league keeps team hits, `e` only when it keeps errors (decision 15) |
| why the game stopped early | `sheet.called`: `mercy`, `time`, `weather`, `darkness` or `other` | only for a game shorter than regulation (decision 6) |
| batting order and lines | `sheet.batting.<side>`: one row per batter, top to bottom: `{player, ab, r, h, rbi, hr, bb}` | the line only when the league keeps batting lines (decision 12); the order gives games played |

### 2.2 Example

The approved Slopitch-Game mockup as a file (Mudcats 11 at Sluggers 14, Week 6, Diamond 1). The order of `batting`
rows is the batting order; the core puts numbers in front of them on the game page.

```yaml
game_id: 2027-06-16-1          # the core envelope: unchanged for every sport
status: final
home: sluggers                 # bats last
away: mudcats
scorekeeper: Bev S.
checked_by: Ted F.
sheet:
  runs:                        # one box per inning played; inning 1 is the first box
    away: [2, 0, 5, 1, 0, 3, 0]
    home: [1, 5, 0, 3, 5, 0, X]   # X: Sluggers led 14-11 after the top of the 7th, so they did not bat
  totals:                      # the R H E boxes as written (no e: this league does not keep errors)
    away: {r: 11, h: 15}
    home: {r: 14, h: 18}
  batting:                     # top to bottom; a line per batter because this league keeps batting lines
    away:
      - {player: norm-w,    ab: 4, r: 2, h: 3, rbi: 0, hr: 0, bb: 0}
      - {player: sheila-r,  ab: 4, r: 1, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: phil-g,    ab: 4, r: 2, h: 2, rbi: 3, hr: 1, bb: 0}
      - {player: doug-e,    ab: 4, r: 1, h: 2, rbi: 2, hr: 0, bb: 0}
      - {player: pat-o,     ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: ken-j,     ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: marg-l,    ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
      - {player: brian-c,   ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: elaine-v,  ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: stan-z,    ab: 3, r: 0, h: 1, rbi: 0, hr: 0, bb: 0}
    home:
      - {player: gary-t,    ab: 4, r: 2, h: 3, rbi: 0, hr: 0, bb: 0}
      - {player: linda-m,   ab: 4, r: 2, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: ron-b,     ab: 4, r: 2, h: 3, rbi: 3, hr: 1, bb: 0}
      - {player: dave-k,    ab: 3, r: 2, h: 2, rbi: 4, hr: 1, bb: 0}
      - {player: bev-s,     ab: 3, r: 1, h: 2, rbi: 2, hr: 0, bb: 0}
      - {player: wayne-h,   ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: carol-d,   ab: 3, r: 1, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: ted-f,     ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
      - {player: joan-p,    ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: murray-l,  ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
```

The other cases (only the changed boxes shown):

```yaml
  runs:                        # a mercy-rule game: 22-4 after five, so the game was called
    away: [3, 5, 5, 4, 5]
    home: [0, 1, 0, 2, 1]
  called: mercy                # mercy, time, weather, darkness or other: why the game is shorter than 7 innings
---
  runs:                        # a playoff game: 9-9 after seven, a scoreless 8th, a walk-off in the 9th
    away: [1, 0, 2, 0, 3, 1, 2, 0, 2]
    home: [0, 3, 1, 2, 0, 2, 1, 0, 3]
---
  bats_first: home             # a coin toss sent the home team up first: the X rule now applies to the visitors
---
  batting:                     # a league that keeps the batting order only (rules.batting: order)
    home:
      - {player: gary-t}
      - {player: linda-m}
      - {name: Jo K.}          # drafts only: a spare written in by hand, no player id yet
```

In a draft (`drafts/`) any box may be left empty (`~`), as for every sport.

### 2.3 Why this shape

- **Runs by inning are the record; R must agree.** The sheet writes both, and two records that must agree catch a
  missed box, as hockey's period boxes and basketball's quarters do. A short list means the game was shorter.
- **`X` is written, not worked out**, because the sheet has it and it says something different from 0 (the half was
  not played). The check makes sure it is only where the rules allow it.
- **Batting lines are totals, not plate-appearance boxes.** Every page reads totals; copying fifty little boxes per
  team would triple the volunteer's work. A stage 7 photo prompt can still read the totals column.
- **The order of the rows is the batting order**, so there is no `order:` number to keep in step. A substitute is a
  row of their own right under the player they replaced (README how-to).
- **Hits come from one place.** With batting lines, the team's H is the sum of the H column and the H box must match;
  without them, the H box is the only source.

### 2.4 Paths

Paths are relative to `sheet` in `check` (the core adds `sheet.`), counting from 0 as every sport does: `runs.home.6`
is the **7th** inning's box. The README says so with a picture of the boxes.

| Path (after the core adds `sheet.`) | The box |
|---|---|
| `sheet.runs.away.2` | the visitors' runs in the 3rd inning |
| `sheet.totals.home.r`, `.h`, `.e` | the home team's R, H, E boxes (`r` is `Score.final_at`) |
| `sheet.called`, `sheet.bats_first` | the two single marks |
| `sheet.batting.away.4` (`.player`, `.name`, `.ab`, `.r`, `.h`, `.rbi`, `.hr`, `.bb`) | the 5th batter of the visitors |

## 3. The rules in Python

### 3.1 Checks

"Gap" means an error in `games/` and a warning in `drafts/` (the core rule for empty boxes). `check` never raises,
returns every problem, and stops a branch when a problem makes later checks meaningless (a bad `runs` list: no run
limit, mercy or R checks). "The final inning" is the last inning in `runs`. Numbers are the options' defaults (5.3).
The **batting side of a half** follows `bats_first`: normally the visitors bat in the top half, the home team in the
bottom half.

| Check (path relative to `sheet`) | Level |
|---|---|
| a key other than `runs totals called bats_first batting` (`<key>`) | error |
| `bats_first` not `home` or `away` | error |
| `runs`, `runs.<side>` missing | gap |
| `runs.<side>` not a list of 1 to `innings` + 10 boxes | error |
| the two lists of different lengths ("both teams have a box for every inning played; write X for a bottom half not needed") | error |
| `runs.<side>.<i>` empty (`~`) | gap |
| `runs.<side>.<i>` not a whole number from 0 to 99 or `X` | error |
| `X` in the team batting first, or in any box but the final inning's | error |
| `X` although the team batting last did not lead after the top half ("Sluggers trailed 9-11 after the top of the 7th, so they batted: write their runs") | error |
| a number in the last-batting team's final box although it led after the top half, in an inning that ends the game ("not needed: write X") | warning |
| more runs than `run_limit` in a limited inning ("the limit is 5 a half-inning: check the box"); with `limit_play: finish`, more than `run_limit` + 3 (a grand slam on the limit play) | error |
| fewer innings than `innings` and no `called` ("a 5-inning game: if it was called, add `called: mercy`, `time`, `weather`, `darkness` or `other`") | error at `called` |
| `called` not one of the five words; `called` on a game of `innings` innings or more | error |
| `called: mercy` when `mercy_runs` is 0 (no mercy rule) | error |
| `called: mercy` and the lead at the end is less than `mercy_runs`, or fewer than `mercy_after` innings were played (the team batting last may stop after the top half when it leads: "4½") | warning |
| a called game shorter than `official_innings` ("fewer than 4 innings: does it count? A game that is replayed stays out of `games/`") | warning |
| more innings than `innings` although the score was not level after regulation | error at `runs.<side>.<innings>` |
| extra innings in a regular-season game beyond `extra_innings` (0: none, the tie stands) | error |
| an extra inning played after a team led at the end of a complete extra inning (the game was over) | error |
| a walk-off half with more runs than needed + 3 ("the game ends when the winning run scores; only a home run brings in more") | warning |
| `totals`, `totals.<side>`, `.r` missing | gap |
| `totals.<side>` not a row; a key other than `r h e` | error |
| `.r` not the sum of the side's runs ("R says 12, the innings add up to 11") | error |
| `.h` missing when `team_hits` is `kept` and the side has no batting lines | gap |
| `.h` set when `team_hits` is `none` and the side has no batting lines | error |
| `.h` not the sum of the batting lines' H | error |
| `.e` missing when `team_errors` is `kept`; set when it is `none` | gap / error |
| `.h`, `.e` not a whole number from 0 to 99 | error |
| `batting`, `batting.<side>` missing when `batting` is not `none` | gap |
| `batting` set when `batting` is `none` ("this league keeps team results only") | error |
| `batting.<side>` not a list of 1 to 30 rows; a row not a row; an unknown key | error |
| `.player` missing (only a `name`: a spare not yet in `players.yml`) | gap |
| `.player` not in `players.yml`; listed twice in the game | error |
| `.player` on another team and not `sub: true` | warning |
| a line key (`ab r h rbi hr bb`) when `batting` is `order` | error |
| a row with no line when `batting` is `every_game` | gap |
| with `optional`: some rows of a side with a line and some without ("all of a team's batters have a line, or none") | error |
| with `optional`: one side with lines and the other without ("only Mudcats' lines: is a page missing?") | warning |
| a line value not a whole number from 0 to 20 | error |
| `.h` more than `.ab`; `.hr` more than `.h` | error |
| PA (`ab` + `bb`) more than the innings the side batted + 2 ("check the line") | warning |
| the side's R column not equal to its runs ("the batters' R add up to 10, the team scored 11") | error |
| the side's RBI more than its runs | warning |
| a side's HR more than `hr_limit` (when set) | warning |

The core then adds, at `Score.final_at` (`sheet.totals.<side>.r`): a tied playoff game, and a tied regular-season
game when `standings.ties` is false.

### 3.2 How the numbers come from the sheet (`read`)

| Number | From |
|---|---|
| `Score.periods` | the regulation innings, always `innings` long: a played half's runs, `None` for an `X` or an inning a called game never reached |
| `Score.extra` | the runs of each extra inning, `[]` when none |
| `Score.final` | the sum of the runs (R must agree, 3.1); `final_at` is `sheet.totals.<side>.r` |
| `decided_in` | `overtime` when extra innings were played (the pages say "Extras", decision 8), else `regulation` |
| player line (group `player`) | every `batting` row with a player id: GP 1, and with a batting line `ab r h rbi hr bb`; with `batting: order`, `counts={}` (games played only, as curling's empty group) |
| `facts` | the runs by inning with each half's limit and open flags, who batted first, the `X`, `called`, the walk-off flag, R/H/E, the batting rows in order, per side HR and 3+-hit players |

`derive(counts, group)`: `pa` = AB + BB (a whole number), `avg` = H / AB and `obp` = (H + BB) / (AB + BB), both
unrounded, `None` with no at-bats or no plate appearances.

### 3.3 Run limit, open innings, mercy, time, ties, forfeits

- **Run limit** (`run_limit`, default 5, 0 = none; decision 4): a half-inning in a limited inning ends when the
  batting team reaches the limit. With `limit_play: stop` (default) the box can be at most the limit; with `finish`
  every run on the play that reached it counts (up to the limit + 3). A box equal to the limit in a limited inning
  is marked (circled on the game page, underlined on the card): the sheet does not say whether the third out came
  first, so the README says the mark means "reached the limit".
- **Open innings** (`open_innings`): `last` (default: the last regulation inning and every extra inning have no
  limit, the mockup's "7 open") or `none` (every inning is limited).
- **Mercy rule** (`mercy_runs`, default 15, 0 = none; `mercy_after`, default 5 innings; decision 5): only checked
  when the sheet says `called: mercy`, and only as a warning (leagues word it differently).
- **Time limit, weather, darkness** (decision 6): the score stands as the boxes show it; the volunteer writes only
  the innings that were completed (or the top half and an `X`, when the home team led). `time_limit` (minutes, a
  `[placeholder]`) is shown in the game's facts ("Called: time limit, 60 minutes"); the sheet records no clock, so
  nothing checks it.
- **Ties and extra innings** (decision 7): a regular-season game level after `innings` is a tie unless the league
  allows `extra_innings` (0 by default). A playoff game plays extra innings until a team leads after a complete
  inning or walks off; a level playoff game is the core's error. Extra innings are open under `open_innings: last`.
- **A forfeit** is the core's (`forfeit: <team id>`, no sheet): no player gets a game. Its score is
  `standings.forfeit` (decision 11, 7-0).

## 4. Standings

### 4.1 Defaults (`sport.yml`)

```yaml
standings:
  rank_by: points
  points: {win: 2, tie: 1, loss: 0}                      # BRIEF: 2 for a win, 1 for a tie; extra innings count the same
  period_points: 0
  ties: {value: true, decide: true}                      # decision 7
  forfeit: {value: {score: [7, 0]}, decide: true}        # decision 11 (BRIEF's example)
  tiebreakers: {value: [head_to_head, {diff: {cap: 7}}], decide: true}   # decision 10: BRIEF's "often capped"
  columns: [gp, w, l, t, pts, pf, pa]                    # the approved Slopitch-Home table: GP W L T PTS RF RA
```

`words.points_for` is `{label: RF, title: Runs for}`, `points_against` `{label: RA, title: Runs against}`. The README
gives the lines for the common variants: win percentage for leagues with rain-outs and unequal schedules (`rank_by:
win_pct`, columns `[gp, w, l, t, pct, pf, pa]`), no cap (`diff`), and a DIFF column.

## 5. Stats and pages

### 5.1 One stat group, shown only when the league keeps batting lines

`BRIEF.md`: "team results only, or a basic batting line (AB, R, H, RBI, HR, BB, AVG)". So one group, `player`
(labelled "Batting"), whose counting stats, rates and boards carry `when: {batting: [optional, every_game]}` (E23).
With `batting: order` the Stats page lists every player with GP only; with `batting: none` there is no player table,
no Leaders section and no player board (the team pages, standings and results are unchanged).

| Counting | Rates (`derived`) | Stats table | Player totals | Game log |
|---|---|---|---|---|
| `ab` AB, `r` R, `h` H, `rbi` RBI, `hr` HR, `bb` BB | `pa` PA (0 places), `avg` AVG (3 places, `format: dot`: ".333"), `obp` OBP (3 places, `dot`) | GP AB H AVG HR RBI R BB | GP PA AB R H HR RBI BB AVG OBP | AB R H RBI HR BB |

The key column is AVG (the first board's stat). Team stats: none (`stats.team: []`; R/H/E per game are in the line
score, and no approved page shows a team season total).

### 5.2 Leaderboards

| Board | Stat | Tile | Home | Detail | Notes |
|---|---|---|---|---|---|
| Batting avg | `avg` | yes, hot | yes | "{h} for {ab}" | `zero: true`; min `avg_min_pa` per team game (E24); the Home list under it is "next best", as the mockup |
| Home runs | `hr` | yes, accent | yes | "{gp} games" | the mockup's "6 games" |
| RBI | `rbi` | no | no | "{gp} GP" | |
| Hits | `h` | no | no | "{ab} AB" | |
| Runs | `r` | no | no | "{gp} GP" | |
| On-base % | `obp` | no | no | "{pa} PA" | `zero: true`, min `avg_min_pa` per team game |

`minimums.avg_min_pa`: default 2, `decide: true`, `per_team_game: true`, note "Minimum {value} plate appearances per
team game to rank." (decision 14). Every board carries `when: {batting: [optional, every_game]}`.

### 5.3 Options (`sport.yml`)

| Option | Type, default | Decide | Used for |
|---|---|---|---|
| `innings` | int 3 to 9, 7 | yes | regulation length, `line_score.periods` (a forfeit's `per_period`) |
| `run_limit` | int 0 to 20, 5 (0 = none) | yes | the limit check and the circled boxes |
| `open_innings` | choice `last none`, `last` | yes | which innings have no limit |
| `limit_play` | choice `stop finish`, `stop` | yes | runs on the play that reaches the limit |
| `mercy_runs` | int 0 to 30, 15 (0 = none) | yes | the mercy warning, the facts text |
| `mercy_after` | int 1 to 9, 5 | yes | the mercy warning |
| `official_innings` | int 1 to 9, 4 | yes | the called-game warning |
| `time_limit` | int 0 to 180 minutes, 60 (0 = none) | yes | the facts text of a game called on time |
| `extra_innings` | int 0 to 5, 0 | yes | extra innings allowed in the regular season (playoffs: until decided) |
| `hr_limit` | int 0 to 10, 0 (0 = none) | yes (`BRIEF.md`'s `[placeholder]`) | home runs a team may hit in a game: the warning |
| `batting` | choice `none order optional every_game`, `optional` | no | what the sheet keeps per batter (5.1) |
| `team_hits` | choice `kept none`, `kept` | no | the H box and column |
| `team_errors` | choice `none kept`, `none` | no | the E box and column |

Other `sport.yml` values: words period `{one: Inning, many: Innings, short: Inn}`, day `Week`, surface `Diamond`,
`extra: {one: Extra inning, short: Extras}` (decision 8); `line_score: {shape: innings, total_label: R, corner: Inning,
periods: innings}`; labels `results: Latest results`, `next: Next game day`, `leaders: Leaders`, Scoreboard `leaders:
Hitting`, `next: Next up`; `display: {card: lines, card_foot: note, surface: label, card_head: status_surface, matchup:
at, results_legend: [{kind: limit, mark_option: run_limit, text: "Inning ended at the run limit."}, {kind: x, text:
"Not needed."}]}` (E25-E27; the design-system contract's slo-pitch hints); no `positions`; `games_per_day: 2`
(doubleheaders, decision 18); `game_minutes: 75`; `default_layout: slopitch`; `blurb: Innings, run limits and an
optional batting line.` (the coming-soon card's line, kept).

### 5.4 The game page (`present`)

| Block | Part | Content | Exists? |
|---|---|---|---|
| final panel | core `final-panel` | the scorebook card: visitors on top, home below (E26), the 46 px slab score, WIN badge; status "Final" or "Final · Extras"; sub "Sluggers by 3" | yes (the slo-pitch skin is CSS); the order is E26 |
| line score | core `line_score`, shape `innings`, title "Line score" | corner "Inning", columns `1`...`7` with `open` on open innings, `8`, `9` for extra innings; R (`total`), then H and E when kept (E20); `mark` on a box at the limit in a limited inning ("run limit"), `void` (X) for a half not needed ("not needed") or, in a called game, for the innings not reached ("not played"); rows in batting order (`first`, E26); a stacked legend: "5 Circled: the inning ended at the 5-run limit. The 7th is open (no limit)." and "X Sluggers led after the top of the 7th, so they didn't bat." (or "Called after 5 innings: mercy rule.") | shape, flags and legend yes; extra columns and row order no |
| result card | core `card` (`lines`) with its own compact `line_score` (no open headers, H and E as the full one) | eyebrow "Final · Diamond 1" (`card_head`, E25); note "Top bat: **Gary T.** 3 for 4" (most hits, then fewest AB, then RBI; none without batting lines); link "Box score" | card and eyebrow include yes; the eyebrow from `sport.yml` is E25 |
| facts | **new** `facts` (E21) | rows "Home runs" (players per team: "Ron B., Dave K. (Sluggers); Phil G. (Mudcats)", a count after a name with two: "Ron B. 2"), "3+ hits", "Limit innings" ("Sluggers 2 (2nd, 5th); Mudcats 1 (3rd)"), and for a called game "Called" ("After 5 innings: mercy rule, 15 runs"); a row with nothing is left out; the winner's team first | specimen and CSS yes; include, block type and parity no |
| batting | `stat_table` per side, `number_col` (the batting order), `heading: plain` (E22) | "Mudcats batting" with the chip, # and Batter fixed, AB R H RBI HR BB, a Totals row; footnote "# = batting order from the score sheet." With `batting: order`, a `roster` block "Batting order" instead (role = the order number, a spare badged); with `none`, nothing | stat table yes; plain heading and the slo-pitch parity case no |

The data comes only from the `Reading` (`facts`, `lines`) and `ctx.players`, as for every sport. No tiles.

### 5.5 The other pages

| Page | Slo-pitch shows | Exists? |
|---|---|---|
| Home | next game day (green panel, diamond rows), latest results as ruled line-score cards with the legend, standings GP W L T PTS RF RA, Leaders: the AVG and HR tiles and the AVG "next best" list | the legend key is E27, the eyebrow E25; the rest is core |
| Schedule | "Week 6", diamonds, cancelled and moved games, doubleheaders, playoffs apart; "Mudcats at Sluggers" | E26 |
| Stats | every board; one "Batting" table | E23 hides it when batting lines are not kept |
| Team | team card, roster with batting totals, results, upcoming, calendar | yes |
| Player | Season totals, Ranks, game log | yes |
| Archive season | as every sport; a season under different options shows its own columns | E23 reads the season's options |
| Landing card | "Slo-pitch", the blurb, Maple Park Slo-Pitch, top three GP W L T PTS, the latest result as a lines card | by itself (section 7) |

## 6. Core extensions

Checked against the code (`scripts/core/{sports,compute,compute_games,compute_stats}.py`, `_includes/parts/`,
`tests/parity/cases.py`). Numbered after hockey's E12-E19. Each is generic (none tests a sport id). **Every existing
sport's pages must stay byte-identical**: the stub, basketball, curling and hockey golden files may change only by new
JSON keys (read by eye), and `tests/golden/landing/off-site.sha256` only for the new `/slopitch/` pages and the other
demos' banners.

| # | Extension | Needed because | Files | Tests |
|---|---|---|---|---|
| E20 | **More total columns in the line score.** `line_score.extras: [{label, title}]` and each row's `extras: [values]`, printed after the total in order as `th.st-line-score__extra` with `<abbr title>` (same class and colours as today's H: no new CSS or contrast pair). The single `extra_label`/`extra` stays and prints as today; the core fills `extras: []` | R/H/E (`PLAN.md`); today one extra column only | `compute_games.py` (`_line_score` defaults), `_includes/parts/line-score.html`, `scripts/design_system/contract.py` and `specimens_scores.py` (the slo-pitch H header gets its `abbr`; a second slo-pitch specimen with E) | parity: `line-score` unchanged for the other sports, new fragment case `line-score-rhe`; `test_build.py` (defaults) |
| E21 | **`facts` block**: `{type: facts, title, rows: [{label, items: [{side, players: [{player, extra}], text}]}]}`. An item with players prints "Ron B., Dave K. 2 (Sluggers)", one with `text` prints "Sluggers 2 (2nd, 5th)"; `side: null` prints the text alone. Names are plain text (as the events block); `dl.st-facts` as the specimen | the game's facts list | `model.py` (`BLOCK_TYPES`), new `_includes/parts/facts.html`, `parts/blocks.html`, `contract.py` (`_slopitch_blocks`), `docs/design.md` | part of the new fragment case `game-tables-slopitch`; `check_contrast.py` passes, `docs/contrast.md` unchanged |
| E22 | **`stat_table` `heading: plain`**: the large `h2` team heading with the chip and the `title`, no score | "Mudcats batting" has no score (the specimen's `team_heading` without one) | `_includes/parts/stat-table.html`, `contract.py`; the specimen's totals cell `colspan="2"` becomes the include's two cells (a specimen change, so basketball stays byte-identical) | `game-tables-slopitch` (facts, two batting tables, footnote); **remove `game-tables` from `SKIPPED`** (every slo-pitch game-tables specimen is then covered by a fragment case) |
| E23 | **Stats shown only when an option is on.** `when: {<option>: [values]}` on a counting stat, a derived stat and a leaderboard: when the season's options do not match, the stat is left out of every list (columns, totals, logs, `detail` fields) and the board is not built. A group nobody has a line in is left off the Stats page, the team roster and the player page, and the Home page drops its Leaders section when no board is left | batting lines are optional by league; `PLAN.md` also names curling's `lineups: none` | `sports.py` (schema: the option exists, values are allowed ones), `compute_stats.py`, `index.html`, `stats/index.html`, `_layouts/{team,player,archive-season}.html` | `test_sports.py`; new `tests/test_option_stats.py` (a test sport in `tests/fixtures/sports/` built under each value: columns, boards and the Home section present or gone; a season override changes one season only) |
| E24 | **Leaderboard minimum per team game**: `min: {stat, setting, per_team_game: true}` makes the needed value `setting` x the team's regular-season games so far (not combined with `cap_at_team_games`) | a fixed AVG minimum leaves the board empty for weeks (decision 14) | `sports.py`, `compute_stats.py` (`_needed`) | `test_build.py`: early and late season, a player on a team with fewer games |
| E25 | **`display.card_head` from `sport.yml`**: `status_surface` puts the "Final · Diamond 1" eyebrow on a `lines` card. The include has it; `compute.py` forces `""` today | the slo-pitch card | `sports.py` (allowed key, values `"" status_surface`), `compute.py` (pass it through) | `test_sports.py`; Jekyll smoke |
| E26 | **Visitors first.** `display.matchup: vs` (default, today) or `at`. With `at` every place that lists a game's two teams puts the away team first and joins them with "at": the game title, final panel, result card rows, line score rows, game rows, next-game panel, ticker, calendar summary. The core writes `league.sides_order` (`[home, away]` or `[away, home]`) and the includes loop over it instead of the literal `"home,away"`. A line score may also say `first: home` for one game (a coin toss, `bats_first`), which orders its rows (full and card) only | softball line scores list the visitors on top, and the X sits on the bottom row | `sports.py`, `compute.py` (`league.json`), `calendars.py`, `_includes/parts/{final-panel,result-card,result-hero,line-score,game-row,next-game}.html`, `_includes/shell/ticker.html`, `_layouts/game.html`, `contract.py` (slo-pitch's sample sides become home = Sluggers with `matchup: at`) | `vs` output byte-identical (golden, off-site hash); new `tests/test_matchup.py` (titles, row order, calendar text, a coin-toss line score); parity: the slo-pitch combos of `result-card`, `final-panel`, `line-score`, `result-card-hero`, `game-row`, `next-game` pass through the new path |
| E27 | **A legend key from an option**: a `results_legend` item may carry `mark` (fixed text) or `mark_option` (an int option: the key shows the league's value, "5") | the circled-5 key must follow `run_limit` | `sports.py` (`_check_results_legend`), `compute.py` | `test_sports.py`; Jekyll smoke (Home shows "5") |

**Considered and not built** (no approved page needs them, and an option no sample uses goes untested):

| Idea | Why not now |
|---|---|
| Period words by option ("Half") | not a slo-pitch need; stays on "Later" for basketball halves and two-period hockey (decision 20) |
| Team rates (team AVG, curling's ends won %) | no approved page shows one (decision 20) |
| "Final/8" with the inning number | needs a status template in the core; "Final · Extras" uses `words.extra` as it is (decision 8) |
| A team-choice open inning ("one open inning per team, written on the sheet") | rare; a league asking for it gets an `open_innings` value later (decision 4) |

## 7. Sample data

`sports/slopitch/sample.py`:

- `LEAGUE_NAME = "Maple Park Slo-Pitch"` (the made-up league of `BRIEF.md` and the design system).
- `TEAMS`: Sluggers SLG, Mudcats MUD, Dugout Dogs DDG, Line Drives LND, Long Balls LGB, Bunters BUN (the design
  system's six).
- `PLAYERS_PER_TEAM = 12` (rec teams bat 10 to 12), `NUMBERS = False` (the game page's # is the batting order; names
  as "Gary T."), `SURFACES = ["1", "2", "3"]`, `TIMES = ["18:30", "18:30", "19:45"]` (the mockup's next game day).
  No `POSITIONS`.
- `sheet(rng, game, ctx)`: draw runs per half-inning (mostly 0 to 3, sometimes the limit; the open 7th 0 to 8),
  honouring the outcome and every option: the run limit and `limit_play`, `X` when the home team leads after the top
  of the final inning, a walk-off that stops at the winning run (or a home run), extra innings when the outcome is
  `ot` and the rules allow them (else a tie; a playoff game always plays them). Over a season: at least one
  mercy-rule game (`called: mercy`, a lead of `mercy_runs` after `mercy_after`), one walk-off, one extra-inning
  playoff game, several limit innings, one game with no batting lines (`batting: optional`). Batting lines that add
  up: the R column equals the runs, the H column the H box, RBI at most the runs, HR within `hr_limit`, PA believable
  for the innings. One draft has a `name:` row. `tests/test_slopitch_sport.py` asserts each.
- **Options in the sample.** Both seasons build with the defaults (`/slopitch/` shows ties, H, no E). The contract
  test already runs the sample for every value of every `choice` option (`batting` x4, `team_errors kept` gives E,
  `open_innings none`, `limit_play finish`); `test_slopitch_sport.py` also builds a season with `extra_innings: 2`
  and `run_limit: 0`, golden-free.

`scripts/make_sample.py` does the rest unchanged (round robin, a cancelled and a moved game, a forfeit, a tie, playoff
rows, one draft). Package 5 checks that `games_per_day: 2` leaves its round robin as it is (one game a night); if it
does not, `games_per_day` stays 1 and decision 18 says so.

Golden files: `tests/golden/slopitch/` (`SPORTS` in `test_golden.py` gains `slopitch`), checked by hand once:
standings, the AVG board with its minimum, the mercy game, the extra-inning game. The `/slopitch/` sport preview and
its **landing card** come by themselves (a `sample.py` and a `blurb`). In the same PR, `landing.yml` becomes
`coming_soon: []` (the key is required; an empty list draws no coming-soon card), `tests/test_landing.py` expects an
empty list and no warning, and `tests/golden/landing/landing.json` and `off-site.sha256` are rewritten (read which
pages their diffs name). The design-system page keeps its coming-soon card specimen (it shows a state, not a promise).

## 8. Tests

| Test | What |
|---|---|
| `sports/slopitch/fixtures/` + `tests/test_slopitch_fixtures.py` | the **shared fixtures**, in hockey's format: `context.yml` (two made-up teams, Alpha and Bravo, ten batters each, a spare with `sub: true`, a player of a third team, default options) and per case `<name>.yml` (`fixture: {folder, game_type, options}` + `sheet:`) with `<name>.expected.json` (`problems` in order; `reading`: score, lines, facts, or `null`). `UPDATE_FIXTURES=1` rewrites them for review. Stage 7's Node runner reads the same files |
| fixture cases (about 70, one or more per row of 3.1) | `clean` (the mockup game), `tie`, `walk-off`, `walk-off-too-many`, `x-not-leading`, `x-in-away`, `x-not-last`, `number-where-x`, `limit-inning`, `over-limit`, `over-limit-finish` (ok and too many), `open-seventh`, `open-none`, `run-limit-0`, `called-mercy`, `called-mercy-short-lead`, `called-mercy-no-rule`, `called-time`, `called-under-official`, `short-not-called`, `called-full-game`, `extra-innings-playoff`, `extra-innings-regular-0`, `extra-innings-regular-2`, `extra-after-decided`, `extra-not-tied`, `bats-first-home` (X on the visitors), `lists-differ`, `r-wrong`, `h-missing`, `h-when-none`, `h-not-lines`, `e-kept`, `e-when-none`, `batting-none`, `batting-none-but-rows`, `batting-order` (GP only), `order-with-line`, `every-game-missing-line`, `optional-mixed-rows`, `optional-one-side` (warning), `h-over-ab`, `hr-over-h`, `pa-too-many`, `r-column-wrong`, `rbi-over-runs`, `hr-limit`, `spare-other-team`, `draft-with-name`, `name-in-final`, `dup-player`, `unknown-keys`, `not-a-block`, `draft-empty-boxes` |
| `tests/test_slopitch_sport.py` | `read` and `present` against the design-system game (`_check_slopitch_game`'s numbers: runs by inning, limit and X marks, R/H, facts, batting totals); `derive` (`None` with no AB); the line score's open, extra-inning, H and E columns and row order; `sample.sheet` honours every outcome under every option value; the season-level asserts of section 7 |
| `tests/test_sport_contract.py` | picks up the folder by itself (sample checks for every choice option, mutated sheets, paths, drafts never stricter) |
| `tests/test_golden.py` | `tests/golden/slopitch/` beside `stub/`, `basketball/`, `curling/`, `hockey/` |
| `tests/test_parity.py` | E20-E22 and E26: `line-score-rhe`, `game-tables-slopitch`, `game-tables` out of `SKIPPED`, the slo-pitch combos through `sides_order`; every other case unchanged |
| `tests/test_jekyll.py` | a slo-pitch build: a game page has the line score with H, the facts list, two batting tables, "Mudcats at Sluggers"; Home has the eyebrow cards, the "5" legend key, the AVG tile ".640"-style; a `batting: none` build has no Leaders and no player table; noindex on every preview page |
| `tests/test_landing.py` | the slo-pitch card is live, `coming_soon` empty, no warning, no coming-soon card on the page |
| core tests | E20, E23-E27 in `test_sports.py`, `test_build.py`, `test_option_stats.py`, `test_matchup.py` |

## 9. Work packages

Packages 1, 2 and 4 start together (no shared file). Package 3 starts when 2 is merged (it then owns
`contract.py`, `tests/parity/` and `tests/test_jekyll.py`). Package 4 writes `check` and `read` against this spec, and
`sport.yml` and `present` once 1 and 2 are merged. Package 5 needs 1-4. Package 6 finishes. Shared files have one owner
at a time: `sports.py`, `compute*.py` and the stub, basketball, curling and hockey golden files belong to 1 (every
JSON change is in package 1, so no other package rewrites a golden file); `test_jekyll.py` to 2, then 3, then 5;
`test_golden.py`, `tests/golden/slopitch/` and `tests/golden/landing/` to 5.

| # | Package (Sonnet builds) | Owns | Done when |
|---|---|---|---|
| 1 | Core data E20 (JSON), E23-E27 (Python) | `scripts/core/{sports,compute,compute_games,compute_stats,model}.py`, `index.html`, `stats/index.html`, `_layouts/{team,player,archive-season}.html`, `tests/test_{sports,build,option_stats}.py`, `tests/fixtures/sports/` (the option-stats sport), `tests/golden/{stub,basketball,curling,hockey}/` | tests green; golden diffs only new keys (`extras`, `card_head`, `matchup`, `sides_order`), read by eye; the built pages of the four sports byte-identical (compare `_site/` before and after) |
| 2 | Parts E20-E22 | `_includes/parts/{line-score,facts,stat-table,blocks}.html`, `scripts/design_system/{contract.py,specimens_scores.py}`, `tests/parity/`, `tests/test_parity.py`, `tests/test_jekyll.py` (block smoke), `docs/design.md` | parity green with `game-tables` out of `SKIPPED`, `line-score-rhe` and `game-tables-slopitch` added; `check_contrast.py` passes with `docs/contrast.md` unchanged; `build_css_fallbacks.py` and `build_design_system.py` run |
| 3 | Visitors first E26 (pages) | `_includes/parts/{final-panel,result-card,result-hero,game-row,next-game}.html`, `_includes/shell/ticker.html`, `_layouts/game.html`, `scripts/core/calendars.py`, then `contract.py`, `tests/parity/`, `tests/test_jekyll.py`, new `tests/test_matchup.py` | `vs` sites byte-identical; slo-pitch parity combos pass with home = Sluggers; a coin-toss line score orders its rows |
| 4 | Slo-pitch rules | `sports/slopitch/{sport.yml,rules.py,README.md}`, `sports/slopitch/fixtures/`, `tests/test_slopitch_{fixtures,sport}.py` | every row of 3.1 has a fixture; the README lists every check with its path and level, the X, walk-off, run-limit and mercy rules, the how-tos (a called game, extra innings, a coin toss, a substitute, a spare, a game without batting lines, a forfeit) and the settings a league may change |
| 5 | Sample, golden, preview, landing | `sports/slopitch/sample.py`, `tests/test_golden.py`, `tests/golden/slopitch/`, `tests/golden/landing/`, `tests/test_jekyll.py` (slo-pitch smoke), `tests/test_landing.py`, `landing.yml` | contract test green; golden files reviewed by eye; the CI run publishes `/slopitch/` and passes the link check (time per copy in the PR); screenshots at 390 px, light and dark, Slo-pitch layout: Home, Schedule, a game (mercy, extras, a walk-off), Stats, a team, a player, the landing page |
| 6 | Docs | `docs/sports.md` (`extras`, `facts`, `heading: plain`, `when`, `per_team_game`, `card_head`, `matchup`, `mark_option`), `docs/open-questions.md` (section 9), `docs/data.md` (the slo-pitch how-tos it points to), `README.md` (`/slopitch/`), `CLAUDE.md`, `PLAN.md` status (stage 5 done; the deferred list down to period words and team rates) | the docs say what the code does |

**Opus reviews:** package 1's interface (the new `sport.yml` keys and JSON shapes, the byte-identical claim) before 4
uses it; package 3's include diffs (every loop over the sides) before merge; package 4 line by line (the X and
walk-off rules, the batting side with `bats_first`, run limit with open innings and `finish`, mercy "4½", extra
innings, the R/H sums, every path and level); the slo-pitch golden standings and AVG board by hand against the sample
files (the per-team-game minimum); package 5's sample for believability (rec scores in the low teens, limit innings,
few walks, a believable walk-off). Then the whole pull request.

## 10. Open decisions for the owner

Each is **recommended, awaiting owner confirmation**. Every rule a league decides also shows as `[placeholder]`
until the league sets it.

1. **Visitors first.** Recommended: list the visitors first everywhere for slo-pitch ("Mudcats at Sluggers", the
   visitors' row on top), as scorebooks and the approved mockup do (E26, `display.matchup: at`). Trade-off: the
   largest core change of this PR (eight includes and the calendar); without it the home team sits on top and the
   X lands on the bottom row only by luck.
2. **Who bats first.** Recommended: the home team in the file is the team that bats last; a coin-toss game adds
   `bats_first: home`, which flips the line score's rows for that game. Trade-off: one more key the README must
   explain; leagues that never toss ignore it.
3. **Innings.** Recommended: 7 (`innings`, 3 to 9), `[placeholder]`. Trade-off: none; the line score follows.
4. **Run limit.** Recommended: 5 runs a half-inning (`run_limit`), the last inning and extra innings open
   (`open_innings: last`), and the limit play stops at the limit (`limit_play: stop`; `finish` counts every run on
   that play), all `[placeholder]`. A team-choice open inning is not built. Trade-off: a box at the limit is circled
   even when the third out came first (the sheet cannot tell).
5. **Mercy rule.** Recommended: 15 runs after 5 innings (4½ when the home team leads), `[placeholder]`, checked only
   when the sheet says `called: mercy`, and only as a warning. Trade-off: a game played out despite a big lead is not
   flagged.
6. **Time limit and called games.** Recommended: the score stands as written for completed innings; `called:` gives
   the reason; a game under 4 innings (`official_innings`) is a warning, not an error; `time_limit` 60 minutes,
   `[placeholder]`, shown only in the facts. Trade-off: leagues whose score "reverts to the last full inning" must
   leave the unfinished inning out themselves (README how-to).
7. **Ties and extra innings.** Recommended: a regular-season tie stands (`ties: true`, `extra_innings: 0`), as
   `BRIEF.md`'s 1 point for a tie implies; playoffs play extra innings, open, until decided. Trade-off: a league
   that plays one extra inning sets `extra_innings: 1`.
8. **The extra-innings word.** Recommended: "Final · Extras", "Win (Extras)", from `words.extra: {one: Extra inning,
   short: Extras}`. Alternative "Final/9" needs a core status template. Trade-off: the inning number is only in the
   line score.
9. **Standings.** Recommended: 2 a win, 1 a tie (`BRIEF.md`), ranked by points; columns GP W L T PTS RF RA (the
   mockup). Win % is one README line for leagues with many rain-outs. Trade-off: points reward teams that played
   more games when schedules are uneven.
10. **Tiebreakers.** Recommended: head-to-head, then run difference capped at 7 a game (`{diff: {cap: 7}}`),
    `[placeholder]`. Trade-off: head-to-head is skipped unless every tied pair has met (the core's rule).
11. **Forfeit score.** Recommended: 7-0 (`BRIEF.md`'s example), `[placeholder]`. Trade-off: it moves run difference
    by 7, up to the cap.
12. **Batting lines.** Recommended: optional by game (`batting: optional`): a game has lines for every batter or
    none, and stats come from the games that have them; `none` (team results only), `order` (games played only) and
    `every_game` are settings. Trade-off: with `optional`, a player's GP counts games with no line, so a per-game
    figure would mislead (none is shown).
13. **Which batting stats.** Recommended: AB, R, H, RBI, HR, BB on the sheet; PA, AVG and OBP worked out; no 2B/3B,
    sacrifice flies, strikeouts or pitching. OBP is (H + BB) / (AB + BB). Trade-off: no slugging percentage; a league
    that wants it needs two more columns on the sheet.
14. **AVG minimum.** Recommended: 2 plate appearances per team game (`avg_min_pa` with `per_team_game`, E24),
    `[placeholder]`, so the board fills from week 1 and stays fair. Alternative: the mockup's fixed "15 at-bats" (no
    core change, an empty board for the first weeks). Trade-off: one small core extension.
15. **R/H/E.** Recommended: R always, H kept (`team_hits: kept`; the batting lines' sum when kept), E not kept
    (`team_errors: none`; rec scorekeepers rarely judge errors, the mockup has R and H). Trade-off: E is one setting
    away, but the `/slopitch/` demo does not show it.
16. **Home-run limit.** Recommended: `hr_limit` per team per game, 0 = none, `[placeholder]` as `BRIEF.md` asks; a
    team over it is a warning (the sheet records what happened). Trade-off: leagues that count an extra home run as
    an out must write it as an out.
17. **Co-ed rules.** Recommended: no gender field in `players.yml`, no batting-order alternation check, no "walk the
    man, the woman bats" rule in the data; the league's co-ed rules go on its rules page. Trade-off: a co-ed order
    mistake is not caught, but the site keeps no personal data beyond "First L.".
18. **Doubleheaders.** Recommended: allow two games a team a day (`games_per_day: 2`); the sample keeps one game a
    night. Trade-off: none if `make_sample.py` is unaffected (package 5 checks).
19. **Walk-offs and the X.** Recommended: a bottom half that should have been an X, and a walk-off with too many
    runs, are warnings; an X where the home team trailed is an error. Trade-off: some rec leagues play the last half
    out for fun; a warning lets them keep the runs.
20. **Period words by option and team rates.** Recommended: not built in this PR (slo-pitch needs neither); both stay
    on `PLAN.md`'s "Later" list for a small core PR when a league asks. Trade-off: stage 5 ends with two deferred
    core ideas.
21. **Substitutes and courtesy runners.** Recommended: a substitute is their own row under the player replaced; a run
    counts for the row the sheet writes it on; no courtesy-runner key. Trade-off: a 55+ league's courtesy runs land
    on whoever the scorekeeper credits.
22. **Officials.** Recommended: umpires' names are not copied or shown (as hockey's referees).

## Risks

- **Real sheets differ.** Some scorebooks have no R/H/E box, some keep one page per team, some write the batting order
  without lines, and run-limit and mercy wording varies most of all. The file format is fixed now; stage 7's entry
  page and photo prompt translate into it. Decisions 4, 5, 6 and 12 are where a league is most likely to push back.
- **Rules I could get wrong.** The walk-off count (only a home run brings in more than the winning run), mercy "4½",
  what a circled box means, and extra-inning run limits vary between rule books (USA Softball, Softball Canada, house
  rules). Each is one rule in `rules.py`, a README line and a fixture rewrite.
- **Visitors first touches every game listing.** E26 changes eight includes and the calendar for every sport, behind a
  default that must print exactly what it prints today. Package 3 gets its own Opus review; the four sports' pages and
  calendars must be byte-identical (golden files, the off-site hash, a before-and-after `_site/` compare).
- **Options multiply.** `batting` (4 values), `team_hits`, `team_errors`, `open_innings` and `limit_play` give many
  page shapes; the contract test covers each value once, and E23 is tested on its own sport, not only through
  slo-pitch.
- **Line score width at 360 px.** 7 innings, R, H and E plus the team column fit (the chip is dropped on the full
  size); 9 or 10 innings scroll in their own box with the team column fixed, as the design system already does.
- **Privacy.** Co-ed leagues may ask for gender to check batting orders; decision 17 keeps it out.
- **Deploy time.** `/slopitch/` adds a fourth sport preview (about 10 seconds and 2-3 MB per deploy), and the landing
  page builds one more demo.
