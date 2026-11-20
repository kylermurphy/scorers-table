# Stage 5, part 3: hockey

Status: **draft for the owner's review**. Nothing is built yet. Section 10 lists the decisions: until one is
answered, the build follows the recommendation, and every rule a league decides shows as `[placeholder]`.
Hockey is new (the Masters site is basketball only), so the references are `BRIEF.md` ("Hockey (old-timers / rec,
non-contact)"), the approved hockey mockups (Hockey-Home, Classic-Hockey-Home, Hockey-Game) and the hockey specimens
on the design-system page (`scripts/design_system/sample.py`, Northside Old-Timers Hockey).

Read first: `BRIEF.md`, `docs/stage-4-spec.md` section 3 (the sport interface), `docs/stage-5-curling-spec.md` (the
model for this document), `docs/stage-5-basketball-spec.md` section 5 ("Deferred": `order: asc`, `format:`),
`docs/sports.md` (what the code does today), `docs/design.md` (the hockey look, the event log).

Hockey words used here: a game has three **periods**; a tied game may go to **overtime** (OT, usually sudden death:
the first goal wins) and then a **shootout** (SO: shooters one at a time against the goalie). A goal may have up to
two **assists**; goals plus assists are **points** (PTS). A **penalty** sends a player to the box for a number of
**penalty minutes** (PIM): 2 for a minor, 4 for a double minor, 5 for a major, 10 for a misconduct. While a team is a
player short, the other team is on the **power play** (a goal then is a PP goal; one scored by the short team is
**short-handed**, SH). An **empty-net** goal (EN) is scored while the goalie is pulled. The **game-winning goal**
(GWG) is the goal that puts the winner one ahead of the loser's final total. For goalies: **goals against** (GA),
**goals-against average** (GAA, lower is better), **save percentage** (SV%), and a **shutout** (no goals against).
Pages write shutouts as **SHO**, because **SO** already means shootout in the line score and "Final · SO".

---

## 1. Scope

**In this pull request**

