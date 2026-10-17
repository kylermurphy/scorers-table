# Curling fixtures

One game file per case, with what the rules must say about it. They are shared: `tests/test_curling_fixtures.py`
runs them against `rules.py`, and the JavaScript copy of the rules (stage 7, for the entry page) is tested against the
same files.

| File | What it is |
|---|---|
| `context.yml` | The rinks (Alpha `aa` is "home", Bravo `bb` is "away", Charlie `cc` plays in neither), the players with their positions (a spare with `sub: true`, players of the third rink), and the league settings every case is checked with. All made up. |
| `<name>.yml` | One case. `fixture: {folder, game_type, options}` says where the file lives (`games` or `drafts`), whether it is a `regular` or `playoff` game, and any rules that differ from `context.yml` (`ends`, `extra_end`, `lineups`). `sheet:` is the sport's part of the game file. A comment at the top says what the case shows. |
| `<name>.expected.json` | `problems`: every problem `check` must return, in order, as `{level, at, message}` (the path is relative to `sheet`; the core adds `sheet.`). `reading`: what `read` returns as `{score, lines, team_lines, facts}`, or `null` when `check` reports an error, or a draft leaves out a box (a lineup row with only a `name` still reads: that row has no line). `score.final_at` is the one path that starts with `sheet.`: it is from the top of the file. |

Every row of the checks table in `../README.md` has a case; `tests/test_curling_fixtures.py` lists which (`ROWS`). The
cases that should be quiet are `QUIET` there.

**Changing a rule.** Edit `rules.py`, then `UPDATE_FIXTURES=1 python -m pytest tests/test_curling_fixtures.py`
rewrites the expected files. Read the diff: every changed line is a change in what the rules say. A new check gets a
new case.

**For the JavaScript runner.** `X` is plain text in YAML and in a JavaScript YAML reader alike. Empty boxes are `~`
(null). The ends are lists of numbers and `"X"`. A message that prints a Python `repr` of a text value
(`'abc'`, in single quotes) must print the same text.
