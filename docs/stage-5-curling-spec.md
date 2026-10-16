# Stage 5, part 2: curling

Status: **draft for the owner's review**. Nothing is built yet. Section 10 lists the decisions: until one is
answered, the build follows the recommendation, and every rule a league decides shows as `[placeholder]`.
Curling is new (the Masters site is basketball only), so the references are `BRIEF.md` ("Curling (club league)"),
the approved curling mockups and the curling specimens on the design-system page (`scripts/design_system/sample.py`,
Pine Lake Curling Club).

Read first: `BRIEF.md`, `docs/stage-4-spec.md` section 3 (the sport interface), `docs/stage-5-basketball-spec.md`
(the model for this document), `docs/sports.md` (what the code does today), `docs/design.md` (the curling look).

Curling words used here: an **end** is one round of 16 stones (like an inning); only one rink scores in an end, or
nobody does (a **blank end**). The **hammer** is the last stone of an end, an advantage: it goes to the rink that
did not score, and a blank end keeps it with the same rink. A rink that scores without the hammer has **stolen** the
end. A **rink** is a team of four (lead, second, vice, skip); the **skip** leads it. Teams **shake hands** to
concede. A **draw** is one game time; a **sheet** is one lane of ice (A, B, C...).

---

## 1. Scope

**In this pull request**

