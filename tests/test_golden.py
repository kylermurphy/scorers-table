"""Golden files: `build.py --sample --today 2026-11-20` on the committed stub sample against tests/golden/.

`tests/golden/_data/computed/` is the whole of `_data/computed/` and `tests/golden/pages.json` holds every stub page
(`_games/ _players/ _teams/ _archive/`, path -> text), so any change to a number, a label, a key, the order of keys or
a page's front matter shows up as a diff in review. When a change is meant, rewrite them:

    UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py

and read the diff of tests/golden/ before committing it (the standings and leaders were checked by hand against
the sample game files when these were first written: see the pull request).
"""
import difflib
import json
import os
import shutil
from pathlib import Path

import pytest

from scripts import build

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
TODAY = "2026-11-20"
PAGE_FOLDERS = ("_games", "_players", "_teams", "_archive")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("golden_build")
    assert build.main(["--sample", "--today", TODAY, "--out", str(out)]) == 0
    return out


def snapshot(out: Path) -> dict[str, str]:
    """{path under tests/golden: text} for everything the build wrote that the golden files pin."""
    files = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((out / "_data" / "computed").rglob("*")) if p.is_file()}
    pages = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
             for folder in PAGE_FOLDERS for p in sorted((out / folder).glob("*.md"))}
    return {**files, "pages.json": json.dumps(pages, indent=2, ensure_ascii=False) + "\n"}


def stored() -> dict[str, str]:
    if not GOLDEN.is_dir():
        return {}
    return {p.relative_to(GOLDEN).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(GOLDEN.rglob("*")) if p.is_file()}


def rewrite(files: dict[str, str]) -> None:
    shutil.rmtree(GOLDEN, ignore_errors=True)
    for rel, text in files.items():
        path = GOLDEN / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")


def test_build_matches_the_golden_files(built):
    actual = snapshot(built)
    if os.environ.get("UPDATE_GOLDEN"):
        rewrite(actual)
        pytest.skip(f"golden files rewritten ({len(actual)} files in tests/golden/)")
    expected = stored()
    assert sorted(actual) == sorted(expected), (
        f"different files. Only in the build: {sorted(set(actual) - set(expected))}. "
        f"Only in tests/golden: {sorted(set(expected) - set(actual))}. Rewrite with UPDATE_GOLDEN=1 if that is meant.")
    for rel in sorted(actual):
        if actual[rel] != expected[rel]:
            diff = "\n".join(list(difflib.unified_diff(expected[rel].splitlines(), actual[rel].splitlines(),
                                                       f"golden/{rel}", f"build/{rel}", lineterm="", n=2))[:60])
            pytest.fail(f"{rel} differs from tests/golden (UPDATE_GOLDEN=1 rewrites it if the change is meant):\n{diff}")


def test_the_golden_files_cover_both_sample_seasons():
    names = set(stored())
    for season in ("sample-2026-27", "sample-2025-26"):
        for name in ("teams", "standings", "schedule", "results", "games", "players", "leaders"):
            assert f"_data/computed/{season}/{name}.json" in names
    for name in ("league", "active", "seasons", "archive", "calendars"):
        assert f"_data/computed/{name}.json" in names
    assert "pages.json" in names
