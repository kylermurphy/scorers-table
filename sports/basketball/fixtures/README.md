# Basketball fixtures

One game file per case, with what the rules must say about it. They are shared: `tests/test_basketball_fixtures.py`
runs them against `rules.py`, and the JavaScript copy of the rules (stage 7, for the entry page) is tested against
the same files.

| File | What it is |
|---|---|
| `context.yml` | The two teams (Alpha `aa` is home, Bravo `bb` is away), the players, and the league settings every case is checked with. The names are made up, kept from the Masters fixtures they grew out of. |
| `<name>.yml` | One case. `fixture: {folder, game_type, options}` says where the file lives (`games` or `drafts`), whether it is a `regular` or `playoff` game, and any rules that differ from `context.yml` (`overtime`, `foul_limit`). `sheet:` is the sport's part of the game file. A comment at the top says what the case shows. |
| `<name>.expected.json` | `problems`: every problem `check` must return, in order, as `{level, at, message}` (the path is relative to `sheet`; the core adds `sheet.`). `reading`: what `read` returns as `{score, lines, facts}`, or `null` when `check` reports an error, or a draft leaves out a whole block. `score.final_at` is the one path that starts with `sheet.`: it is from the top of the file. |

The ten Masters cases are `clean`, `and-one`, `bad-final`, `draft-with-sub`, `ft-mismatch`, `overtime`, `page-two`,
`tie`, `tie-without-overtime` and `unknown-jersey`. Masters' own `forfeit` case is not here: a forfeit has no
sheet, and the core handles it.

Every row of the checks table in `../README.md` has a case; `tests/test_basketball_fixtures.py` lists which.

**Changing a rule.** Edit `rules.py`, then `UPDATE_FIXTURES=1 python -m pytest tests/test_basketball_fixtures.py`
rewrites the expected files. Read the diff: every changed line is a change in what the rules say. A new check
gets a new case.

**For the JavaScript runner.** Running-score totals are keys (`{2: 23, 4: 11}`). YAML reads them as numbers in
Python and a JavaScript YAML reader gives them as text (`"27"`); the runner must turn them back into numbers.
`0` and `"00"` are two jerseys (`"00"` is in quotes in the files). A message that prints a Python `repr`
(`not None`, `'abc'`) must print the same text.