| What | Where |
|---|---|
| The curling sport folder | `sports/curling/`: `sport.yml`, `rules.py` (`check`, `read`, `present`, `derive`), `sample.py`, `README.md` (the game file box by box, for the volunteer) |
| Shared test files | `sports/curling/fixtures/`: one game per case, with the expected problems and numbers (section 8), for the stage 7 JavaScript port |
| Two new display parts | `numbers` ("The game in numbers") and `roster` (the lineups): includes, parity cases (section 6, E5 and E6) |
| Small core extensions | the card's own line score and meta, the extra-end word, a results legend, the skip line on team cards, three sample-generator constants (section 6) |
| Sample seasons | two made-up curling seasons for the golden files and the `/curling/` sport preview (section 7) |
| Docs | `docs/sports.md`, `docs/open-questions.md` (curling's placeholders), `README.md` (the `/curling/` address), `PLAN.md` status |

**Not in this pull request**

- The JavaScript copy of the rules and the entry page: stage 7 (decided for basketball: decision 8 there). The fixtures
  are written now so the port can be tested against them.
- A printable curling score card and the photo-reading prompt: later (`PLAN.md`).
- The "club scoreboard" display (end numbers hung under the running score, `BRIEF.md`'s option): a new line-score shape
  with no specimen yet. Decision 11.
- Hockey and slo-pitch, and core features only they need (leaderboard `order: asc`, a `format:` for rates).
- Six layouts per sport and the screenshot sweep: stage 6. This PR screenshots the curling sample in the Curling
  layout only. The shipped `league.yml` stays `sport: basketball`; the committed `data/sample-*` stay basketball.

## 2. The game file

### 2.1 What a club score card holds, and how it maps

A club curling score card is small: the draw, the sheet, the two rinks and their players by position, a box per end
for each rink (with the ends numbered across the top), an extra-end box, a Total, and often a mark for which rink had
the last stone in the first end ("LSFE", decided by a coin toss or the league's own rule). The game file copies that,
box for box, in the core envelope (`docs/data.md`) with the sport's part under `sheet:`.

| On the card | In the file | Notes |
|---|---|---|
| draw, sheet, date, time | the schedule row (`schedule.csv`: `date`, `time`, `surface` = `A`) | the core's, as for every sport |
| the two rinks | the envelope's `home` and `away` | "home" is only the first-listed rink; pages say "vs" |
| LSFE / hammer in end 1 | `sheet.hammer: home` or `away` | required (decision 6). Every later end's hammer follows from the scores |
| one box per end per rink | `sheet.ends.<side>`: one entry per end, `0` to `8`, `X` for an end not played | exactly `rules.ends` boxes (8 by default, decision 1) |
| extra end(s) | `sheet.extra.<side>`: one entry per extra end | only when level after the last end (decision 2) |
| "shook hands after 6" | `sheet.conceded: <side>`: the rink that conceded; the ends left are `X` | decision 7 |
| time called (ice time ran out) | `sheet.time_called: true`; the ends left are `X` | decision 7 |
| Total | `sheet.final.<side>` | must equal the ends plus the extra ends |
| players by position | `sheet.lineups.<side>`: rows in throwing order, each `{player, position}`, a spare with `spare_for` | when `rules.lineups` is `recorded` (decision 8) |
| scorekeeper, checked by, notes | the envelope (`scorekeeper`, `checked_by`, `notes`) | the core's |
| a forfeit | the envelope's `forfeit: <team id>`, no `sheet` | the core's, as for every sport |

### 2.2 Example

The approved Curling-Game mockup as a file (Button Pushers 7, Hurry Hard 5; Hurry Hard had the hammer in end 1;
Button Pushers stole end 4; end 1 was blank; Ron M. spared for Brian S.).

```yaml
game_id: 2026-12-01-1          # the core envelope: unchanged for every sport
status: final
home: button-pushers
away: hurry-hard
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  hammer: away                 # who threw the last stone of end 1 (LSFE)
  ends:                        # points per end, end 1 first; 0 for the rink that did not score; X = not played
    home: [0, 0, 1, 1, 0, 3, 0, 2]
    away: [0, 2, 0, 0, 1, 0, 2, 0]
  final: {home: 7, away: 5}    # the Total boxes, as written
  lineups:                     # in throwing order, lead first, as on the card
    home:
      - {player: carol-d, position: lead}
      - {player: ken-w, position: second}
      - {player: linda-f, position: vice}
      - {player: doug-h, position: skip}
    away:
      - {player: pat-o, position: lead}
      - {player: ron-m, position: second, spare_for: brian-s}
      - {player: joanne-t, position: vice}
      - {player: wayne-b, position: skip}
```

A concession and an extra end look like this (only the changed boxes shown):

```yaml
  ends:                        # Free Guards shook hands after end 6
    home: [0, 2, 2, 0, 3, 1, X, X]
    away: [1, 0, 0, 2, 0, 0, X, X]
  conceded: away
  final: {home: 8, away: 3}
---
  ends: {home: [1, 0, 2, 0, 0, 1, 0, 0], away: [0, 1, 0, 1, 2, 0, 0, 0]}   # a playoff game, 4-4 after eight
  extra: {home: [0, 1], away: [0, 0]}  # the first extra end was blank (keep playing); home scored 1 in the second
  final: {home: 5, away: 4}
```

In a draft (`drafts/`), any box may be left empty (`~`) and a lineup row may be `{name: Jo K., position: lead}` (a spare
written in by hand, no player id yet), as basketball allows a sub's name. `X` is plain text in YAML and in a
JavaScript YAML reader alike, so the stage 7 port needs no special case.

### 2.3 Why this shape

- **End by end, not the club scoreboard.** The end-by-end grid is what the line score, the hammer walk and every stat
  need, and most score cards have it. A scoreboard-style card can be copied into it by the volunteer (or, in stage 7,
  by the entry page); the reverse is not true for blanks. Decision 11.
- **Only the first hammer.** The rest follows from the scores, so a second record of it could only disagree. A card
  that marks the hammer in every end is copied by its first mark.
- **`X` instead of a shorter list.** The file has every box the card has, so a missing number is visible as a missing
  box, and "not played" is a mark the volunteer writes, never something the rules guess.

### 2.4 Paths

Paths are relative to `sheet` in `check` (the core adds `sheet.`), counting from 0 as every sport does: `ends.home.3`
is end 4. The README says so with a picture of the boxes.

| Path (after the core adds `sheet.`) | The box |
|---|---|
| `sheet.hammer` | the LSFE mark |
| `sheet.ends.away.3` | the away rink's box for end 4 |
| `sheet.extra.home.0` | the home rink's first extra-end box |
| `sheet.conceded`, `sheet.time_called` | the "shook hands" and "time" notes |
| `sheet.final.home` | the home rink's Total box (`Score.final_at`) |
| `sheet.lineups.away.1` (`.player`, `.position`, `.spare_for`, `.name`) | the away rink's second lineup row |

## 3. The rules in Python

### 3.1 Checks

"Gap" means an error in `games/` and a warning in `drafts/` (the core rule for empty boxes). `check` never raises,
returns every problem, and stops a branch when a problem makes the later checks meaningless (no `ends` block: no end,
extra-end or Total checks), as basketball does.

| Check (path relative to `sheet`) | Level |
|---|---|
| a key other than `hammer ends extra conceded time_called final lineups` (`<key>`) | error |
| `hammer` missing | gap |
| `hammer` not `home` or `away` | error |
| `ends` missing, or not a block with `home` and `away` | gap |
| `ends.<side>` not a list of exactly `rules.ends` boxes ("this league plays 8 ends: write 8 boxes, X for an end not played") | error |
| `ends.<side>.<i>` empty | gap |
| `ends.<side>.<i>` not a whole number from 0 to 8, or `X` | error |
| `ends.<side>.<i>` is 7 or 8 ("very rare: check the card") | warning |
| `ends.home.<i>`: both rinks scored in one end (only one rink scores in an end) | error |
| `ends.<side>.<i>`: `X` for one rink and a number for the other | error |
| `ends.<side>.<i>`: a number after an `X` (`X` marks only the ends left when a game stopped early) | error |
| `ends.home.0` is `X` (no end was played: that is a forfeit, not a score) | error |
| `ends.<side>.<i>`: the first `X`, with neither `conceded` nor `time_called` set | error |
| `conceded` not `home` or `away`; set although every end was played; set together with `time_called` | error |
| `conceded`: the rink that shook hands was not behind ("the score stands as it is, so the rink that concedes is the one behind") | error |
| `time_called` not `true` | error |
| `extra`, `extra.<side>` not lists of the same length; `extra.<side>.<i>` not 0 to 8 | error |
| `extra` filled in, but the game was not level after the last end, or it stopped early | error |
| `extra` filled in for a regular-season game when `rules.extra_end` is `playoffs` | error |
| `extra.home.<i>`: both rinks scored; an extra end after the one that broke the tie; the last extra end blank (a game ends on a score) | error |
| `extra` missing although the game was level after the last end, in a playoff game or with `extra_end: always` (and not `time_called`) | error |
| `final`, `final.<side>` missing | gap |
| `final.<side>` not a whole number, or not the ends plus the extra ends ("the Total box says 7, but the ends add up to 6") | error |
| `lineups` filled in when `rules.lineups` is `none` | error |
| `lineups`, `lineups.<side>` missing when `rules.lineups` is `recorded` | gap |
| `lineups.<side>` not a list of 3 or 4 rows (a rink may play three; more than four never throw) | error |
| `lineups.<side>.<i>` not a row; an unknown key (`.<key>`) | error |
| `.position` missing, not `lead second vice skip`, or the same position twice in a rink; a rink with no `skip` | error |
| `.player` missing (only a `name`: a spare not yet in `players.yml`) | gap |
| `.player` not in `players.yml`; listed twice in the game | error |
| `.player` on another team, not `sub: true`, and no `spare_for` | warning |
| `.spare_for` not a player of this rink in `players.yml`, or also in this lineup | error |
| `.spare_for` set on a row whose player is a regular of this rink | warning |

The core then adds, at `Score.final_at` (`sheet.final.<side>`): a tied playoff game (only reachable with
`time_called`, since the sport already asks for the extra end), and a tied regular-season game when `ties: false`.

### 3.2 How the numbers come from the sheet (`read`)

**The hammer walk.** Start with the rink in `hammer`. For each end played, regulation then extra: note who had the
hammer; if nobody scored, the end is blank and the hammer stays; if the rink with the hammer scored, it gives the
hammer up; if the other rink scored, that is a steal and the hammer stays with the rink that had it. (This is the
rule the design-system sample is already checked against: `_check_curling_result` in `sample.py`.)

| Number | From |
|---|---|
| Final | the ends plus the extra ends (the Total box must agree) |
| `Score.periods` | the regulation ends, `None` for each `X` (the core counts an unplayed end for nobody) |
| `Score.extra` | the extra ends, when played; `decided_in` is `overtime` then, otherwise `regulation` |
| `final_at` | `sheet.final.<side>` |
| team `ends_won` | ends the rink scored in, extra ends included |
| team `stolen` | ends scored without the hammer |
| team `hammer_ends` | ends played with the hammer (blank ends included) |
| team `hammer_scored` | ends scored with the hammer ("scored with hammer 3 of 5") |
| team `blanks` | blank ends while holding the hammer ("a blank counts to the rink that had hammer and kept it", as the mockup) |
| team `big_ends` | ends of 3 or more |
| team `ends` | ends played, extra ends included (for the "of 54 ends" detail only) |
| player lines | one `Line` (group `player`, no counts) per lineup row with a player id: one game played. A spare gets the game, not the regular they replaced |
| `facts` | `hammer_by_end` (side per played end), `stopped` (`conceded` and the side, or `time`), `ends` (the league's number), the lineup rows (position, `spare_for`) for the roster block |

`derive` returns `{}`: curling has no rates (decision 9, decision 10).

### 3.3 Extra ends, ties, concessions, time, forfeits

- **Level after the last end** (`rules.extra_end`, decision 2): with `playoffs` (the default), a regular-season game
  level after the last end is a tie, and a playoff game goes to an extra end; with `always`, every level game goes
  to an extra end. Extra ends go on until one ends with a score; a blank extra end means another one (the hammer
  stays, as in any blank end). The winner of an extra end has an `ot_win` for the core, and `points.ot_win` and
  `ot_loss` default to win and loss, so an extra end changes nothing in the standings unless a league says so.
- **Ties**: the core's `standings.ties` (default `true`, `[placeholder]`). A regular-season tie with `ties: false` is
  reported by the core at the Final box.
- **A concession** ends the game after the last completed end; the score stands as it is, the rink that conceded
  must be behind, and the remaining ends are `X`. It is a regulation result (a win and a loss), not a forfeit: the
  ends played count in every stat. No minimum number of ends is enforced (decision 7).
- **Time called**: the same, but with no rink conceding; a level game is then a tie (or the core's error when ties
  are not allowed, or in a playoff).
- **A forfeit** is the core's (`forfeit: <team id>`, no sheet): no player gets a game, no team stat moves. Its score
  is `standings.forfeit` (decision 5).

## 4. Standings and stats

### 4.1 Standings defaults (`sport.yml`)

```yaml
standings:
  rank_by: points
  points: {win: 2, tie: 1, loss: 0}                     # BRIEF: 2 for a win, 1 for a tie
  period_points: 0
  ties: {value: true, decide: true}                     # decision 2
  forfeit: {value: {score: [1, 0]}, decide: true}       # decision 5
  tiebreakers: {value: [head_to_head, diff], decide: true}   # BRIEF: head-to-head, then points for and against
  columns: [gp, w, l, t, pts, pf, pa]                   # the approved Curling-Home table
```

A league that ranks on ends won writes `tiebreakers: [head_to_head, periods_won]` (the core's `pw`, shown as EW
"Ends won", counts regulation ends only: decision 4). The README gives the lines for the common variants.

### 4.2 Player stats: games played only

`BRIEF.md`: "Players: games played and position; spares listed." So the player group has **no counting stats**
(`stats.player: []`); the core counts `gp` from the lineups. A player's position is the `players.yml` one (the player
page already shows it: "Skip · 2026–27 season"); a spare is a player with `sub: true`, shown as "Spare" in the Stats
table's team column, as today. No player leaderboards. Decision 9 (the alternative: games as a spare, games at each
position).

| Page | Shows |
|---|---|
| Stats: "All players" | Player · Team · GP |
| Player: season | GP (Season row, Playoffs row) |
| Player: game log | the opponent, result and score (no stat columns: `log: []`) |

### 4.3 Team stats

`stats.team`: `ends_won` EW "Ends won", `stolen` SE "Stolen ends", `blanks` BE "Blank ends", `big_ends` 3+ "Big ends
(3 or more)", `hammer_ends` HE "Ends with hammer", `hammer_scored` HS "Scored with hammer", `ends` E "Ends played",
summed over the regular season like every core team stat. A league may add any of them to its standings `columns`.

"Scored with hammer" counts any score with the hammer, as the mockup does; it is not the "hammer efficiency" some
analysts quote (scoring two or more). Rates such as "ends won %" are not built (decision 10).

### 4.4 Leaderboards ("Rink leaders")

| Board | Stat | Tile | Detail | Notes |
|---|---|---|---|---|
| Stolen ends | `stolen` | yes, hot | "in {gp} games" | as the mockup |
| Ends won | `ends_won` | yes, accent | "of {ends} ends, {gp} games" | the mockup showed "50%"; a count until decision 10 |
| Big ends (3 or more) | `big_ends` | no | "in {gp} games" | as the mockup's list |

All three are `of: team` boards, which the core supports today (`_team_board`, details over the team's stats and
standings columns). No minimums.

## 5. Pages

### 5.1 The game page (`present`)

| Block | Part | Content | Exists? |
|---|---|---|---|
| final panel | core `final-panel` | the ink band with both rinks and the big score; status "Final", "Final · EE" after an extra end (E8); sub "Button Pushers by 2" | yes |
| line score (the hero) | core `line_score`, shape `ends`, full size | title "End by end", meta "8 ends · no extra end" / "8 ends · extra end" / "Shook hands after 6 of 8 ends" / "Time called after 7 of 8 ends"; corner "End", columns `1`..`8` and one `EE` column per extra end, total "Tot"; cells: scored end `won`, stolen end `mark` (tint, frame, hidden words "stolen end"), unplayed `void` (X), the hammer marker in each end's cell; a blank end's column `blank` (shaded, hidden word "blank end"); the note "**Hurry Hard** had hammer in the first end." and the legend Hammer (last rock), Stolen end, Blank end (Not played when there is an X) | yes: the include already prints every flag and the parity case compares it |
| result card | core `card` with its own compact `line_score` | the end table without per-cell hammers or blank shading, the hammer marker after the rink that had it in end 1; foot "Sheet A · 6:30 PM", plus "Shook hands after 6" when conceded; link "Game" | the card's own line score and extra meta are E7 |
| hero (Scoreboard) | core, from the card line score with team codes | | yes |
| the game in numbers | **new** `numbers` block (E5) | heads: each rink's chip and code; rows Ends won, Stolen ends (`is-hot` on the stealing rink), Ends with hammer, Scored with hammer ("3 of 5"), Blank ends, Big ends (3+); the bigger value bold (`is-key`); note "A blank counts to the rink that had hammer and kept it." | specimen and CSS yes; include and parity no |
| lineups | **new** `roster` block (E6) | per rink: a head (chip, rink name, "Rink ›" linking the team page; plain text in a past season), rows Lead, Second, Vice, Skip (skip bold), a spare with the outline "Spare" badge and "for Brian S."; note "In throwing order, as on the score card." Left out when `rules.lineups` is `none` | specimen and CSS yes; include, the plain-text head and parity no |

The data comes only from `Reading` (`facts` and `team_lines`) and `ctx.players`, as for every sport.

### 5.2 The other pages

| Page | Curling shows | Exists? |
|---|---|---|
| Home | the next draw (Curling layout: grouped by start time, the house emblem, "Sheet A" tiles); "Latest draw" result cards with the legend row above them (Hammer in end 1, Stolen end, Not played); standings headed "Rink"; "Rink leaders" tiles and lists | the legend row is E9; the rest is core today |
| Schedule | "Draw 7" days, sheet letters, cancelled and moved games, playoffs apart | yes |
| Team | the team card with the skip line ("Skip Gail R."), the roster table (GP), results, upcoming, calendar | the skip line is E10 |
| Player | position and season line, GP, game log | yes (a group with no counting stats is tested in E11) |
| Stats | the three rink boards (tiles, then the list), "All players" with GP | yes |
| Archive season | as every sport; rosters' heads not linked | E6 |

Words in `sport.yml`: period `{one: End, many: Ends, short: E}`, extra `{one: Extra end, short: EE}` (E8), surface
`Sheet`, day `Draw` (decision 12), points for/against `PF`/`PA`; labels `results: Latest draw`, `next: Next draw`,
`leaders: Rink leaders`, `team: Rink` (Classic and Scoreboard keep "Team", as the mockups); `display: {card: lines,
card_foot: meta, surface: label, results_legend: [...], team_sub: skip}`; `positions: [lead, second, vice, skip]`;
`game_minutes: 120`; `default_layout: curling`. Options: `ends` (int, 4 to 10, default 8, `decide: true`),
`extra_end` (choice `playoffs`/`always`, `decide: true`), `lineups` (choice `recorded`/`none`).

## 6. Core extensions

Checked against the code (`scripts/core/{model,sports,compute,compute_games,compute_stats,standings}.py`,
`_includes/parts/`, `tests/parity/cases.py`, `scripts/make_sample.py`, `tests/test_sport_contract.py`). Numbered after
basketball's E1-E4. Each is generic: none tests the sport id, and each is needed for curling's approved pages.

| # | Extension | Needed now because | Files | Tests |
|---|---|---|---|---|
| E5 | **`numbers` block**: `{type, title, corner, rows: [{label, cells: {home, away}, key: home/away/null, hot}], note}` | the game page in the approved mockup | `model.py` (`BLOCK_TYPES`); new `_includes/parts/numbers.html`; `parts/blocks.html` (dispatch); `scripts/design_system/contract.py` (`_curling_blocks`); `tests/parity/cases.py` (a fragment case `game-tables-numbers` for curling; the `game-tables` skip reason narrowed to hockey and slo-pitch); `docs/design.md` (includes table) | parity in every layout that shows curling's game tables (Curling, Classic), light and dark. CSS (`.st-table--numbers`, `.is-hot`) and its contrast pairs exist; `check_contrast.py` passes with `docs/contrast.md` unchanged |
| E6 | **`roster` block**: `{type, title, teams: [{side, rows: [{role, player, key, spare_for}]}], link_label, note}` | the lineups in the mockup; `BRIEF.md` "spares listed" | `model.py`; new `_includes/parts/roster.html`; `parts/blocks.html`; `parts-scores.css` (the head's rules move from `a.st-roster__head` to `.st-roster__head`, hover only on the link, so a past season's plain head looks the same); `contract.py`; `tests/parity/cases.py` (remove `roster` from `SKIPPED`, add `cases/roster.html`); `docs/design.md` | parity for the roster part in all six layouts; Jekyll smoke: an archive game prints a `div` head and no link; `check_contrast.py` passes unchanged (same roles) |
| E7 | **The card's own line score and extra meta**: `present()`'s `card` may carry `line_score` (compact) and `meta_extra` (a list of strings, appended after the sheet and time) | the compact card in the mockup has no per-cell hammers or blank shading, and "Shook hands after 6" sits in the card foot; `compute_games._card` drops both today, while the include and the parity data already expect them | `compute_games.py` (`_card`: pass `line_score` through `_line_score`'s defaults, append `meta_extra`); `docs/sports.md` | unit test in `test_build.py`; the stub and basketball golden files change only by `card.line_score: null` (reviewed by eye) |
| E8 | **The extra-period word**: optional `words.extra: {one, short}`; the final status uses `short` ("Final · EE"; "OT" when unset), the points sentence says "an extra-end win", and the `periods_won` tiebreak phrase uses the period word ("ends won", not "periods won") | an "OT" on a curling page is wrong, and "periods won" is not curling | `sports.py` (`_check_words`); `compute_games.py` (`OVERTIME_WORD`); `compute.py` (points sentence); `standings.py` (`tiebreak_note` takes the period word) | `test_sports.py` (schema), `test_standings.py` (the phrase), golden unchanged for stub and basketball |
| E9 | **Results legend**: optional `display.results_legend: [{kind, text}]` (`kind` one of the legend keys), printed by `parts/legend.html` above a list of result cards on Home, Schedule and a team page | the approved Curling-Home has it, and the card's marks need it for sighted readers (the hidden words serve screen readers) | `sports.py` (`_check_display`); `compute.py` (`league.json.results_legend`); `index.html`, `schedule/index.html`, `_layouts/team.html` | `test_sports.py`; `test_jekyll.py` (present for curling, absent for basketball) |
| E10 | **The skip line on team cards**: optional `display.team_sub: <position>`; `teams.json` `sub` = "Skip Gail R." from the regular with that position in `players.yml` (none: no line; two: the first in the file) | the approved curling team card shows it | `sports.py` (must be one of `positions`); `compute.py` (`_teams`) | unit test; parity's `team-card` case already carries a sub |
| E11 | **Sample generator constants and a group with no counting stats**: optional `SURFACES` (default `1`, `2`...), `TIMES` (default today's), `NUMBERS` (default `True`) and `POSITIONS` (default none: written to `players.yml` in roster order) in `sample.py`; the contract test asks for a `00` jersey only when `NUMBERS` is on, and for `PLAYERS_PER_TEAM` players a team instead of five; `stats.player: []` works end to end | a curling sample with sheet letters, two draw times, no jersey numbers, positions and four players a rink; today `make_sample.py` writes numbers and `1`, `2` and the contract test demands five players and a `00` | `scripts/make_sample.py`, `tests/test_sport_contract.py`, `tests/test_make_sample.py`, `tests/test_build.py` (a sport with an empty player group: Stats table GP only, empty log columns, no player boards) | `make_sample.py --check` passes with the committed basketball sample byte for byte unchanged |

**Considered and not built** (none is needed by the approved curling pages, and an option no sample uses goes
untested):

| Idea | Why not now |
|---|---|
| A tiebreaker on any team stat (`{stat: stolen}`) | `periods_won` already ranks on ends won; no curling rule we know of breaks ties on steals. Easy to add (`standings.py` + `sports.py`) when a league asks |
| Team rates ("ends won 50%") | decision 10: needs `derive` for teams, rounding and ranking on team boards |
| The club-scoreboard line score | decision 11: a new shape with no specimen |
| A different number of ends for playoffs, a minimum number of ends before conceding | decisions 1 and 7: a league can set `ends` per season with `overrides`; nobody has asked for either |
| Hiding the Stats page's player table when `lineups: none` | it is the deferred "stats shown only when an option is on" (basketball spec section 5); the table shows its empty state |

Still deferred, with the sport that needs them: `order: asc` (hockey), `format:` for rates (slo-pitch, hockey), period
words chosen by an option (basketball halves).

## 7. Sample data

`sports/curling/sample.py`:

- `LEAGUE_NAME = "Pine Lake Curling Club"` (the made-up league of `BRIEF.md` and the design system).
- `TEAMS`: Button Pushers BP, Hurry Hard HH, Hog Liners HL, Free Guards FG, Takeouts TO, Stone Cold SC (the design
  system's six; ids `button-pushers`...). Six rinks: three games a draw, no byes.
- `PLAYERS_PER_TEAM = 4`, `NUMBERS = False`, `POSITIONS = ["lead", "second", "vice", "skip"]`, `SURFACES = ["A", "B",
  "C"]`, `TIMES = ["18:30", "18:30", "20:45"]` (sheets A and B at the early draw, C at the late one, as the
  mockup's next draw). Names come from `make_sample.py`'s made-up pool ("First L.").
- `sheet(rng, game, ctx)`: toss for the hammer; play `rules.ends` ends with simple odds (the rink with the hammer
  scores 1-3 most often, sometimes blanks to keep it; the other rink sometimes steals 1 or 2); repeat with the same
  `rng` until the outcome is met, then fix the last end if needed. A rink behind by five or more after
  three-quarters of the ends sometimes shakes hands (`conceded`, the rest `X`). A requested `tie` stays a tie with
  `extra_end: playoffs` and becomes an extra-end game with `always`; a playoff game level after the last end gets
  extra ends. When `game.players` has a spare, it replaces one regular with `spare_for`. In `drafts/`, one lineup row
  is a `name:` only (the draft path of the rules). Over a season it writes a few steals, blanks, big ends, at least
  one concession and one extra-end game.

`scripts/make_sample.py` does the rest unchanged (round robin, a cancelled and a moved draw, a forfeit, a tie where
allowed, playoff rows, one draft); E11 adds only the constants. **Ends**: the shared `data/seasons.yml` cannot give
one sport's sample season its own `ends` (an `overrides: {rules: {ends: 6}}` would be an unknown option for
basketball), so both sample seasons play the default 8; `tests/test_curling_sport.py` generates a season with
`ends: 6` and with `ends: 10` and runs every check on it, and the fixtures cover both (section 8).

Golden files: `tests/golden/curling/` (`SPORTS` in `test_golden.py` gains `curling`), written with
`UPDATE_GOLDEN=1` and checked by hand once: standings, the three rink boards, one concession game, one extra-end game.
The sport preview `/curling/` appears by itself (`sport_previews: true` builds every sport with a `sample.py`); its
banner then lists Basketball and Curling. The shipped `league.yml` and the committed `data/sample-*` stay basketball.

## 8. Tests

| Test | What |
|---|---|
| `sports/curling/fixtures/` + `tests/test_curling_fixtures.py` | the **shared fixtures**, in basketball's format: `context.yml` (two made-up rinks, Alpha and Bravo, four players each with positions, a spare with `sub: true`, a player of a third team, default options) and per case `<name>.yml` (`fixture: {folder, game_type, options}` + `sheet:`) with `<name>.expected.json` (`problems` in order; `reading`: score, lines, team lines, facts, or `null`). `UPDATE_FIXTURES=1` rewrites them for review. Stage 7's Node runner reads the same files |
| fixture cases (about 45, one or more per row of 3.1) | `clean` (the mockup game), `clean-6-ends` and `clean-10-ends` (options), `blank-first-end`, `steals-and-big-end`, `eight-ender` (warning), `both-scored`, `nine-on-an-end`, `x-on-one-side`, `number-after-x`, `x-without-reason`, `conceded`, `conceded-while-ahead`, `conceded-all-played`, `conceded-and-time`, `time-called-tie`, `extra-end-playoff`, `extra-end-always`, `two-extra-ends` (first blank), `extra-end-not-level`, `extra-end-regular-when-playoffs`, `extra-end-blank-last`, `level-playoff-no-extra`, `bad-total`, `no-hammer` (game and draft), `hammer-text`, `wrong-number-of-ends`, `lineup-three`, `lineup-five`, `two-skips`, `no-skip`, `unknown-position`, `spare-for-regular`, `spare-for-unknown`, `spare-from-other-team` (no warning), `other-team-no-spare` (warning), `player-twice`, `draft-with-name`, `name-in-final`, `lineups-when-none`, `no-lineups` (game and draft), `unknown-keys`, `not-a-block` |
| `tests/test_curling_sport.py` | `read`'s hammer walk against the design-system sample's three games (`_check_curling_result` agrees); `present` (flags per cell, the `EE` columns, the meta for each way a game ends, the compact card line score, the numbers rows and bold cells, the roster with a spare, no roster with `lineups: none`); `derive` returns `{}`; `sample.sheet` honours every outcome under both `extra_end` values and with `ends` 6, 8 and 10 |
| `tests/test_sport_contract.py` | picks up the folder by itself (sample checks for every value of `extra_end` and `lineups`, mutated sheets, paths, drafts never stricter); E11's two relaxed conditions |
| `tests/test_golden.py` | `tests/golden/curling/` beside `stub/` and `basketball/` |
| `tests/test_parity.py` | E5 and E6: the `roster` case in six layouts and the `game-tables-numbers` fragment, light and dark |
| `tests/test_jekyll.py` | a curling build (`sport_previews: [curling]` or a temporary root): a game page has `.st-table--numbers`, `.st-roster`, `svg.st-hammer` and the void X; Home has the results legend; an archive game's roster head is not a link; a team card has the skip line; noindex on every preview page |
| core tests | E5-E11 in `test_sports.py`, `test_build.py`, `test_standings.py`, `test_make_sample.py` |

## 9. Work packages

Packages 1, 2 and 3 start together (no shared file). Package 4 starts with them on `check` and `read`, and adds
`present` once 1 and 2 are merged. Package 5 needs 3 and 4. Package 6 finishes. Packages that share a file
(`sports.py`, `test_jekyll.py`, the golden files) never run at the same time: 1 owns `sports.py` and the stub and
basketball golden files; 2 and 5 both touch `test_jekyll.py`, and 5 runs after 2.

| # | Package (Sonnet builds) | Owns | Done when |
|---|---|---|---|
| 1 | Core data extensions E7-E10 | `scripts/core/{sports,compute,compute_games,standings}.py`, `index.html`, `schedule/index.html`, `_layouts/team.html`, `tests/test_{sports,build,standings}.py`, `tests/golden/{stub,basketball}/` | tests green; stub and basketball pages unchanged; golden diffs only the new keys, read by eye |
| 2 | Parts E5-E6 | `scripts/core/model.py` (`BLOCK_TYPES`), `_includes/parts/{numbers,roster,blocks}.html`, `assets/css/parts-scores.css`, `scripts/design_system/contract.py`, `tests/parity/`, `tests/test_parity.py`, `tests/test_jekyll.py` (archive roster head), `docs/design.md` | parity green with the `roster` skip removed and the numbers fragment added; `check_contrast.py` passes with `docs/contrast.md` unchanged; `build_css_fallbacks.py` run |
| 3 | Sample generator E11 | `scripts/make_sample.py`, `tests/test_sport_contract.py`, `tests/test_make_sample.py` | `make_sample.py --check` clean on the committed basketball sample; the new constants tested with a throwaway sport in `tests/fixtures/sports/` |
| 4 | Curling rules | `sports/curling/{sport.yml,rules.py,README.md}`, `sports/curling/fixtures/`, `tests/test_curling_{fixtures,sport}.py` | every row of 3.1 has a fixture; the README lists every check with its path and level, the hammer rule, and the volunteer's how-tos (a concession, time called, an extra end, a spare, a three-player rink, a forfeit) and the warning about rink names (decision 13) |
| 5 | Sample, golden, preview | `sports/curling/sample.py`, `tests/test_golden.py`, `tests/golden/curling/`, `tests/test_jekyll.py` (curling smoke) | contract test green; golden files reviewed by eye; the CI run publishes `/curling/` and passes the link check (time per copy in the PR); screenshots at 390 px, light and dark, Curling layout: Home, Schedule, a game (with a concession and with an extra end), Stats, a team, a player |
| 6 | Docs | `docs/sports.md` (new keys, blocks, sample constants), `docs/open-questions.md` (curling's placeholders and section 10), `README.md` (`/curling/`), `CLAUDE.md`, `PLAN.md` status | the docs say what the code does |

**Opus reviews:** package 1's interface (the new `sport.yml` keys and JSON shapes) before 4 uses it; package 4 line
by line (the hammer walk, steals, blanks, extra ends, concession and time, ties and the core's checks, every path and
level); the curling golden standings and boards by hand against the sample files; package 5's sample for
believability (scores, steals, concessions that look like a club league). Then the whole pull request.

## 10. Decisions for the owner

All recommended, **awaiting the owner's confirmation**; the build follows the recommendation until then. Each rule a
league decides also shows as `[placeholder]` until the league sets it.

1. **Ends in a game.** Recommended: an `ends` option, 4 to 10, default 8 (`BRIEF.md`; daytime and senior leagues
   often play 6), shown as `[placeholder]`. A game file has exactly that many boxes. A league whose playoffs play more
   ends sets it per season only; a separate playoff number waits for a league that asks.
2. **Level after the last end.** Recommended: a tie in the regular season and extra ends in the playoffs
   (`extra_end: playoffs`, `ties: true`, both `[placeholder]`); option `always` for leagues that play an extra end in
   every game. An extra-end win counts as a full win (2 points). Trade-off: leagues that never allow ties must set
   two settings (`extra_end: always`, `ties: false`).
3. **Standings points and columns.** Recommended: 2 for a win, 1 for a tie, 0 for a loss, ranked by points, columns
   GP W L T PTS PF PA (the approved Curling-Home table). Team stats (stolen ends...) are not columns by default, to
   keep the table narrow at 360 px; a league can add them.
4. **Tiebreakers.** Recommended: head-to-head, then points difference (my reading of `BRIEF.md`'s "points for and
   against"), `[placeholder]`. Alternatives a league can set: `points_for`, or `periods_won` (ends won in the
   scheduled ends; an extra end is not counted there, though it is in the "Ends won" board). A last-stone draw total,
   common in competitive curling, is not on a score card and is not supported.
5. **Forfeit score.** Recommended: 1-0, `[placeholder]`, so a forfeit barely moves the points difference that breaks
   ties. Alternative: 8-0 (or `per_period`: 1-0 in every end), which rewards the rink that showed up more and also
   counts 8 ends won.
6. **Hammer.** Recommended: the LSFE box is required in a finished file; every later hammer is worked out. Without it
   there are no stolen ends, the marks in the line score or the numbers block. Trade-off: a league whose cards never
   note it must start doing so (the alternative, an option to leave hammer out and hide those stats, is the deferred
   "stats shown only when an option is on").
7. **Concessions and time.** Recommended: a rink may shake hands after any complete end; it must be behind; the score
   stands and the ends left show X; it counts as a normal win and loss. A game may also stop when time is called
   (`time_called`), with the same X marks and a tie if level. No minimum number of ends before conceding.
8. **Lineups and positions.** Recommended: lineups recorded per game (`lineups: recorded`; `none` for a league whose
   cards have no names), 3 or 4 players in throwing order, positions lead, second, vice, skip, the label "Vice" (the
   third). Trade-off with `none`: no games played, no lineups block, and the Stats page's player list stays on its
   empty-state line.
9. **Player stats.** Recommended: games played and position only, no player leaderboards (`BRIEF.md`). Alternative:
   games as a spare, or games at each position (one counting stat each).
10. **Team stats and boards.** Recommended: ends won, stolen, blank, big (3+), ends with hammer and scored with hammer
    per game and per season; boards Stolen ends and Ends won (tiles) and Big ends (list), as counts with "in 7 games".
    The approved mockup's "Ends won 50%" needs team rates (a core change): later, if wanted. "Scored with hammer"
    counts any score, not the analysts' 2+ "hammer efficiency".
11. **How the line score shows things.** Recommended, as the approved design: a stolen end tinted and framed with the
    hidden words "stolen end"; a blank end's column shaded; X for an end not played; the hammer marker in each end
    (full size) and after the rink with the hammer in end 1 (cards); extra ends as `EE` columns. The club-scoreboard
    style (`BRIEF.md`'s option) waits for a specimen.
12. **Schedule words.** Recommended: "Draw 7" for a league night, as the mockup (strictly, a draw is one start time:
    an evening with a 6:30 and an 8:45 draw is one "Draw 7" here); sheets as letters in `schedule.csv` (`A`), shown
    as "Sheet A" and on the letter tiles; a blank sheet column shows no tile.
13. **Rink names.** Clubs often name a rink after its skip ("Team Smith"), which puts a surname on every page.
    Recommended: the README and `docs/data.md` say to use a made-up name or "Gail R.'s rink", as the "First L." rule
    requires; the build does not try to detect surnames.

## Risks

- **Real cards differ.** Some cards are scoreboard style, some mark the hammer in every end, some have no names. The
  file format is fixed now and stage 7's entry page and photo prompt will have to translate into it; decisions 6, 8
  and 11 are where a league is most likely to push back.
- **Rules I could get wrong.** The hammer rule (a blank keeps it) is standard for four-player curling but not for
  every format (mixed doubles passes it on a blank); concession and time-limit customs vary by club. All are in the
  README and the fixtures, so a change is one rule and a fixture rewrite.
- **Shared code in a sport PR.** E7-E11 touch the core, the stub and basketball golden files, `make_sample.py` and the
  contract test. Package 1 gets its own Opus review, and the committed basketball sample must stay byte for byte the
  same.
- **Two "ends won" numbers.** The core's EW column and `periods_won` tiebreaker count scheduled ends; the curling team
  stat counts extra ends too. They differ only after an extra end, and the README says so; making them agree means
  changing the core's period count for every sport.
- **Deploy time.** `/curling/` adds a sport preview (about 10 seconds and 2-3 MB per deploy, from basketball's
  measured numbers), as decided for sport previews.
