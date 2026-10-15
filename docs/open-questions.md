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

## 3. Decisions waiting for the owner

The stage 3 decisions are written out in `docs/design.md`, under "Decisions made in stage 3 (for the owner to
confirm)". The ones that are still open:

1. **Team palettes follow the layout.** A team with no colour of its own changes colour when the league changes
   layout. Should the palette follow the team or the sport instead?
2. **The team card** is new and no mockup shows it. Is the design right in all six layouts?
3. **Changed mockup colours.** The contrast changes in "Mockup colours changed for AA" (for example Basketball's
   deeper light `hot` red, the Scoreboard ticker tag in amber) are accepted?
4. **Accepted exception.** The curling header's red line stays at 2.76:1 (decorative). OK?
5. **Structure the mockups did not draw:** the hero card for curling and hockey; the Scoreboard game row with the
   time first; the Scoreboard "Next up" bar for slo-pitch; edges on Classic-Curling's tiles; no amber outline on
   Scoreboard's dark lead row.
6. **Old browsers.** Browsers older than Safari 16.2, Chrome 111 and Firefox 113 show the layout's default colours
   instead of the league's own (readable, but not the league's colour). Is that floor acceptable for a 50+
   audience, or should stage 4 write the derived colours as hex instead?
7. **Scenes** (header and footer pictures) are fixed and do not follow the league colour. Should any of them?
8. **Sample "Scored with hammer" 3 of 5** (the mockup said 2 of 5): confirm the correction.
9. **Search engines.** Default off (noindex) or on? (`BRIEF.md`, "Not decided yet".)
10. **Setup help.** A written guide only, or also a `/new-league` Claude Code command? (`BRIEF.md`.)
11. **Desktop** layouts are stage 9; phone first until then.
