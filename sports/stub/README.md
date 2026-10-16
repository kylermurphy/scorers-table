# The stub sport

A made-up sport, used to test the whole site. Two teams play a number of halves (default 2); the sheet has a
Final box, optional overtime, and an optional list of who played with their points. Nothing here is a
real league's rule: a real sport is a folder like this one (`sport.yml`, `rules.py`, `sample.py`,
`README.md`).

## The sheet

In a game file (`data/<season>/games/<game_id>.yml`) the sheet is the `sheet:` block. Sides are `home` and
`away`, never team ids.

```yaml
sheet:
  periods: {home: [12, 9], away: [11, 10]}   # one whole number per half, for each side
  overtime: {home: 3, away: 1}               # only when the rules have overtime and the halves ended level
  final: {home: 24, away: 22}                # the Final box, as written
  players:                                   # optional: who played; pts is optional on each row
    home: [{player: ann-b, pts: 9}, {player: joe-k}]
    away: [{player: tom-w, pts: 4}]
```

| Box | What goes in it |
|---|---|
| `periods.<side>` | a list with exactly one whole number (0 to 99) per half. The number of halves is the league's `rules: {periods: N}` (2 unless set). |
| `overtime.<side>` | whole numbers (0 to 99), one per side, and not equal. Leave the box out unless the league's `rules: {overtime: overtime}` is set and the halves ended level. |
| `final.<side>` | the Final box: the halves plus overtime added up (0 to 999). |
| `players.<side>` | optional. A list of `{player: <id from players.yml>, pts: <whole number>}`. A player on the list played; `pts` may be left out (counted as 0). |

A game tied after the halves with no overtime is a tie (regular season) or an error (playoffs); the core
decides that, not this sport. A forfeit has no sheet: the game file says `forfeit: <team id>` instead.

## What is checked

Paths are inside the game file; the core puts `sheet.` in front of the ones below.

| Path | Problem | Level |
|---|---|---|
| `<key>` | a line other than `periods`, `overtime`, `final`, `players` | error |
| `periods.<side>` | missing, not a list, or not exactly one number per half | error (warning in a draft when empty) |
| `periods.<side>.<i>` | not a whole number from 0 to 99 | error |
| `overtime` | present when the rules have no overtime, or when the halves did not end level | error |
| `overtime.<side>` | missing or not a whole number; `overtime.home` when the overtime is still tied | error |
| `final.<side>` | missing, not a whole number, or not the halves plus overtime ("the Final box says 24, but the halves and overtime add up to 23") | error |
| `players.<side>.<i>.player` | not a player in `players.yml`, or listed twice in the game | error |
| `players.<side>.<i>.player` | a player of another team who is not marked `sub: true` | warning |
| `players.<side>.<i>.pts` | not a whole number | error |
| `players.<side>` | every row has `pts` but they do not add up to `final.<side>` | warning |

Unknown lines are errors at every level (`periods.<key>`, `final.<key>`, a player row's `<key>`), because
they are nearly always typos. A **draft** (`drafts/`) may leave boxes empty: an empty or missing box is a
warning there and an error in `games/`.

## What the site shows

* The line score has one column per half (`H1`, `H2`), an `OT` column when there was overtime, and the
  Final total; the higher number in each column is marked as the winner of that half.
* The result card names the top scorer ("Top: #7 Ann B. 9 pts") when any player has points.
* The game page has a box score table for each side that lists players, and a note.
* Player stats: `pts` (summed) and `ppg` (points per game, one decimal, half up).

## Settings the league may change

| Setting (`league.yml`) | Values | Default |
|---|---|---|
| `rules.periods` | 1 to 9 | 2 |
| `rules.overtime` | `none`, `overtime` | `none` (the league decides: shown as `[placeholder]` until set) |
| `standings.*` | see `sport.yml`; forfeit score and tiebreakers are the league's to decide | 2-1-0, ties allowed |
| `stats.minimums.ppg_min_games` | games played before a player is ranked on points per game | 0 (the league decides) |