| What | Where |
|---|---|
| The hockey sport folder | `sports/hockey/`: `sport.yml`, `rules.py` (`check`, `read`, `present`, `derive`), `sample.py`, `README.md` (the game sheet box by box, for the volunteer) |
| Shared test files | `sports/hockey/fixtures/`: one game per case with the expected problems and numbers (section 8), for the stage 7 JavaScript port |
| Three new display parts | `events` (the scoring summary), `penalties` (the penalty table) and `group` (a titled group of game tables), plus three small `stat_table` options for the goalie and skater tables (section 6, E16-E18) |
| Core extensions | leaderboard `order: asc`, a `format:` for rates, more than one stat group on every page, leaderboard columns, the shootout sub line (section 6, E12-E15, E19) |
| Sample seasons | two made-up hockey seasons for the golden files, the `/hockey/` sport preview and its landing card (section 7) |
| Docs | `docs/sports.md`, `docs/open-questions.md` (hockey's placeholders and section 10), `README.md` (`/hockey/`), `CLAUDE.md`, `PLAN.md` status, `landing.yml` (hockey off `coming_soon`) |

**Not in this pull request**

- The JavaScript copy of the rules and the entry page: stage 7. The fixtures are written now so the port can be
  tested against them.
- A printable hockey game sheet and the photo-reading prompt: later (`PLAN.md`).
- Slo-pitch (its own pull request), and the `facts` block it needs.
- Three stars, team shots on goal by period, faceoffs, plus-minus, goalie minutes played: not on a typical rec sheet,
  or not wanted (decisions 10 and 15).
- Six layouts per sport and the screenshot sweep: stage 6. This PR screenshots the hockey sample in the Hockey layout
  only. The shipped `league.yml` stays `sport: basketball`; the committed `data/sample-*` stay basketball.

## 2. The game file

### 2.1 What a rec game sheet holds, and how it maps

A rec hockey game sheet (the referee's or scorekeeper's copy) has: the date, rink and pad; each team's roster with
jersey numbers, the goalie marked; a scoring summary (period, time, goal by number, up to two assists by number,
often a PP/SH/EN mark); a penalty list (period, time, number, infraction, minutes); the goalies with their goals
against (and on some sheets shots against); the score by period with OT and SO boxes and a total; signatures. The game
file copies that, box for box, in the core envelope (`docs/data.md`) with the sport's part under `sheet:`.

| On the sheet | In the file | Notes |
|---|---|---|
| date, time, rink, pad | the schedule row (`schedule.csv`: `date`, `time`, `venue`, `surface` = `1`) | the core's, as for every sport |
| the two teams | the envelope's `home` and `away` | "home" is the first-listed team; pages say "vs" |
| scorekeeper, notes | the envelope (`scorekeeper`, `checked_by`, `notes`) | referees' names are not copied (privacy, and no page needs them) |
| a forfeit | the envelope's `forfeit: <team id>`, no `sheet` | the core's |
| roster rows | `sheet.roster.<side>`: `{player, num}` per row, top to bottom | who dressed; a goalie is a roster row too |
| scoring summary | `sheet.goals`: one list in the order written, each `{period, time, side, num, assists, strength, en, ps}` | numbers, as on the sheet; the roster turns them into players |
| penalties | `sheet.penalties`: `{period, time, side, num, infraction, minutes}` | `num: bench` for a bench penalty |
| goalies | `sheet.goalies.<side>`: `{num, ga, shots, decision}` per goalie who played | `shots` only when `rules.goalie_shots` is `recorded` (decision 10) |
| shootout | `sheet.shootout`: `{first, home: [...], away: [...]}`, each attempt `{num, scored}` | only after a level overtime (decision 4) |
| score by period | `sheet.score.<side>`: `{periods: [..], ot, so, final}` | the boxes as written; they must agree with the goals |

### 2.2 Example

The approved Hockey-Game mockup as a file (Blades 5, Wolves 3, Week 8, Pad 1). Times are time elapsed in the period
(decision 14) and must be **in quotes**: unquoted, `4:12` is read by Python's YAML reader as the number 252.

```yaml
game_id: 2026-11-29-1          # the core envelope: unchanged for every sport
status: final
home: blades
away: wolves
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  roster:                      # who dressed, top to bottom; num is the jersey number written on the sheet
    home:
      - {player: len-t, num: 31}           # the goalie is a roster row; `goalies` below says who played in net
      - {player: barry-s, num: 4}
      - {player: terry-w, num: 6}
      - {player: doug-h, num: 8}
      - {player: gord-p, num: 12}
      - {player: ken-l, num: 17}
      - {player: al-f, num: 22}
    away:
      - {player: murray-b, num: 1}
      - {player: phil-a, num: 2}
      - {player: wayne-k, num: 9}
      - {player: gary-n, num: 11}
      - {player: rod-b, num: 14}
      - {player: bob-c, num: 21}
  goals:                       # the scoring summary, in the order written
    - {period: 1, time: "4:12", side: home, num: 12, assists: [4, 17]}
    - {period: 1, time: "9:38", side: away, num: 9, assists: [14]}
    - {period: 1, time: "13:05", side: home, num: 17, assists: [12]}
    - {period: 2, time: "2:47", side: away, num: 14, assists: [9, 2]}
    - {period: 2, time: "7:20", side: home, num: 8, assists: [22]}
    - {period: 2, time: "11:54", side: away, num: 9}                  # unassisted: no assists line
    - {period: 3, time: "5:31", side: home, num: 12, assists: [4]}    # the GWG is worked out, never written
    - {period: 3, time: "12:09", side: home, num: 4, assists: [12, 6]}
  penalties:
    - {period: 1, time: "12:15", side: away, num: 21, infraction: Tripping, minutes: 2}
    - {period: 2, time: "9:02", side: home, num: 22, infraction: Hooking, minutes: 2}
    - {period: 3, time: "8:44", side: away, num: 11, infraction: Slashing, minutes: 2}
    - {period: 3, time: "14:10", side: home, num: 8, infraction: Body contact, minutes: 2}
  goalies:
    home: [{num: 31, ga: 3}]
    away: [{num: 1, ga: 5}]
  score:                       # the "score by periods" boxes; ot and so stay empty when not played
    home: {periods: [2, 1, 2], ot: ~, so: ~, final: 5}
    away: {periods: [1, 2, 0], ot: ~, so: ~, final: 3}
```

The other marks, and a game decided in a shootout (only the changed boxes shown):

```yaml
  goals:
    - {period: 2, time: "6:40", side: away, num: 9, assists: [14], strength: PP}   # power play
    - {period: 3, time: "1:15", side: home, num: 17, strength: SH}                # short-handed
    - {period: 3, time: "14:30", side: home, num: 12, en: true}                   # into an empty net
    - {period: 2, time: "3:02", side: away, num: 11, ps: true}                    # penalty shot: never assisted
  penalties:
    - {period: 2, time: "5:10", side: home, num: bench, served_by: 6, infraction: Too many players, minutes: 2}
---
  score:                       # 2-2 after three, a scoreless OT, home wins the shootout 2-1
    home: {periods: [1, 0, 1], ot: 0, so: 1, final: 3}
    away: {periods: [0, 2, 0], ot: 0, so: 0, final: 2}
  shootout:
    first: home                # who shot first (it decides when a shootout can stop early)
    home: [{num: 12, scored: true}, {num: 9, scored: false}, {num: 4, scored: true}]
    away: [{num: 9, scored: false}, {num: 14, scored: true}, {num: 2, scored: false}]
```

In a draft (`drafts/`) any box may be left empty (`~`), and a roster row may be `{name: Jo K., num: 30}` (a spare
written in by hand, no player id yet), as basketball and curling allow.

### 2.3 Why this shape

- **Numbers, not names, in goals and penalties.** The sheet writes "#12, assists #4 #17"; copying the numbers keeps
  the file a copy of the paper, and one roster row turns a number into a player. A number that is not on the roster
  is a mistake the check can point at.
- **One goal list for both teams**, in the order written, as most sheets have one scoring summary. A sheet with a
  summary per team is copied into it by the volunteer (or in stage 7 by the entry page).
- **The score boxes are copied too**, although the goals already give the score: two records that must agree catch
  a missed or extra goal line, as basketball's quarter boxes do.
- **The GWG, the running score and each goalie's decision with one goalie are worked out**, never written, so they
  cannot disagree with the goals.

### 2.4 Paths

Paths are relative to `sheet` in `check` (the core adds `sheet.`), counting from 0 as every sport does: `goals.6` is
the seventh goal line. The README says so with a picture of the boxes.

| Path (after the core adds `sheet.`) | The box |
|---|---|
| `sheet.roster.home.4` (`.player`, `.num`, `.name`) | the fifth roster row of the home team |
| `sheet.goals.6` (`.period`, `.time`, `.side`, `.num`, `.assists.1`, `.strength`, `.en`, `.ps`) | the seventh goal line |
| `sheet.penalties.2` (`.period`, `.time`, `.side`, `.num`, `.served_by`, `.infraction`, `.minutes`) | the third penalty line |
| `sheet.goalies.away.0` (`.num`, `.ga`, `.shots`, `.decision`) | the away team's first goalie row |
| `sheet.shootout.first`, `sheet.shootout.home.2` (`.num`, `.scored`) | the home team's third shootout attempt |
| `sheet.score.home.periods.1`, `.ot`, `.so`, `.final` | the home team's score boxes (`final` is `Score.final_at`) |

## 3. The rules in Python

### 3.1 Checks

"Gap" means an error in `games/` and a warning in `drafts/` (the core rule for empty boxes). `check` never raises,
returns every problem, and stops a branch when a problem makes later checks meaningless (no `roster`: no number
lookups; no `score`: no score checks). Numbers below are the options' defaults (section 5.3).

| Check (path relative to `sheet`) | Level |
|---|---|
| a key other than `roster goals penalties goalies shootout score` (`<key>`) | error |
| `roster`, `roster.<side>` missing; `goals`, `penalties` may be left out (none) | gap |
| `roster.<side>` not a list of 1 to 25 rows | error |
| `roster.<side>.<i>` not a row; an unknown key | error |
| `.num` missing, not 0 to 99 or `"00"`, or twice on one side | error |
| `.player` missing (only a `name`: a spare not yet in `players.yml`) | gap |
| `.player` not in `players.yml`; listed twice in the game | error |
| `.player` on another team and not `sub: true` | warning |
| `goals.<i>` not a row; an unknown key | error |
| `.period` not 1 to `rules.periods`, `OT`, or `OT2`, `OT3`... (playoff sudden death) | error |
| `.time` missing | gap |
| `.time` not text like `"4:12"` (a number: "put the time in quotes") or past the period's length (`period_minutes`; `overtime_minutes` in OT) | error |
| `.time` out of order with the line before in the same period (with the league's clock direction) | warning |
| `.side` not `home` or `away`; `.num` not on that side's roster | error |
| `.assists` not a list of at most 2 numbers; a number not on the scorer's roster; the scorer or the same player twice | error |
| `.strength` not `EV`, `PP` or `SH`; `.en`, `.ps` not `true` | error |
| `.ps: true` with assists (a penalty shot is never assisted) | error |
| `.strength: PP` and the other team has no penalty in this period or the one before; `SH` and this team has none ("check the strength mark") | warning |
| a player with more goals than `rules.goal_cap` (when set) | warning |
| `penalties.<i>` not a row; an unknown key; `.period`, `.time`, `.side` as for goals | error / gap |
| `.num` not on the roster and not `bench`; `.served_by` set without `bench`, or not on the roster | error |
| `.infraction` missing | gap |
| `.infraction` not text | error |
| `.minutes` not a whole number from 1 to 20 | error |
| `.minutes` not 2, 4, 5 or 10 ("unusual: check the sheet") | warning |
| `goalies`, `goalies.<side>` missing | gap |
| `goalies.<side>` not a list of 1 or 2 rows; an unknown key | error |
| `.num` not on that side's roster, or twice | error |
| `.ga` missing | gap |
| `.ga` not a whole number from 0 | error |
| the goalies' `ga` together not the other team's goals in periods and OT, empty-net goals left out ("the GA boxes add up to 4, but Wolves scored 5, none into an empty net") | error |
| `.shots` set when `rules.goalie_shots` is `none` | error |
| `.shots` missing when it is `recorded` | gap |
| `.shots` less than `.ga` | error |
| two goalies for a side and not exactly one `decision: true` ("who gets the win or loss?") | error |
| `decision` on a side with one goalie | warning |
| `score`, `score.<side>`, `.periods`, `.final` missing | gap |
| `.periods` not a list of `rules.periods` whole numbers | error |
| `.periods.<i>` not the side's goals in that period ("the box says 2, the goal lines have 1") | error |
| `.ot` filled although regulation was not level, or the league plays no overtime in this kind of game | error |
| `.ot` empty although regulation was level and overtime is played here ("write 0 for a scoreless overtime") | error |
| `.ot` not the side's goals in OT; more than one OT goal in all (sudden death) | error |
| `shootout` or `.so` filled although the game was not level after OT, or the league plays no shootout here | error |
| `shootout`, `.so` missing although it was level after OT and a shootout is played here | error |
| `shootout.first` not `home` or `away`; an attempt not a row, `.num` not on the roster, `.scored` not true/false | error |
| `shootout`: level at the end ("a shootout ends with a winner") | error |
| `shootout`: attempts that do not fit `rules.shootout_rounds` (a round missing, or shots after it was decided) | warning |
| `.so` not 1 for the shootout winner and 0 for the other | error |
| `.final` not a whole number, or not the periods plus OT plus SO | error |

The core then adds, at `Score.final_at` (`sheet.score.<side>.final`): a tied playoff game, and a tied regular-season
game when `standings.ties` is false.

### 3.2 How the numbers come from the sheet (`read`)

Goals are first put in time order within each period (with the clock direction), so the running score and the GWG
follow the game, not the order of the lines.

| Number | From |
|---|---|
| `Score.periods` | the goals per regulation period |
| `Score.extra` | `[OT goals]` when overtime was played, `[OT goals, SO]` after a shootout (SO 1-0) |
| `Score.final` | periods + OT + SO (the Final box must agree); a shootout win adds one goal (decision 4) |
| `decided_in` | `overtime` for an OT goal, `shootout` after a shootout, else `regulation` |
| skater line (group `skater`) | every roster row with a player id that is not a goalie who played: GP 1, `g`, `a`, `pts` (= g + a), `pim`, `ppg`, `shg`, `gwg` |
| goalie line (group `goalie`) | each goalie row: GP 1, `ga`, `sa` (shots, when recorded), `w` `l` `t` `otl` for the goalie of record (the only goalie, or the one with `decision`), `sho` (decision 13), and the goalie's own `a` and `pim` |
| GWG | the winner's goal number (loser's final + 1), in time order, OT included; none after a tie or a shootout |
| PIM | the penalty's minutes to the player; a bench penalty counts to nobody (the team total in the foot includes it) |
| shootout goals | no player goal, no point, no goalie GA (decision 4) |
| `facts` | the goals in time order (player ids, assists, running score, strength, GWG flag), the penalties, the goalies, the shootout attempts, `periods`, the clock direction, per-team PIM |

A goalie's `w`, `l`, `t` and `otl` come from the `Score` that `read` itself built, so they cannot disagree with the
standings; the standings points themselves stay the core's.

`derive(counts, group)`: for `goalie`, `gaa` = GA / GP (unrounded; `None` with no games) and `sv_pct` = (SA - GA) / SA
(`None` when no shots were recorded); for `skater`, `{}`. GAA per game played, not per 60 minutes: rec sheets do not
record minutes in net (decision 10).

### 3.3 Overtime, shootouts, ties, forfeits

- **Regular season, level after regulation** (`rules.overtime`, decision 2): `none` (the default) leaves a tie;
  `overtime` plays one sudden-death OT and leaves a tie if nobody scores; `shootout` plays the OT and then a shootout;
  `shootout_only` goes straight to the shootout (the OT box stays empty).
- **Playoffs, level after regulation** (`rules.playoff_overtime`, decision 5): `sudden_death` (the default) plays
  OT periods until a goal (`OT`, `OT2`...; one OT box holds the total); `shootout` plays one OT and then a shootout.
- **Results**: an OT or shootout win is the core's `ot_win`, the loss `ot_loss`. With the sport's defaults both
  count as a win and a loss (2 and 0 points); a league that plays overtime sets `ot_loss: 1` (decision 6). The
  final panel says "Final · OT" or "Final · SO" (the core's words today).
- **Ties**: the core's `standings.ties` (default `true`, `[placeholder]`).
- **Games cut short** (ice time ran out, a mercy rule): the score stands; the volunteer writes a note in the
  envelope's `notes`. No special key (decision 17).
- **A forfeit** is the core's (`forfeit: <team id>`, no sheet): no player gets a game, no goalie a decision. Its score
  is `standings.forfeit` (decision 8).

## 4. Standings

### 4.1 Defaults (`sport.yml`)

```yaml
standings:
  rank_by: points
  points: {win: 2, tie: 1, loss: 0}                      # BRIEF: 2 for a win, 1 for a tie; ot_win/ot_loss = win/loss
  period_points: 0
  ties: {value: true, decide: true}                      # decision 2
  forfeit: {value: {score: [1, 0]}, decide: true}        # decision 8
  tiebreakers: {value: [wins, head_to_head, diff], decide: true}   # BRIEF: wins, head-to-head, goal difference
  columns: [gp, w, l, t, pts, pf, pa]                    # the approved Hockey-Home table: GP W L T PTS GF GA
```

`words.points_for` is `{label: GF, title: Goals for}` and `points_against` `{label: GA, title: Goals against}`. The
README gives the lines for the common variants: overtime with a loser point (`overtime: shootout`, `points: {ot_loss:
1}`, columns `[gp, w, l, otl, pts, pf, pa]`, `ties: false`), and a goal-difference cap (`tiebreakers: [wins,
head_to_head, {diff: {cap: 5}}]`) for a league with a mercy rule.

## 5. Stats and pages

### 5.1 Two stat groups

`BRIEF.md`: skaters GP, G, A, PTS, PIM; goalies GP, GA, GAA, shutouts, record. So `stats` has two groups:

| Group | Counting | Rates (`derived`, with `group:`, E14) | Stats table | Player totals | Game log |
|---|---|---|---|---|---|
| `skater` | `g` G, `a` A, `pts` PTS, `pim` PIM, `ppg` PPG, `shg` SHG, `gwg` GWG | none | GP G A PTS PIM | GP G A PTS PIM PPG SHG GWG | G A PTS PIM |
| `goalie` | `w` W, `l` L, `t` T, `otl` OTL, `ga` GA, `sa` SA, `sho` SHO, `a` A, `pim` PIM | `gaa` GAA (2 places), `sv_pct` SV% (3 places, `format: dot`: ".912") | GP W L T GA GAA SHO (SV% when shots are recorded) | the same + OTL, A, PIM | GA, SV%, result |

PPG here is power-play goals (not points per game); its title says so. Columns a league never uses disappear by
themselves: a rate nobody has a value for (SV% without shots) is left out of every list (core rule today), and the
README shows how to drop OTL or T with `stats.columns`.

### 5.2 Leaderboards

| Board | Group, stat | Order | Tile | Home | Detail | Notes |
|---|---|---|---|---|---|---|
| Points | skater `pts` | desc | no | yes | "{gp} GP" | columns G, A, PTS: the Hockey layout's table with round rank chips (E15) |
| Goals | skater `g` | desc | no | no | "{gp} GP" | |
| Assists | skater `a` | desc | no | no | "{gp} GP" | |
| Penalty minutes | skater `pim` | desc | no | no | "{gp} GP" | `playoffs: true`, `player_rank: false` (as basketball's technicals) |
| Goals-against avg | goalie `gaa` | **asc** | yes, accent | yes | "{ga} GA in {gp} GP" | `zero: true` (0.00 is the best), min `goalie_min_games` |
| Shutouts | goalie `sho` | desc | yes, hot | yes | "{gp} GP" | |
| Save % | goalie `sv_pct` | desc | no | no | "{sa} shots, {gp} GP" | `zero: true`, min `goalie_min_games`; empty (so hidden) without shots |

`minimums.goalie_min_games`: default 4 (the approved mockup's "Goalies need 4 games played to rank."), `decide: true`,
`cap_at_team_games: true`, note "Goalies need {value} games played to rank." The goalie tiles sit under a
"Goalies" label (the board's `group_label`, from `stats.labels`, E14).

### 5.3 Options (`sport.yml`)

| Option | Type, default | Decide | Used for |
|---|---|---|---|
| `periods` | int 2 to 4, 3 | yes | score boxes, `line_score.periods` (a forfeit's `per_period`) |
| `period_minutes` | int 5 to 30, 15 | yes | the time check |
| `overtime` | choice `none overtime shootout shootout_only`, `none` | yes | regular season (3.3) |
| `playoff_overtime` | choice `sudden_death shootout`, `sudden_death` | yes | playoffs (3.3) |
| `overtime_minutes` | int 1 to 20, 5 | yes | the time check in OT |
| `shootout_rounds` | int 1 to 5, 3 | yes | the shootout warning |
| `clock` | choice `elapsed remaining`, `elapsed` | yes | time order, the GWG, the event log's note |
| `goalie_shots` | choice `none recorded`, `none` | no | SA and SV% |
| `goal_cap` | int 0 to 10, 0 (no cap) | yes (`BRIEF.md`'s `[placeholder]`) | the warning |

Other `sport.yml` values: words period `{one: Period, many: Periods, short: P}`, day `Week`, surface `Pad`;
`line_score: {shape: periods, total_label: T, corner: Period, periods: periods}`; labels `results: Latest results`,
`next: Next game night`, `leaders: Leaders` (Classic: `Scoring leaders`, as the mockup); `display: {card: rows,
card_foot: status_note, surface: sub}` (the design-system contract's hockey hints); `positions: [forward, defence,
goalie]` (shown on the player page only; the game sheet, not the position, decides who was in net); `game_minutes: 75`;
`default_layout: hockey`; `blurb: Periods, goals and assists, penalties and goalies.` (the coming-soon card's line).

### 5.4 The game page (`present`)

| Block | Part | Content | Exists? |
|---|---|---|---|
| final panel | core `final-panel` | the rink panel, both teams, the big score; status "Final", "Final · OT", "Final · SO"; sub "Blades by 2", after a shootout "Blades won the shootout" (E19); foot (`split`): "Goalies: **#31 Len T.** · **#1 Murray B.**" and "PIM 4–4" | yes (the `split` foot is in the include and its parity case) |
| line score | core `line_score`, shape `periods` | corner "Period", columns `1 2 3`, `OT` when played, `SO` after a shootout (plain columns, as curling's `EE`), total "T"; no cell marks | yes |
| result card | core `card` (`rows`) | note "GWG **#12 Gord P.**", a tie "Tie", a shootout "Won in a shootout"; foot "Final · ..." (`status_note`); link "Game sheet" | yes |
| scoring | **new** `events` (E16) | "Scoring": a group per period played ("1st period", "2nd period", "3rd period", "Overtime", "Shootout") with its tally ("BLA 2 · WOL 1"); each goal: time, chip and code, scorer with a GWG badge, "Assists: #4 Barry S., #17 Ken L." or "Unassisted", PP/SH/EN/PS words after the scorer, the running score; a period with no goals says "No scoring"; shootout rows "Scored"/"Missed" with the shootout tally; note "Score shown Blades first. Times are time elapsed in the period." | specimen and CSS yes; include, empty-period state and parity no |
| penalties | **new** `penalties` (E17) | "Penalties": PER, TIME, PLAYER (name, chip, code; "Bench (served by #6 Terry W.)"), INFRACTION, MIN; the team legend below; left out when there were none | specimen and CSS yes; include and parity no |
| goalies | `group` (E18) + `stat_table` with `team_col` | "Goalies": Goalie, Team (chip + name), Result (W/L/T/OTL, bold), GA (big); + SA and SV% with shots; note "Both goalies played the full game." or "Wolves used two goalies; #1 Murray B. took the decision." | stat table yes; team column, cell styles, group and parity no |
| skaters | `group` (E18) + one `stat_table` per side with `heading: small` | "Skaters", intro "Players with a goal, assist or penalty.", per team a small heading and G, A, PTS (key), PIM with a Total row; a goalie with an assist or penalty is listed too | stat table yes; small heading and parity no |

The data comes only from the `Reading` (`facts`, `lines`) and `ctx.players`, as for every sport. No tiles (the
mockup has none).

### 5.5 The other pages

| Page | Hockey shows | Exists? |
|---|---|---|
| Home | next game night (face-off panel, "Pad 1" under the time), latest results, standings GP W L T PTS GF GA, "Leaders": the Points table and the two goalie tiles under "Goalies" | board columns are E15; the rest is core |
| Schedule | "Week 8", pads, cancelled and moved games, playoffs apart | yes |
| Stats | every board; "Skaters" and "Goalies" tables, each with its own columns | one table per group is E14 |
| Team | team card, roster as two tables (skaters, goalies), results, upcoming, calendar | E14 |
| Player | position line; Season totals per group, labelled when a player has both; Ranks; one game log per group | E14 |
| Archive season | as every sport | E14 |
| Landing card | "Hockey", the blurb, Northside Old-Timers Hockey, top three GP W L T PTS, the latest result | by itself (section 7) |

## 6. Core extensions

Checked against the code (`scripts/core/{sports,compute_stats,compute_games,fmt}.py`, `_includes/`, `stats/index.html`,
`_layouts/{player,team}.html`, `tests/parity/cases.py`). Numbered after curling's E5-E11. Each is generic (none
tests a sport id) and needed for the approved hockey pages. **Every existing sport's pages must stay byte-identical**:
the stub, basketball and curling golden files may change only by new JSON keys (read by eye), and
`tests/golden/landing/off-site.sha256` only for the new `/hockey/` pages and the other demos' banners.

| # | Extension | Needed because | Files | Tests |
|---|---|---|---|---|
| E12 | **Leaderboard `order: asc`** (lowest first; default `desc`). With `zero: true` a 0 ranks (0.00 GAA is first); `None` never ranks. The Stats table sorts its key column the same way, and a player's rank follows the board | GAA | `sports.py` (`_check_leaderboards`: `order` in `asc desc`), `compute_stats.py` (`_player_board` sort, `_table` order) | `test_sports.py` (schema); `test_build.py`: asc board with a 0.00 first, a `None` left out, ties sharing a rank, minimum applied, table order |
| E13 | **`format:` for a derived stat**: `dot` drops the leading zero (".912", "1.000", ".000"); default `decimal` (today's). Places as today | SV% (slo-pitch's average later) | `fmt.py` (`dot`), `sports.py` (`format` allowed with `places`), `compute_stats.py` (`_stat_block` display) | `test_fmt.py`; `test_sports.py`; golden unchanged |
| E14 | **More than one stat group on every page.** `stats.labels: {skater: Skaters, goalie: Goalies}` (a new reserved key; default the key in title case); a derived stat may name its `group:` (offered only to that group's columns and boards); `leaders.tables` (one per group, in `sport.yml` order; `leaders.table` stays the first, for compatibility); the Stats page and the team roster print one table per group, with a small group heading only when there are two or more; the player page labels each group's totals when the player has more than one; the game log takes `group` and prints one table per group; a board's `group_label` comes from `stats.labels` ("Goalies", as the mockup, not today's "Goalie") | goalies and skaters have different columns; today only the first group reaches the Stats and team pages, and the game log uses the first row's columns for every row | `sports.py` (schema), `compute_stats.py`, `stats/index.html`, `_layouts/{player,team,archive-season}.html`, `_includes/core/{player-table,stat-line,game-log}.html` | new `tests/test_stat_groups.py` (a two-group test sport in `tests/fixtures/sports/`: two tables, labels, a player in both groups with two logs, derived per group); one-group output unchanged (golden, off-site hash) |
| E15 | **Leaderboard `columns:`** (stat keys of the board's group): the core fills `board.columns` (with `key_col` on the board's stat) and each row's `cells` | the Hockey layout's Points table (G, A, PTS); the include and its parity case already draw it, but `_board` always sends `columns: null` | `sports.py`, `compute_stats.py` (`_board`, `_player_board`) | `test_build.py`; `test_jekyll.py` (hockey build: `.st-table--leaders` on Home in the Hockey layout, the list form elsewhere) |
| E16 | **`events` block**: `{type, title, groups: [{label, tally: [{side, n}], empty, events: [{time, side, player, name, badge, sub, score}]}], note}` | the scoring summary | `model.py` (`BLOCK_TYPES`), new `_includes/parts/events.html`, `parts/blocks.html`, `scripts/design_system/{contract.py,specimens_scores.py}` (the "No scoring" state; a `.st-events__empty` rule in `parts-scores.css` using `--st-muted` on `--st-surface`, an existing pair), `docs/design.md` | parity case `event-log` (remove it from `SKIPPED`; one template with the events and penalties includes) in all six layouts, light and dark; `check_contrast.py` passes, `docs/contrast.md` unchanged |
| E17 | **`penalties` block**: `{type, title, rows: [{period, time, side, player, text, infraction, minutes}], legend: [sides]}` (`player` a players.yml id, or `text` for a bench penalty) | the penalty table | `model.py`, new `_includes/parts/penalties.html`, `parts/blocks.html`, `contract.py`, `docs/design.md` | the same `event-log` parity case; Jekyll smoke: a past-season player is plain text |
| E18 | **Game table grouping**: a `group` block `{type, title, intro, note, blocks: [stat_table...]}` (one section head, children inside); on `stat_table`: `team_col: true` (rows carry `side`: chip + team name), a column's `style: strong` or `big` (`.st-table__strong`, `.st-table__big`), and `heading: small` (`h3.st-team-heading--sm`, no score) | the Goalies and Skaters sections of the mockup | `model.py`, new `_includes/parts/game-group.html`, `parts/stat-table.html`, `parts/blocks.html`, `contract.py` (`_hockey_blocks`), `tests/parity/cases.py` | a fragment case `game-tables-hockey`; the `game-tables` skip reason narrowed to slo-pitch; `game-tables-box` (basketball) unchanged |
| E19 | **The shootout sub line**: "Blades won the shootout" instead of "Blades by 1" when `decided_in` is `shootout` | "by 1" is wrong after a shootout | `compute_games.py` (`_final`) | `test_build.py`; golden unchanged |

**Considered and not built** (no approved page needs them, and an option no sample uses goes untested):

| Idea | Why not now |
|---|---|
| A points sentence that hides the OT parts when a league plays no OT | not needed while the sport's default `ot_loss` equals `loss` (decision 6) |
| A hockey tile on the game page (top scorer) | not in the mockup |
| Team stats (team PIM, PP goals) and team boards | not in `BRIEF.md`; per-game PIM is in the final panel foot |
| A goal-difference cap shown in the standings | the core's `{diff: {cap: n}}` tiebreaker already covers the usual mercy-rule rule |
| Period words by option ("Half" for two-period leagues) | still deferred (basketball halves); `periods: 2` keeps the word "Period" |

## 7. Sample data

`sports/hockey/sample.py`:

- `LEAGUE_NAME = "Northside Old-Timers Hockey"` (the made-up league of `BRIEF.md` and the design system).
- `TEAMS`: Blades BLA, Wolves WOL, Lumberjacks LUM, Ice Dogs ICE, Grey Owls OWL, Huskies HUS (the design system's six).
- `PLAYERS_PER_TEAM = 12` (11 skaters and a goalie; `BRIEF.md` says 12-15), `POSITIONS = ["goalie"]` (the first player
  of each team; the rest have no position), `SURFACES = ["1", "2", "1"]`, `TIMES = ["20:00", "20:00", "21:15"]`
  (Pad 1 and Pad 2 at 8:00, Pad 1 at 9:15, as the mockup's next game night). Jersey numbers on: the sheet's `num`
  comes from `players.yml`, and a player with none gets a free number on the sheet.
- `sheet(rng, game, ctx)`: the goalie is the team's goalie when dressed, else a spare in `game.players` (a spare
  goalie), else a skater. Draw goals per team (0 to 7, mostly 2 to 5) that honour the outcome; give each a period, a
  time in order, a scorer weighted toward a few top players, 0 to 2 assists; about one goal in six on a power play
  (after an opposing penalty in the same period), a few short-handed, an empty-net goal now and then late in a
  one-goal game; 2 to 6 minor penalties a game from a short list (tripping, hooking, slashing, holding, interference,
  body contact, high sticking), an occasional 5 or 10. The outcome bends to the rules: `ot` with `overtime: none`
  becomes a tie; a playoff game level after three goes to OT. Over a season the sample has at least one shutout, one
  OT win, one shootout, one game with two goalies for a team, a bench penalty and a penalty shot; `tests/test_hockey_sport.py`
  asserts each. In `drafts/`, one roster row is a `name:` only.
- **Options in the sample.** Both seasons build with the defaults, so `/hockey/` shows ties. A shootout needs
  `overtime: shootout`: the shared `data/seasons.yml` cannot give one sport its own option (as curling found), so
  playoff games show OT, and `test_hockey_sport.py` generates a season with `overtime: shootout` and `goalie_shots:
  recorded` and runs every check, golden-free. The contract test already runs the sample for every value of every
  `choice` option.

`scripts/make_sample.py` does the rest unchanged (round robin, a cancelled and a moved game, a forfeit, a tie, playoff
rows, one draft). One thing to check: its made-up name pool must hold 6 x 12 players plus the spares; package 4 says
so in a test, and grows the pool in `make_sample.py` (without changing the committed basketball sample) only if needed.

Golden files: `tests/golden/hockey/` (`SPORTS` in `test_golden.py` gains `hockey`), checked by hand once: standings,
the points and goalie boards, one OT game, one game with two goalies. The `/hockey/` sport preview appears by itself
(`sport_previews: true`), and so does its **landing card** (it has a `sample.py` and a `blurb`). Remove the hockey line
from `landing.yml` `coming_soon` in the same PR (the build warns until then), rewrite
`tests/golden/landing/landing.json` and `off-site.sha256` and read which pages their diffs name.

## 8. Tests

| Test | What |
|---|---|
| `sports/hockey/fixtures/` + `tests/test_hockey_fixtures.py` | the **shared fixtures**, in curling's format: `context.yml` (two made-up teams, Alpha and Bravo, a goalie and five skaters each with numbers, a spare goalie with `sub: true`, a player of a third team, default options) and per case `<name>.yml` (`fixture: {folder, game_type, options}` + `sheet:`) with `<name>.expected.json` (`problems` in order; `reading`: score, lines, facts, or `null`). `UPDATE_FIXTURES=1` rewrites them for review. Stage 7's Node runner reads the same files |
| fixture cases (about 70, one or more per row of 3.1) | `clean` (the mockup game), `tie`, `ot-win`, `ot-scoreless-tie`, `shootout-win`, `shootout-only`, `shootout-early-stop`, `shootout-level` (error), `shootout-round-missing` (warning), `playoff-sudden-death-ot2`, `playoff-shootout`, `ot-when-none`, `ot-missing`, `two-ot-goals`, `so-without-shootout`, `pp-goal`, `pp-without-penalty` (warning), `sh-goal`, `en-goal` (not in GA), `ps-goal`, `ps-with-assist`, `gwg-in-ot`, `gwg-out-of-order-lines`, `time-unquoted`, `time-past-period`, `time-out-of-order` (both clocks), `scorer-not-on-roster`, `assist-is-scorer`, `three-assists`, `bench-penalty`, `served-by-without-bench`, `odd-minutes` (warning), `two-goalies-decision`, `two-goalies-no-decision`, `goalie-not-on-roster`, `ga-mismatch`, `shots-recorded`, `shots-when-none`, `shots-below-ga`, `shutout`, `shared-shutout` (none credited), `goalie-assist`, `goal-cap` (warning), `period-box-wrong`, `final-wrong`, `periods-2`, `roster-dup-number`, `roster-00`, `spare-other-team` (warning), `draft-with-name`, `name-in-final`, `no-goalies` (game and draft), `unknown-keys`, `not-a-block`. A case that only Python can read (an unquoted time, which a JavaScript YAML reader keeps as text) is marked `python_only` in its fixture header |
| `tests/test_hockey_sport.py` | `read` and `present` against the design-system game (`_check_hockey_game`'s numbers: tallies, running score, GWG, goalie GA, skater lines, PIM foot); `derive` (GAA, SV% `None` without shots); the line score's OT and SO columns; `sample.sheet` honours every outcome under every `overtime` value; the season-level asserts of section 7 |
| `tests/test_sport_contract.py` | picks up the folder by itself (sample checks for every choice option, mutated sheets, paths, drafts never stricter) |
| `tests/test_golden.py` | `tests/golden/hockey/` beside `stub/`, `basketball/`, `curling/` |
| `tests/test_parity.py` | E16-E18: the `event-log` case and the `game-tables-hockey` fragment, light and dark; `leader-list` unchanged |
| `tests/test_jekyll.py` | a hockey build: a game page has `.st-events`, `.st-table--events`, the goalie and skater tables, the split foot; Home has `.st-table--leaders` and the "Goalies" tiles; Stats has two tables; a player with goalie and skater games has two logs; noindex on every preview page |
| `tests/test_landing.py` | the hockey card is live, no coming-soon hockey card, no warning |
| core tests | E12-E15 and E19 in `test_sports.py`, `test_build.py`, `test_fmt.py`, `test_stat_groups.py` |

## 9. Work packages

Packages 1, 2 and 3 start together (no shared file). Package 3 writes `check` and `read` against the interface in this
spec, and `sport.yml` and `present` once 1 and 2 are merged. Package 4 needs 1, 2 and 3. Package 5 finishes.
Shared files have one owner at a time: `sports.py` and the stub, basketball and curling golden files belong to 1;
`test_jekyll.py` to 2, then 4; `test_golden.py`, `tests/golden/hockey/` and `tests/golden/landing/` to 4.

| # | Package (Sonnet builds) | Owns | Done when |
|---|---|---|---|
| 1 | Core stats E12-E15, E19 | `scripts/core/{sports,compute_stats,compute_games,fmt}.py`, `stats/index.html`, `_layouts/{player,team,archive-season}.html`, `_includes/core/{player-table,stat-line,game-log}.html`, `tests/test_{sports,build,fmt,stat_groups}.py`, `tests/fixtures/sports/` (the two-group sport), `tests/golden/{stub,basketball,curling}/` | tests green; golden diffs only new keys (`leaders.tables`, board `order`), read by eye; the built pages of stub, basketball and curling byte-identical (compare `_site/` before and after) |
| 2 | Parts E16-E18 | `scripts/core/model.py`, `_includes/parts/{events,penalties,game-group,stat-table,blocks}.html`, `assets/css/parts-scores.css` (the empty-period line only), `scripts/design_system/{contract.py,specimens_scores.py}`, `tests/parity/`, `tests/test_parity.py`, `tests/test_jekyll.py` (block smoke), `docs/design.md` | parity green with `event-log` out of `SKIPPED` and `game-tables-hockey` added; `check_contrast.py` passes with `docs/contrast.md` unchanged; `build_css_fallbacks.py` run; `build_design_system.py` run |
| 3 | Hockey rules | `sports/hockey/{sport.yml,rules.py,README.md}`, `sports/hockey/fixtures/`, `tests/test_hockey_{fixtures,sport}.py` | every row of 3.1 has a fixture; the README lists every check with its path and level, the GWG and shutout rules, and the how-tos (overtime, a shootout, two goalies, a bench penalty, a penalty shot, a spare goalie, a game cut short, a forfeit) and the settings a league may change |
| 4 | Sample, golden, preview, landing | `sports/hockey/sample.py`, `scripts/make_sample.py` (the name pool, only if needed), `tests/test_golden.py`, `tests/golden/hockey/`, `tests/golden/landing/`, `tests/test_jekyll.py` (hockey smoke), `tests/test_landing.py`, `landing.yml` | contract test green; golden files reviewed by eye; the CI run publishes `/hockey/`, passes the link check (time per copy in the PR); screenshots at 390 px, light and dark, Hockey layout: Home, Schedule, a game (with OT, with two goalies), Stats, a team, a goalie's and a skater's page, the landing page |
| 5 | Docs | `docs/sports.md` (new keys, blocks, `order`, `format`, groups), `docs/open-questions.md` (section 8: hockey's placeholders and section 10), `docs/data.md` (the hockey how-tos it points to), `README.md` (`/hockey/`), `CLAUDE.md`, `PLAN.md` status | the docs say what the code does |

**Opus reviews:** package 1's interface (the new `sport.yml` keys and JSON shapes, and the byte-identical claim)
before 3 uses it; package 3 line by line (OT and shootout paths, the GA sum with empty-net goals, goalie decisions,
the GWG in time order, shutouts, PP/SH warnings, every path and level, the YAML time trap); the hockey golden
standings and boards by hand against the sample files (GAA ranked lowest first with the minimum); package 4's sample
for believability (rec scores, few PP goals, minor penalties, a spare goalie). Then the whole pull request.

## 10. Decisions for the owner

Each is **recommended, awaiting owner confirmation**. Until answered, the build follows the recommendation; every
rule a league decides also shows as `[placeholder]` until the league sets it.

1. **Periods and their length.** Recommended: 3 periods (`periods`, 2 to 4) of 15 minutes (`period_minutes`), both
   `[placeholder]`; the length only drives the time check. Trade-off: a two-half league keeps the word "Period"
   until period words by option exist.
2. **A game level after regulation in the regular season.** Recommended: a tie (`overtime: none`, `ties: true`), as
   `BRIEF.md` says; options `overtime`, `shootout`, `shootout_only`. Trade-off: a league with no ties must set two
   settings (`overtime: shootout`, `ties: false`).
3. **Overtime format.** Recommended: one sudden-death OT of 5 minutes (`overtime_minutes`). 3-on-3 or 4-on-4 is not
   on the sheet, so it is a line on the rules page, not a setting. Trade-off: a league playing a full OT where two
   goals can count gets an error; an option can come if one asks.
4. **Shootout scoring.** Recommended: 3 rounds then sudden death (`shootout_rounds`, `[placeholder]`); the winner gets
   one goal in the final score (3-2 SO), which counts in GF, GA and the difference, as scoreboards and the NHL show
   it; no player gets a goal or point and no goalie a GA; shutouts ignore the shootout. Trade-off: leaving the
   shootout goal out of GF needs a core change (the core reads a level final as a tie).
5. **A level playoff game.** Recommended: sudden-death OT periods until a goal (`playoff_overtime: sudden_death`);
   option one OT then a shootout. Trade-off: very long OT games are rare in rec hockey but possible with ice time
   limits; those leagues choose `shootout`.
6. **Standings points.** Recommended: 2 a win, 1 a tie, 0 a loss; an OT or shootout loss scores like a loss by
   default, and the README's overtime line adds `ot_loss: 1` (the "loser point"). Columns GP W L T PTS GF GA (the
   mockup); OTL is added by the overtime line. Trade-off: one more line for OT leagues, but a no-OT league's points
   sentence never mentions overtime.
7. **Tiebreakers.** Recommended: wins, then head-to-head, then goal difference (`BRIEF.md`), `[placeholder]`. A
   mercy-rule league can cap the difference (`{diff: {cap: 5}}`). Trade-off: head-to-head is skipped unless every
   tied pair has met (the core's rule).
8. **Forfeit score.** Recommended: 1-0, `[placeholder]`, so a forfeit barely moves goal difference. Alternative 5-0
   (common in adult leagues). Trade-off: 1-0 rewards the team that showed up least; it changes nothing but GF/GA.
9. **Assists.** Recommended: up to two per goal, as written; leaving them out is allowed (unassisted), so no option.
   Trade-off: a league that never records assists shows a column of zeros and an empty Assists board.
10. **Goalie stats.** Recommended: a GA box per goalie is required; GAA is GA per game played (rec sheets have no
    minutes in net); shots are optional (`goalie_shots: none`), and SV% and its board appear only when recorded; two
    goalies in a game each get a GP and the one marked `decision` gets the W/L. Trade-off: a goalie relieved early
    still gets a full game in GAA.
11. **Goalie minimum.** Recommended: 4 games to rank on GAA and SV% (`goalie_min_games`, the mockup's number, capped
    at the team's games), `[placeholder]`. Trade-off: early in the season the cap keeps the boards from being empty.
12. **Penalty minutes.** Recommended: PIM shown in the skater tables, the game page and a PIM board that is off Home
    and out of the "Ranks" line; infractions as free text; minutes 2, 4, 5, 10 (anything else a warning); bench
    penalties count to nobody. A penalty limit before ejection is not built. Trade-off: some leagues prefer not to
    show a PIM board at all (one line removes it).
13. **Strength marks and shutouts.** Recommended: PP, SH, EN and penalty-shot marks are optional per goal; PPG, SHG
    and GWG appear in a player's totals, not in the narrow tables. A shutout goes to a goalie who played the whole
    game alone and allowed no goal in periods or OT (empty-net goals included); a shared shutout is not credited.
14. **Clock direction.** Recommended: times are time elapsed in the period (`clock: elapsed`, as the mockup's 4:12,
    9:38, 13:05), `[placeholder]`; `remaining` for sheets that copy the scoreboard clock. Trade-off: a wrong setting
    only reverses the order warnings and could pick the wrong GWG, so the README asks the league to set it.
15. **Three stars.** Recommended: not built (rare on rec sheets, no mockup). Trade-off: a league that names stars
    can write them in the notes.
16. **Player goal cap.** Recommended: `goal_cap` (0 = none), `[placeholder]` as `BRIEF.md` asks, and a warning, not
    an error, when a player passes it. Trade-off: it sits in "Still to decide" for every league until set.
17. **Mercy rule and games cut short.** Recommended: the score stands as written, a note in `notes` says why, and no
    special display. Trade-off: the card does not say "called" unless the note is read on the game page.
18. **Lineups.** Recommended: the roster is required (games played come from it), with jersey numbers; a spare
    from another team is a warning unless `sub: true`. Trade-off: a sheet with no roster cannot give GP.
19. **Officials.** Recommended: referees' names are not copied into the file or shown. Trade-off: none that a page
    needs; a league can keep them on the paper sheet.

## Risks

- **Real sheets differ.** Some write time remaining, some list goals per team, some have no goalie GA box. The file
  format is fixed now and stage 7's entry page and photo prompt will translate into it; decisions 10 and 14 are
  where a league is most likely to push back.
- **Rules I could get wrong.** Shootout conventions (the +1 goal, shutouts after a shootout), the goalie of record in
  split games, and what counts as a shutout vary between the NHL and rec leagues. Each is one rule in `rules.py`, a
  README line and a fixture rewrite.
- **The YAML time trap.** Python's YAML reader turns an unquoted `4:12` into 252; a JavaScript reader keeps the text.
  The check catches it in Python, the entry page always writes quotes, and the one fixture that shows it is marked
  Python-only, so the stage 7 port is not asked to agree on it.
- **Shared code in a sport PR.** E14 touches the Stats, team, player and archive pages of every sport. Package 1 gets
  its own Opus review, and the stub, basketball and curling pages must be byte-identical (golden files, the
  off-site hash, a before-and-after `_site/` compare).
- **Penalty and goalie tables at 360 px.** Five penalty columns and up to six goalie columns: both scroll in their
  own box with the first column fixed, as the design system already does; screenshots in package 4 confirm it.
- **Deploy time.** `/hockey/` adds a sport preview (about 10 seconds and 2-3 MB per deploy, from basketball's
  measured numbers), and the landing page builds one more demo.
