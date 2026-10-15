# Loader fixtures

`valid/` is a small, correct data folder (made-up league, sport `tiny`): the real season `2026-27` is empty,
`sample-2026-27` stands in for it, `sample-2025-26` is a past sample season with its own points rule.
`sample-2026-27/drafts/` holds a file that is not even YAML: the loader must never open it.
Tests that need broken data copy `valid/` or write files into `tmp_path`.
