# Adding a sport

For a developer. A sport is a folder, `sports/<id>/`, that says everything the core cannot know: how a score
sheet is laid out, how it is checked, which stats it has and how they are shown. The core (`scripts/core/`)
does the rest: loading the files, the standings, the pages, the calendars. There is no plugin framework. The
core lists `sports/*/sport.yml` to find sports, and loads `rules.py` and `sample.py` from the league's sport.

Read in this order: `sports/stub/` (a complete, tiny sport: copy it), then `sports/basketball/` (the first real
sport: its `README.md`, `sport.yml`, `rules.py`, `sample.py` and `fixtures/` show every part used for real) and
`sports/curling/` (the second: ends and a hammer, positions, no player stats, and its own two display blocks), then
this page, then `docs/stage-4-spec.md` section 3, `docs/stage-5-basketball-spec.md` and
`docs/stage-5-curling-spec.md` for the reasons. The code is the last word. Where it has moved on from the spec, [the end of this page](#where-the-code-differs-from-the-spec)
says so.

Three folders are in `sports/` today. **`basketball`** is the sport the template ships with (`sport: basketball`
in `league.yml`). **`curling`** is the second real sport; a league uses it by writing `sport: curling` in
`league.yml` (see [the curling README](../sports/curling/README.md)). **`stub`** is the core's test sport (two halves
and a Final box): the golden files in `tests/golden/stub/` and most core tests use it, and its `sport.yml` says
`demo: false`, so no sport preview is built for it. Hockey and slo-pitch follow, one pull request each.

