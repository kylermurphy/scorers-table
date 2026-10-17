"""Golden files: `build.py --sample --today 2026-11-20` on each sport's sample against tests/golden/<sport>/.

For each sport in SPORTS the test writes a throwaway root: the repository's `sports/`, its `league.yml` with that
sport (and the sport's sample league name), its `data/seasons.yml`, and the sample seasons that
`scripts/make_sample.py` writes for that sport with the fixed seed (so they are the files committed under
`data/sample-*/` when the sport is the league's own). It then builds that root.

`tests/golden/<sport>/_data/computed/` is the whole of `_data/computed/` and `tests/golden/<sport>/pages.json`
holds every page (`_games/ _players/ _teams/ _archive/`, path -> text), so any change to a number, a label, a key,
the order of keys or a page's front matter shows up as a diff in review. When a change is meant, rewrite them:

    UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py

and read the diff of tests/golden/ before committing it (the stub's standings and leaders were checked by hand
against its sample game files when these were first written, the basketball ones the same way: see the pull
request). The stub stays the core's test sport, with golden files of its own.
"""
import difflib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from scripts import build, make_sample
from scripts.core.sports import load_sport

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
TODAY = "2026-11-20"
PAGE_FOLDERS = ("_games", "_players", "_teams", "_archive")
SPORTS = ("stub", "basketball", "curling")


def sample_root(base: Path, sport_id: str) -> Path:
    """A throwaway repository root that shows `sport_id`'s sample league."""
    sport, problems = load_sport(sport_id, ROOT / "sports", with_sample=True)
    assert sport is not None, problems
    root = base / sport_id
    shutil.copytree(ROOT / "sports", root / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "data").mkdir()
    shutil.copy(ROOT / "data" / "seasons.yml", root / "data" / "seasons.yml")
    shutil.copytree(ROOT / "data" / "2026-27", root / "data" / "2026-27")        # the (empty) current season
    text = (ROOT / "league.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^sport: .*$", f"sport: {sport_id}", text)
    text = re.sub(r"(?m)^name: .*$", f"name: {json.dumps(sport.sample.LEAGUE_NAME)}", text)
    (root / "league.yml").write_text(text, encoding="utf-8")
    make_sample.write_all(root, make_sample.generate_all(root))
    return root


@pytest.fixture(scope="module", params=SPORTS)
def built(request, tmp_path_factory):
    base = tmp_path_factory.mktemp("golden_root")
    out = tmp_path_factory.mktemp("golden_build")
    root = sample_root(base, request.param)
    assert build.main(["--root", str(root), "--sample", "--today", TODAY, "--out", str(out)]) == 0
    return request.param, out


def snapshot(out: Path) -> dict[str, str]:
    """{path under tests/golden/<sport>: text} for everything the build wrote that the golden files pin."""
    files = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((out / "_data" / "computed").rglob("*")) if p.is_file()}
    pages = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
             for folder in PAGE_FOLDERS for p in sorted((out / folder).glob("*.md"))}
    return {**files, "pages.json": json.dumps(pages, indent=2, ensure_ascii=False) + "\n"}


def stored(sport_id: str) -> dict[str, str]:
    folder = GOLDEN / sport_id
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(folder.rglob("*")) if p.is_file()}


def rewrite(sport_id: str, files: dict[str, str]) -> None:
    shutil.rmtree(GOLDEN / sport_id, ignore_errors=True)
    for rel, text in files.items():
        path = GOLDEN / sport_id / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")


def test_build_matches_the_golden_files(built):
    sport_id, out = built
    actual = snapshot(out)
    if os.environ.get("UPDATE_GOLDEN"):
        rewrite(sport_id, actual)
        pytest.skip(f"golden files rewritten ({len(actual)} files in tests/golden/{sport_id}/)")
    expected = stored(sport_id)
    assert sorted(actual) == sorted(expected), (
        f"different files. Only in the build: {sorted(set(actual) - set(expected))}. "
        f"Only in tests/golden/{sport_id}: {sorted(set(expected) - set(actual))}. "
        "Rewrite with UPDATE_GOLDEN=1 if that is meant.")
    for rel in sorted(actual):
        if actual[rel] != expected[rel]:
            diff = "\n".join(list(difflib.unified_diff(expected[rel].splitlines(), actual[rel].splitlines(),
                                                       f"golden/{sport_id}/{rel}", f"build/{rel}", lineterm="", n=2))[:60])
            pytest.fail(f"{rel} differs from tests/golden/{sport_id} (UPDATE_GOLDEN=1 rewrites it if the change is meant):\n{diff}")


@pytest.mark.parametrize("sport_id", SPORTS)
def test_the_golden_files_cover_both_sample_seasons(sport_id):
    names = set(stored(sport_id))
    for season in ("sample-2026-27", "sample-2025-26"):
        for name in ("teams", "standings", "schedule", "results", "games", "players", "leaders"):
            assert f"_data/computed/{season}/{name}.json" in names
    for name in ("league", "active", "seasons", "archive", "calendars"):
        assert f"_data/computed/{name}.json" in names
    assert "pages.json" in names



def test_a_team_board_counts_only_games_with_a_score_sheet(built):
    """`{gp}` in a team board's detail ("in 5 games") is the games the team stat was counted from: a forfeit has no
    sheet and adds nothing to the value, so it is not a game there (the standings' GP still counts it)."""
    sport_id, out = built
    season = json.loads((out / "_data" / "computed" / "active.json").read_text(encoding="utf-8"))["season"]
    computed = out / "_data" / "computed" / season
    games = json.loads((computed / "games.json").read_text(encoding="utf-8")).values()
    rows = [r for b in json.loads((computed / "leaders.json").read_text(encoding="utf-8"))["boards"]
            if b["of"] == "team" for r in b["rows"]]
    if not rows:
        pytest.skip(f"{sport_id} has no team boards")
    on_sheet = lambda team: sum(g["type"] == "regular" and not g["forfeit"]                  # noqa: E731
                                and team in (g["home"]["team"], g["away"]["team"]) for g in games)
    forfeited = {t for g in games if g["forfeit"] and g["type"] == "regular" for t in (g["home"]["team"], g["away"]["team"])}
    checked = 0
    for row in rows:
        counts = [int(n) for n in re.findall(r"(\d+) games?", row["detail"])]
        assert counts == [on_sheet(row["team"])], (row["team"], row["detail"])
        checked += row["team"] in forfeited
    assert checked, "the sample has a forfeit between ranked teams, so this test sees the difference"
