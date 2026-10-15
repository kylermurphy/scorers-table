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

Basketball's standings note has no tiebreaker placeholder because the sample does not show one; a
real league still has to decide it.

## 2. Rules a league has to decide

`BRIEF.md` gives "typical club rules" as defaults. These are the choices behind them. Each one is a
setting later (stages 4 and 5) and shows as a `[placeholder]` until the league answers.

**Every sport**
* Tiebreakers for standings, in order.
* Playoff format and which games count as playoffs.
* Whether ties are allowed in the regular season, and how a forfeit is scored.

**Basketball**
* Points for a win (the sample uses 2) or the Masters rule (1 per quarter won and 3 per win).
* Whether overtime is played, and how a tie after overtime is treated.

**Curling**
* 8 or 6 ends; whether an extra end is played when tied or the game is a tie.
* Whether a team may concede early (the sample shows "Shook hands after 6").
* The order of tiebreakers: head-to-head, then points for and against.

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
old-browser floor; fixed scenes; the "Scored with hammer" 3 of 5 correction). Still open, from `BRIEF.md`:

1. **Search engines.** Default off (noindex) or on? (`BRIEF.md`, "Not decided yet".)
2. **Setup help.** A written guide only, or also a `/new-league` Claude Code command? (`BRIEF.md`.)
3. **Desktop** layouts are stage 9; phone first until then.