- [The folder](#the-folder)
- [`sport.yml`](#sportyml)
- [`rules.py`: the four functions](#rulespy-the-four-functions)
- [What `present` returns](#what-present-returns)
- [What the core does for you: standings](#what-the-core-does-for-you-standings)
- [`sample.py`](#samplepy)
- [Sport previews](#sport-previews)
- [The contract test](#the-contract-test)
- [Checklist for a new sport](#checklist-for-a-new-sport)
- [Where the code differs from the spec](#where-the-code-differs-from-the-spec)

## The folder

| File | Required | What it is |
|---|---|---|
| `sport.yml` | yes | Everything declarative: words, periods, options, stats, leaderboards, standings defaults, display hints. Checked against a fixed schema (`scripts/core/sports.py`, `check_sport_spec`). |
| `rules.py` | yes | Four pure functions: `check`, `read`, `present`, `derive`. |
| `sample.py` | yes | `LEAGUE_NAME`, `TEAMS`, and one function that writes a believable sheet. |
| `README.md` | yes | The game file format, box by box, with the problem paths. This is the volunteer's reference (`docs/data.md` points to it). A missing one is a warning when the sport loads and a failure of the contract test. |
| `fixtures/` | stage 5 | Shared test files: `<name>.yml` plus `<name>.expected.json` (every problem `check` must return, and what `read` returns), one case per check. `tests/test_<id>_fixtures.py` runs them against `rules.py`; the JavaScript port will run the same files. Basketball and curling have them (`sports/basketball/fixtures/README.md`; curling's `README.md` is in `sports/curling/fixtures/`). To change a rule, change `rules.py` and rewrite the files: `UPDATE_FIXTURES=1 python -m pytest tests/test_<id>_fixtures.py`, then read the diff. |
| `rules.js` | stage 7 | The JavaScript port for the entry page. It moved from stage 5 to stage 7 with the entry page, its only user; each sport's pull request leaves its fixtures ready for it. |
| `convert_masters.py` | basketball only | A one-off converter: a Masters Basketball League data folder in, a scorers-table `data/` folder out. Not part of the contract; see [the basketball README](../sports/basketball/README.md). |
| `sheet.py`, a spec | later | The printable sheet. |

Nothing registers a sport. A folder with a `sport.yml` exists; a league uses it by writing `sport: <id>` in
`league.yml`. Only the league's sport is loaded for a build. The contract test loads every folder.

Where a sport's data lives: the game file is the envelope the core checks (`game_id`, `status`, `home`, `away`,
`checked_by`, `forfeit`, ...) plus one `sheet:` block that belongs to the sport. The core never looks inside
`sheet`; the sport's `check` does. Inside `sheet`, sides are always `home` and `away`, never team ids.

## `sport.yml`

Top-level keys. Unknown keys are errors, with a "did you mean".

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Shown as the default tagline ("Basketball"). |
| `default_layout` | yes | One of `basketball curling hockey slopitch classic scoreboard`. |
| `demo` | no (`true`) | `false` keeps the sport out of `sport_previews` (see [Sport previews](#sport-previews)). Only the stub says `false`. |
| `games_per_day` | no (1) | Games one team may play on one date. |
| `game_minutes` | no (60) | Default event length in the calendar files. |
| `words` | yes | See below. |
| `line_score` | yes | See below. |
| `options` | no | The settings `league.yml` `rules:` may set. |
| `standings` | yes | The typical-club standings rule; the same keys as `league.yml` `standings:`. |
| `stats` | yes | Counting stats by group, `derived` rates, `team` stats. |
| `minimums` | no | Leaderboard minimums a league may set. |
| `leaderboards` | no | In page order. |
| `labels`, `labels_by_layout` | no | Section names, and per-layout overrides. |
| `display` | no | Hints for core parts. |
| `positions` | no | Allowed `players.yml` positions (curling: `lead second vice skip`). |

### `words`

| Key | Meaning |
|---|---|
| `period` | `{one: Half, many: Halves, short: H}`. The column labels are `H1`, `H2`. Required. |
| `day` | "Week" in "Week 3", or "Draw". Required. |
| `surface` | "Court", "Sheet", "Diamond", "Pad". Leave it out (or `""`) when the sport has none. |
| `extra` | **Optional.** What play after regulation is called: `{one: Extra end, short: EE}`. Without it the core says "OT". With it: the final status reads "Final · EE", a game log row "Win (EE)", the points sentence "1 for an extra-end loss" (`one`, lower-cased and hyphenated), and the `periods_won` tiebreaker says "ends won" (the period's `many`) instead of "periods won". A shootout is still "SO". |
| `points_for`, `points_against` | `{label: PF, title: Points for}`. Required. |

### `line_score`

```yaml
line_score: {shape: periods, total_label: Final, corner: Team, periods: periods}
```

| Key | Meaning |
|---|---|
| `shape` | `quarters`, `ends`, `periods` or `innings`. Picks the line-score layout. |
| `total_label`, `corner` | The text of the total column and the top-left corner. |
| `periods` | **Optional.** How many regulation periods a game has: a number (`4`), or the name of an `int` option (`periods`), whose value in the league's rules is used. The core needs it to score a `forfeit: {score: per_period}` (1-0 in every period). Without it, `per_period` cannot be computed. |

### `options`

What a league may set under `rules:`. Each option has a key (lower-case, like `run_limit`) and:

| Key | Meaning |
|---|---|
| `type` | `int`, `bool`, `choice` or `text`. Required. |
| `default` | Required. Must itself pass the option's own checks. |
| `min`, `max` | `int` only. |
| `values` | `choice` only: the allowed values. |
| `decide` | `true` if this is a rule the league decides. Left out of `league.yml`, it shows as `[placeholder]` on the site and in "Still to decide". |
| `label` | The words for it in "Still to decide" ("Overtime"). Without one, the key is turned into words. |

`ctx.options` in `rules.py` is these after defaults and the season's `overrides:`.

### `standings`

The sport's usual rule. A key may be wrapped to mark it as the league's to decide:

```yaml
forfeit: {value: {score: [1, 0]}, decide: true}
tiebreakers: {value: [head_to_head, diff, points_for], decide: true}
```

The keys are `rank_by`, `points`, `period_points`, `ties`, `forfeit`, `tiebreakers`, `columns` and `playoffs`
([next section](#what-the-core-does-for-you-standings)). A `columns` entry may be any engine column or a key
of the sport's `stats.team`.

### `stats`

```yaml
stats:
  player:                                    # a group of counting stats; Line.counts uses these keys
    - {key: pts, label: PTS, title: Points}
  derived:                                   # rates, from rules.derive()
    - {key: ppg, label: PPG, title: Points per game, places: 1}
  team: []                                   # team counting stats (Reading.team_lines)
```

* Any group name other than `derived`, `team` and `columns` is a group of player counting stats. Most sports
  have one, `player`; hockey has `skater` and `goalie`. A group may have **no counting stats**: curling writes
  `player: []` (`derived: []`) and `columns: {player: {table: [gp], totals: [gp]}}`. The core still counts `gp` from
  the lineups, so the Stats page lists every player with GP, a player page shows GP, the game log has no stat
  columns, and there are no player leaderboards. Its `read` still returns a `Line` with `counts={}` for each player in a lineup, which is how GP is counted.
* Keys are lower-case words. `gp` (games played) is reserved: the core counts it, so a sport never lists it.
* `places` (0 to 4) is the number of decimals of a derived stat. `derive` may return the rate unrounded: the
  core rounds it half up to `places` for `totals` and the pages, and ranks the leaderboards on the exact value,
  so 20.14 is ahead of 20.06 although both show 20.1. (A `derive` that rounds itself, like the stub's, ranks on
  what it returned.)
* `columns` (optional) sets the columns and their order for each group, in three places:

  ```yaml
  stats:
    columns:
      player:
        table:  [gp, pts, ppg, ftm, fta, ft_pct]   # the Stats page and the roster tables
        totals: [gp, pts, ppg, ftm, fta, ft_pct, tech]   # a player's Season / Playoffs rows
        log:    [pts, ftm, fta, tech]               # a player's game log (gp is never shown there)
  ```

  Each list holds `gp`, the group's counting stats and the derived stats, in the order shown. A list left out
  keeps the default: GP, the counting stats, then the rates. A rate nobody has a value for yet is left out of
  every list. The key column is the first leaderboard's stat for the group when the list has it, else the first
  column after GP. The computed `leaders.columns[group]` is `{table, totals, log}`, each a list of
  `{key, label, title, key_col}`.

### `minimums`

```yaml
minimums:
  ppg_min_games: {default: 0, decide: true, label: "Minimum games for the points per game leaders",
                  note: "Minimum {value} games played."}
```

`default` is a whole number. `decide` and `label` work as for options. `note` is a template (below).

### `leaderboards`

```yaml
leaderboards:
  - {id: ppg, of: player, group: player, stat: ppg, label: Points / game, tile: true, edge: accent,
     min: {stat: gp, setting: ppg_min_games, cap_at_team_games: true}, detail: "{pts} pts in {gp} GP"}
```

`id`, `of` (`player` or `team`), `stat` and `label` are required. `group` defaults to `player`. `stat` must be
a counting or derived stat of that group (or a team stat when `of: team`). `tile: true` also makes a leader
tile on the home page. `min` points `setting` at a key of `minimums`.

A **team board** (`of: team`) ranks the teams on one of the sport's `stats.team`, summed over the regular season.
Its `detail` may name the standings columns (`{w}`, `{pf}`, `{diff}`...), the team's stats
(`{ends}`) and `gp`. Here `gp` is the games the team **has a score sheet for**: team stats are counted from sheets,
so a forfeit adds nothing to them and is not a game in "in {gp} games". The standings' own GP column still counts
the forfeit. (Curling: `detail: "in {gp} games"`.)

Four optional switches (all true/false, all off or on as listed) change who is ranked and where a board shows:

| Key | Default | Effect |
|---|---|---|
| `zero` | `false` | A value of 0 is ranked (free-throw percentage: 0.0% is a real result). A missing value (`None`, "—") never is; without `zero` a 0 is not ranked either. |
| `playoffs` | `false` | The board counts playoff games too, regular season and playoffs summed (technical fouls over the whole season). Rates are worked out again from the sums. The player's own Season and Playoffs rows stay apart. |
| `home` | `true` | `false` keeps the board off the Home page; the Stats page and an archive season still show it. |
| `player_rank` | `true` | `false` keeps the board out of the "Ranks:" line on a player page. Ranks are kept per stat, so when two boards share a stat the first one with `player_rank` on gives the rank. |

`detail` and `note` strings are Python `str.format` templates over the row's display values (`{gp}`, `{pts}`,
and for team boards the standings columns). The schema rejects a name the core does not supply, so a typo
fails the contract test and not a page. This is the only templating a sport writes.

### `labels`, `labels_by_layout`, `display`, `positions`

* `labels` is a map of section names (`results`, `next`, `leaders`, ...). `labels_by_layout` maps a layout id
  to the same, e.g. `{scoreboard: {leaders: Buckets}}`. A league may override any of them in `league.yml`.
* `display` hints where a core part branches on the sport. Parts never test the sport's id, they read these:

  | Key | Values |
  |---|---|
  | `card` | `rows` (default) or `lines` (the result card holds a line score) |
  | `card_foot` | `note` (default), `meta` ("Sheet A · 6:30 PM") or `status_note` |
  | `surface` | `label` (default) or `sub` (under the time) |
  | `results_legend` | **Optional.** `[{kind, text}, ...]`: a key printed above a list of result cards on Home, Schedule and a team page, for the marks the card's line score uses. `kind` is one of `hammer won mark blank limit x`; `text` is the words ("Hammer in end 1", "Stolen end", "Not played"). It reaches the pages as `league.json` `results_legend` (empty when the sport sets none). |
  | `team_sub` | **Optional.** A key of `positions` (curling: `skip`). Each team card gets a line under its name, "Skip Gail R.": the regular (not a spare) in `players.yml` with that position, the first listed when two share it; no line when nobody has it. It is `teams.json` `sub`. Needs `positions:` in the same file. |

## `rules.py`: the four functions

All four are **pure**: no file reading, no randomness, no clock. They may import only the standard library
and `scripts.core.model`, so the stage 7 JavaScript port can match them line for line. They must not change
their arguments (the contract test checks).

| Function | Gets | Returns |
|---|---|---|
| `check(sheet, ctx)` | the `sheet:` block (anything: it is not yet known to be valid), a `SportContext` | `list[Problem]`: **every** problem found |
| `read(sheet, ctx)` | a sheet `check` accepted | a `Reading` |
| `present(reading, ctx)` | a `Reading` | a dict of display blocks ([next section](#what-present-returns)) |
| `derive(counts, group)` | summed counts including `gp`, and the stat group | `{stat key: number or None}`; `None` shows as a dash |

* **`check`** returns paths relative to `sheet` (`final.home`, `players.home.0.pts`); the core puts `sheet.` in
  front. `""` means the whole sheet. It reports unknown keys (there is no separate schema), and it must
  never raise, whatever it is given: the contract test feeds it deleted, emptied, negative, text and
  unknown-key variants of real sheets. Each `Problem` has `level` (`error` or `warning`), `at` and one plain
  sentence that says what to do. `ctx.folder` is `"games"` or `"drafts"`: a draft may leave boxes empty, so a
  missing box is a warning there and an error in `games` (a draft is never stricter than a finished sheet).
* **`read`** is arithmetic over a valid sheet. It does not decide wins, ties or standings points: the core
  does that from the `Score`, so no sport can get the standings rule wrong.
* **`present`** returns a closed set of blocks that core includes render. A sport writes no HTML or Liquid.
* **`derive`** serves one game and a season total alike, so the game page and the stats page agree.

### The types (`scripts/core/model.py`)

| Type | Fields |
|---|---|
| `Problem` | `level`, `at`, `message`, `file` (set by the core) |
| `SportContext` | `sport` (its parsed `sport.yml`), `options`, `teams`, `players`, `sides` (`{"home": "otters", "away": "ravens"}`), `game_type` (`regular` or `playoff`), `folder` |
| `Score` | `final` (per side), `periods` (per side; `None` = not played), `extra` (overtime and so on, after the periods), `decided_in` (`regulation`, `overtime` or `shootout`), `final_at` |
| `Line` | `side`, `player` (an id from `players.yml`), `group` (`"player"` by default), `counts` (keys from `stats.<group>`) |
| `Reading` | `score`, `lines` (a player with no line did not play), `team_lines` (per side), `facts` (anything `present` needs) |

`Score.final_at[side]` is the path of the box that holds that side's final score, **from the top of the file**
(`sheet.final.home`), unlike the paths `check` returns. The core uses it to point at the right box when a
result is wrong (a tie where ties are not allowed).

### What `call_sport` checks

The core calls every sport function through `call_sport` (`scripts/core/problems.py`). If a function raises,
or returns the wrong shape, the build stops with exit code 2 (an internal error, not a data problem) naming
the function and its file. It checks:

| Function | Checked |
|---|---|
| `check` | returns a list, and every item is a `Problem` |
| `read` | returns a `Reading`; `score` is a `Score` with `final`, `periods` and `final_at` for both sides, whole numbers, equal period counts, a valid `decided_in`; every `Line` has a side, a player id, integer counts, a `group` and count keys that `sport.yml` lists; `team_lines` keys likewise; `facts` is a dict |
| `present` | returns a dict with only the keys `line_score card tiles blocks`; every block has a known `type`; `card.meta_extra`, when given, is a list of strings |
| `derive` | returns a dict of stat key to number or `None` |

The contract test checks more (cell flags, column keys, that `derive` returns only declared stats).

## What `present` returns

```python
{
  "line_score": {"shape": "periods", "corner": "Team", "total_label": "Final", "extra_label": None,
                 "columns": [{"label": "H1"}, {"label": "H2"}],
                 "rows": {"home": {"cells": [{"v": 12, "won": True}, {"v": 9}], "total": 21,
                                   "extra": None, "hammer_first": False},
                          "away": {...}},
                 "mark_word": None, "won_word": "won the half", "legend": [], "note": None},
  "card":   {"note": "Top: #7 Ann B. 9 pts", "strong": "#7 Ann B.", "link_label": "Box score",
             "line_score": None, "meta_extra": []},
  "tiles":  [],
  "blocks": [{"type": "stat_table", ...}, {"type": "note", "text": "..."}],
}
```

* Top-level keys: `line_score`, `card`, `tiles`, `blocks`. Nothing else.
* A cell or column holds `v` (the value) and any of the **flags** `won mark blank void open hammer`, set to
  `True` only when they apply. They map one-to-one onto the design system's classes (`is-won`, `is-mark`,
  `is-blank`, `is-void`, `is-open`, `svg.st-hammer`). Every row has one cell per column.
* `card` (all optional except what the card prints): `note` and `strong` (the note, and the part of it in bold),
  `link_label` ("Box score"; default "Box score"), `note_long`, and two for a sport whose cards show more:
  `line_score` is the card's **own compact line score**, the same shape as the game's but usually without the
  per-cell hammers or blank shading (curling's `card: lines` cards; when it is `None` the include falls back to the
  game's line score), and `meta_extra` is a list of strings added to the foot after the surface and time
  ("Sheet A · 6:30 PM · Shook hands after 6"). `meta_extra` must be a list of strings; `call_sport` checks.
* **Block types:** `stat_table`, `note`, `top_performer`, `numbers` and `roster`.
  * `stat_table`: `title`, `side`, `caption`, `number_col`, `columns` (`key`, `label`, `title`, `key_col`),
    `rows` (`player` id and `cells` of already-formatted text), `totals` (`label` and `cells`), `note`.
  * `note`: `text`.
  * `top_performer`: the game's best player as a tile: `label` ("Top scorer"), `player` (a players.yml id),
    `side` (`home` or `away`: whose player), `value` (24), `unit` ("Points") and an optional `detail` line
    ("Rapids · 6-7 free throws"). The player is a link when the player has a page and plain text in a past
    season. Two players tied are two blocks, so two tiles; a sport that wants no tile for three or more
    leaves the block out.
  * `numbers` ("The game in numbers", curling): `title`, `corner` (the first column's head), `rows` and `note`.
    Each row is `{label, cells: {home, away}, key, hot}`: `cells` are already-formatted text, `key` is `home`,
    `away` or `null` (the side whose cell is bold, normally the bigger value) and `hot: true` also gives that cell
    the hot accent (curling's stolen ends). The columns are the game's two sides, each headed by its chip and team
    code.
  * `roster` (the lineups, curling): `title`, `link_label` ("Rink"), `teams` and `note`. Each team is
    `{side, rows: [{role, player, key, spare_for}]}`: `role` is the position's word, `player` a players.yml id,
    `key` bolds the name (the skip) and `spare_for` (a player id, or null) adds the outline "Spare" badge and
    "for Brian S.". The team's head links to the team page; in a past season, which has no team pages, it is plain
    text.
* A new kind of display (still to come: `facts`, `events`, a penalties table) becomes a **reusable core part** with
  CSS, a specimen on the design-system page and a parity case. It then joins the list `BLOCK_TYPES` in
  `scripts/core/model.py` and the contract list in `scripts/design_system/contract.py`. `numbers` and `roster` were
  added this way for curling (`_includes/parts/numbers.html`, `roster.html`, dispatched by `parts/blocks.html`).
  A sport never ships its own Liquid.

## What the core does for you: standings

The core, not the sport, turns a `Score` into results and points (`scripts/core/standings.py`).

**Per game**, each team gets a result: `win`, `loss`, `tie`, `ot_win` or `ot_loss` (the last two when
`decided_in` is not `regulation`). Its points are `points[result] + period_points x periods won`.
Only regulation periods count; a tied period gives nobody a point. The Masters rule is
`period_points: 1, points: {win: 3, tie: 0, loss: 0}`. `ot_win` and `ot_loss` default to `win` and `loss`.

**Forfeits** are a win and a loss. `forfeit: {score: [7, 0]}` gives that score and no period points;
`forfeit: {score: per_period}` gives 1-0 in every regulation period (the sport must say how many with
`line_score.periods`), which does earn period points.

**Ties**: a tied playoff game is always an error; a tied regular-season game is an error when `ties: false`.
Both are reported at `Score.final_at`. Playoff games never count in the standings.

**Columns** the engine knows: `gp w l t otw otl pts pct pf pa diff gb pw`, plus any key of `stats.team`.
`w` counts every win, overtime wins too, and `gp` is `w + l + t`. `pct` counts a tie as half a win. `pw` is
periods won.

**Game logs.** A player's game log has one row per game: the opponent, the result, the score and the group's `log`
columns. Each row carries its own `result_label`: "Win", "Loss" or "Tie", with the sport's extra word after an
extra-play game ("Win (OT)", "Loss (EE)"). The page prints `result_label`; a sport does nothing for this.

**Ranking.** Teams are grouped by `rank_by` (`points`, or `win_pct` when teams play unequal schedules). Inside
a group the tiebreakers run in the listed order, **without restarting**: each splits the group by its key,
and only sub-groups still tied go on to the next. Teams still level after the last one **share a rank** (1,
2, 2, 4) and are listed by name.

| Tiebreaker | Sorts by (higher is better) |
|---|---|
| `head_to_head` | win % in the games among the tied teams (a tie is half a win). Skipped unless every pair has met. |
| `head_to_head_points` | standings points per game among the tied teams. Same skip rule. |
| `wins` | wins |
| `win_pct` | win % |
| `diff` | points for minus against. `{diff: {cap: 7}}` counts each game's margin at most 7 either way. |
| `points_for` | points for |
| `points_against` | fewest points against |
| `periods_won` | periods won |

Each row records the tiebreaker that separated it, and the note under the table says so in a sentence. A new
tiebreaker is a small function in `standings.py` plus a name in `sports.py` `TIEBREAKERS`; it is a core change,
not a sport change.

## `sample.py`

```python
LEAGUE_NAME = "Example Valley Stub League"
TEAMS = [("otters", "Otters", "OTT"), ("ravens", "Ravens", "RAV"), ...]    # made-up names only
PLAYERS_PER_TEAM = 7                                                       # optional; 7 if left out
# More optional constants, read by make_sample.py (below): TIMES, SURFACES, NUMBERS, POSITIONS, NOTES

def sheet(rng: random.Random, game: SampleGame, ctx: SportContext) -> dict
```

* `TEAMS` is a list of `(id, name, code)`. Use **made-up** teams and players. Nothing may look like a real
  league.
* `SampleGame` gives `game_id`, `players` (`{"home": [ids], "away": [ids]}`, who played) and the
  `outcome` wanted: `win_home`, `win_away`, `tie` or `ot`. Bend the outcome to what the rules allow (no
  overtime: `ot` becomes a tie; a playoff game never ties). Use only `rng`, never the clock or global
  random, and do not change `game` or `ctx`.
* `scripts/make_sample.py` does the rest from the league's sport with a fixed seed: teams, made-up
  "First L." players (one with jersey `00` when `NUMBERS` is on, a couple of spares), a round robin, one cancelled game, one moved
  game, one forfeit, a tie where the rules allow one, upcoming game days, playoff rows with placeholder
  teams and one draft. It writes `data/sample-*/`, runs your `check`, `read` and `present` on every sheet,
  and then runs the loader on the result. Any problem stops it.
* **Optional constants** in `sample.py` (a sport sets only what differs from basketball's defaults; a wrong value
  stops the script with a message naming the constant):

  | Constant | Default | Meaning |
  |---|---|---|
  | `PLAYERS_PER_TEAM` | `7` | Regulars on a team (curling: `4`, a rink). The contract test asks for this many, not five. |
  | `TIMES` | `["19:00", "20:15"]` | The start times of a night: game number `g` of a day starts at `TIMES[g % len(TIMES)]`. Curling: `["18:30", "18:30", "20:45"]`, so two sheets share the early draw and one plays late. Each must look like `"19:00"`. |
  | `SURFACES` | `"1"`, `"2"`... | The court, sheet or pad names for a sport whose `words` has a `surface`: game `g` of a day plays on `SURFACES[g]`. Curling: `["A", "B", "C"]`. A list shorter than the games a night has is an error. |
  | `NUMBERS` | `True` | `False` gives players no jersey number. With `True` one player gets `00`, which exercises the strict loader (the contract test asks for a `00` only when `NUMBERS` is on). Curling: `False`. |
  | `POSITIONS` | none | A list of the sport's `positions`, written to `players.yml` in roster order: the first player of a team gets the first, and so on. Each must be in `sport.yml` `positions`. Curling: `["lead", "second", "vice", "skip"]`. |
  | `NOTES` | two sentences | The free-text game notes some sheets carry. Curling writes its own. |

* `make_sample.py` reads the sport from `league.yml`. To write a new sport's sample, set `sport:` there
  first. `python scripts/make_sample.py --check` fails if the files on disk differ from what it would
  write; a test runs that. The committed `data/sample-*` are the sample of the sport `league.yml` names
  (basketball today).
* `tests/test_golden.py` writes each sport's sample into a temporary root and compares the build with
  `tests/golden/<sport>/` (`stub`, `basketball` and `curling`). `UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py`
  rewrites them; read the diff, and check a new sport's standings and leaders by hand against its sample files.

## Sport previews

`sport_previews` in `league.yml` (`true`, `false` or a list of sport ids; it is separate from `preview`, which is
the league's own look with made-up games) makes the deploy also build a demo copy of the site for each sport at
`/<sport>/` (`/basketball/` and `/curling/` today). A sport needs nothing for this beyond a `sample.py`: every folder in `sports/`
with one is a demo, unless its `sport.yml` says `demo: false`. A copy shows the sport's `sample.py` league, the
sport's `default_layout`, the sport's own defaults (so its `decide: true` settings show as `[placeholder]`) and
the two sample seasons; nothing of the league's own `league.yml` but `timezone` and `time_format`.

* `python scripts/preview_root.py --list` prints the ids `league.yml` asks for (and checks them);
  `python scripts/preview_root.py <sport> <folder>` writes the temporary root a copy is built from.
  `scripts/build_preview.sh` runs both, then `build.py --root <folder> --out . --sport-preview <sport>` and Jekyll
  with the base path `<BASE_PATH>/<sport>`, once per sport after the real build, and finally puts the real data
  back.
* Every page of a copy is `noindex, nofollow`, whatever `search_engines` says; it has no calendar files; nothing on
  the league's own pages links to it; its banner (`shell/sample-banner.html`) names it a sport preview and links to
  the other sport previews and back to the live site. A sport id may not be one of the site's top-level paths
  (`archive assets calendar games players preview rules schedule sheets stats teams`).
* A new sport therefore gets its demo for free the day its folder lands. If the sport is not ready to be shown,
  set `demo: false` until it is.

## The contract test

```
python -m pytest tests/test_sport_contract.py
```

It runs on every folder in `sports/`, so a new sport joins it with no change to the test. For each sport it
checks:

* `sport.yml` is valid, the four files are there, the four functions exist and take the right arguments, and
  the README is not empty.
* The sample season passes every check, for the defaults and for every value of every `choice` option, and is
  identical on two runs.
* The sample has a cancelled game, a moved game, a forfeit, a draft, playoff rows with placeholder teams, and
  made-up "First L." names with a spare (and a `00` when `NUMBERS` is on, or no numbers when it is off), with
  `PLAYERS_PER_TEAM` players a team and, when `POSITIONS` is set, the positions in roster order.
* **Every problem `check` reports has a path that leads into the sheet** (or to a missing key whose parent
  exists), for many broken variants of real sheets, in `games` and in `drafts`. `check` is never
  stricter for a draft, and never changes its input.
* `present` uses only the known keys, block types and cell flags; `read`'s final-score paths resolve;
  `derive` returns only declared stats; `sample.sheet` changes nothing it is given.
* The committed `data/sample-*` is what `make_sample.py` writes, and the loader finds no problem in it.

Related: `tests/test_sports.py` (the `sport.yml` schema, with the folders in `tests/fixtures/sports/`) and
`tests/test_stub_sport.py` (the stub's own rows) and `tests/test_empty_player_group.py` (a sport whose
player group counts nothing, built end to end). A new sport adds a `tests/test_<id>_sport.py` for its own rules,
and, from stage 5, shared fixtures (`tests/test_<id>_fixtures.py`).

## Checklist for a new sport

1. Copy `sports/stub/` to `sports/<id>/`. The id is lower-case letters, digits and hyphens.
2. `sport.yml`: name, `default_layout`, `words`, `line_score` (with `periods`), `options`, `standings`,
   `stats`, `minimums`, `leaderboards`, `labels`, `display`, `positions`.
3. Mark every rule that a league decides with `decide: true`. **Never invent a league's rule.** The defaults
   are the typical club rule, and the league's own choice replaces them.
4. `rules.py`: `check` (every problem, paths relative to `sheet`, never raises, drafts may leave boxes
   empty), `read`, `present` (known blocks and flags only), `derive`. Keep it pure and standard-library
   only, so the JavaScript port can match it.
5. `sample.py`: made-up teams and a `sheet()` that honours the outcome. Add `PLAYERS_PER_TEAM`, `TIMES`, `SURFACES`,
   `NUMBERS` and `POSITIONS` where the sport's nights and rosters differ from basketball's.
6. `README.md`: the format box by box, with the problem paths and levels, as `sports/stub/README.md` does.
7. Run `python -m pytest tests/test_sport_contract.py`. Fix what it names.
8. Write the sport's own tests (every row of its checks). From stage 5, add fixtures in
   `sports/<id>/fixtures/`.
9. Set `sport: <id>` in `league.yml`, run `python scripts/make_sample.py`, then
   `python scripts/build.py` and look at the pages at 390 px in both themes. Add the sport to `SPORTS` in
   `tests/test_golden.py` and write its golden files (`UPDATE_GOLDEN=1`), checked by hand. (The golden test writes
   the sample into a temporary folder, so you need not leave `league.yml` on the new sport: the committed
   `data/sample-*` stay the shipped sport's, and `make_sample.py --check` must still pass on them.)
10. If the sport needs a display the closed block list cannot express, add a core part first (include, CSS,
    specimen, parity case, entry in `BLOCK_TYPES`), then use it.
11. Check the sport preview: `scripts/build_preview.sh` (with `bundle exec jekyll build` first) builds
    `_site/<id>/`. Leave `demo` out so it is shown, or set `demo: false` while it is unfinished.
12. Update `docs/data.md` examples only if they mention the sport, and list the sport's `decide: true` settings in
    `docs/open-questions.md`.

## Where the code differs from the spec

The spec (`docs/stage-4-spec.md`) is the plan. The code, as of this page, differs in these ways:

| Spec | Code |
|---|---|
| `line_score` has `shape`, `total_label`, `corner` (3.2). | Also an optional `periods`, needed for `per_period` forfeits. |
| `options` and `minimums` list `type`/`default`/`decide`... (3.2). | Both also take an optional `label`, the words for "Still to decide". |
| Sports import from `scripts.core.types` (3.1, 3.3). | The module is `scripts.core.model`: a file called `types.py` shadows the standard library's `types`. |
| `stats.player` (3.2). | Any group name works (hockey: `skater`, `goalie`); `derived`, `team` and `columns` are the reserved names. |
| A sports folder needs four files (3). | `README.md` may be missing at load (a warning); the contract test requires it. |
| `Score.final_at` "for core problems" (3.1). | Paths start with `sheet.` (from the top of the file), unlike `check`'s paths. `call_sport` enforces it. |
| Forfeits (3.5): "a forfeit is a win/loss; its score is `forfeit.score`". | A fixed score earns no period points; `per_period` earns all of them. |
| Ranks (3.5): "teams still level share a rank". | Competition ranking: 1, 2, 2, 4. |
| Columns (3.5). | `w` includes overtime wins, `gp = w + l + t`; `otw`/`otl` are the "of which" counts. |
| `sample.py` has `LEAGUE_NAME`, `TEAMS`, `sheet` (3.6). | Also an optional `PLAYERS_PER_TEAM` (default 7). |
| `build.py` flags (4). | Not covered here; `scripts/build.py` is written separately. `--sport-preview <id>` is the flag for a sport's demo copy. |
| Block types: `stat_table`, `note` (3.3). | Also `top_performer` (stage 5, the game page's top scorer tile). |
| Leaderboards have `id of group stat label tile edge min detail` (3.2). | Also `zero`, `playoffs`, `home`, `player_rank`. |
| `stats` has the groups, `derived` and `team` (3.2). | Also `columns` (the order of the columns for the Stats page, a player's totals and a game log), and `derive` may return an unrounded rate (the core rounds it and ranks on the exact value). |
| `sport.yml` has no switch for demos. | The optional `demo` key (default `true`); the stub says `false`. |
| `rules.js` ships with each sport (stage 5 plan). | Moves to stage 7 with the entry page. Stage 5 leaves each sport's `fixtures/` for it. |
| Block types: `stat_table`, `note` (3.3). | `top_performer` (basketball), `numbers` and `roster` (curling). Still to come: `facts`, `events`, a penalties table. |
| `words` has `period`, `day`, `surface`, `points_for`, `points_against` (3.2). | Also an optional `extra` (`{one, short}`): "Final · EE", "an extra-end win", "ends won". |
| `display` has `card`, `card_foot`, `surface` (3.2). | Also `results_legend` (a key above the result cards) and `team_sub` (the skip line on a team card). |
| `present()['card']` has `note`, `strong`, `link_label` (3.4). | Also `line_score` (the card's own compact line score), `meta_extra` (more parts for the card foot) and `note_long`. |
| `sample.py` has `LEAGUE_NAME`, `TEAMS`, `sheet`, optional `PLAYERS_PER_TEAM`. | Also optional `TIMES`, `SURFACES`, `NUMBERS`, `POSITIONS` and `NOTES`. |
| A team board's `{gp}` is the standings' GP. | The games with a score sheet: a forfeit is not a game there. |
