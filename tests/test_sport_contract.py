"""The contract every folder under sports/ must keep (docs/stage-4-spec.md, section 7): sport.yml valid, the
README and the four functions present, a sample season that passes every check and is the same on every run,
problem paths that point at a real place in the file, `present` using only the known blocks and cell flags,
and no function changing what it is given. It runs on whatever folders exist, so stage 5 sports join for free."""
import copy
import csv
import io
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import make_sample
from scripts.core.config import normalise_standings, sport_standings_defaults
from scripts.core.model import BLOCK_TYPES, CELL_FLAGS, PRESENT_KEYS, STAT_RESERVED, Reading, SampleGame
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, discover_sports, load_sport

ROOT = Path(__file__).resolve().parent.parent
SPORT_IDS = discover_sports(SPORTS_ROOT)
SEASONS = [{"id": "sample-2026-27", "as_of": "2026-11-20"}, {"id": "sample-2025-26"}]
LINE_CELL_KEYS = {"v", *CELL_FLAGS}
LINE_COLUMN_KEYS = {"label", *CELL_FLAGS}


@pytest.fixture(scope="module", params=SPORT_IDS)
def sport(request):
    loaded, problems = load_sport(request.param, SPORTS_ROOT, with_sample=True)
    assert problems == [], problems
    return loaded


def settings_of(sport, **choose):
    """The sport's defaults, with some options set (choose={"overtime": "overtime"})."""
    rules = {key: opt["default"] for key, opt in sport.spec["options"].items()} | choose
    return rules, normalise_standings(sport_standings_defaults(sport.spec))


def variants(sport):
    """One settings dict for the defaults, then one for every value of every `choice` option."""
    out = [{}]
    for key, opt in sport.spec["options"].items():
        if opt["type"] == "choice":
            out.extend({key: value} for value in opt["values"] if value != opt["default"])
    return out


def generate(sport, season, choose=None, collect=None):
    rules, standings = settings_of(sport, **(choose or {}))
    return make_sample.generate_season(sport, season, rules=rules, standings=standings, collect=collect)


# ------------------------------------------------------------------ the folder

def test_there_is_at_least_one_sport():
    assert "stub" in SPORT_IDS


def test_a_sport_folder_is_complete(sport):
    for name in ("sport.yml", "rules.py", "sample.py", "README.md"):
        assert (sport.folder / name).is_file(), f"{sport.folder.name}/{name} is missing"
    assert (sport.folder / "README.md").read_text(encoding="utf-8").strip()
    for name in ("check", "read", "present", "derive"):
        assert callable(getattr(sport.rules, name))
    assert callable(sport.sample.sheet) and sport.sample.TEAMS and sport.sample.LEAGUE_NAME


# ------------------------------------------------------------------ the sample season

def test_the_sample_is_identical_on_two_runs(sport):
    for choose in variants(sport):
        for season in SEASONS:
            assert generate(sport, season, choose) == generate(sport, season, choose), (choose, season["id"])


def test_the_sample_passes_every_check_for_every_choice_option(sport):
    """generate_season runs the sport's check/read/present on every sheet and raises on any problem."""
    for choose in variants(sport):
        for season in SEASONS:
            files = generate(sport, season, choose)
            assert any(name.startswith("games/") for name in files), (choose, season["id"])


def test_the_sample_season_has_one_of_everything(sport):
    files = generate(sport, SEASONS[0])
    rows = list(csv.DictReader(io.StringIO(files["schedule.csv"])))
    assert list(rows[0]) == make_sample.CSV_COLUMNS
    assert any(r["status"] == "cancelled" for r in rows)
    moved = [r for r in rows if r["moved_from"]]
    assert len(moved) == 1 and moved[0]["game_id"].startswith(moved[0]["moved_from"]) and moved[0]["date"] > moved[0]["moved_from"]
    playoffs = [r for r in rows if r["type"] == "playoff"]
    assert playoffs
    team_ids = {t[0] for t in sport.sample.TEAMS}
    assert any(r["home"] not in team_ids for r in playoffs), "playoff rows with placeholder teams"
    assert all(r["home"] in team_ids and r["away"] in team_ids for r in rows if r["type"] == "regular")
    games = {n[len("games/"):-4]: parse_yaml(t) for n, t in files.items() if n.startswith("games/")}
    drafts = {n[len("drafts/"):-4]: parse_yaml(t) for n, t in files.items() if n.startswith("drafts/")}
    assert len(drafts) == 1 and all(d["status"] == "draft" and d["review"] for d in drafts.values())
    assert sum(1 for g in games.values() if "forfeit" in g) == 1
    assert all("sheet" not in g for g in games.values() if "forfeit" in g)
    assert all(g["status"] == "final" and g["checked_by"] for g in games.values())
    by_id = {r["game_id"]: r for r in rows}
    played = {r["game_id"] for r in rows if r["date"] <= "2026-11-20" and r["status"] != "cancelled"}
    assert set(games) | set(drafts) == played                      # every past, uncancelled game has a file
    assert not set(games) & set(drafts)
    assert all(by_id[i]["home"] == g["home"] and by_id[i]["away"] == g["away"] for i, g in games.items())


def test_the_past_season_is_finished(sport):
    files = generate(sport, SEASONS[1])
    rows = list(csv.DictReader(io.StringIO(files["schedule.csv"])))
    games = {n[len("games/"):-4] for n in files if n.startswith("games/")}
    assert not any(n.startswith("drafts/") for n in files)
    assert {r["game_id"] for r in rows} == games
    assert not any(r["status"] or r["moved_from"] for r in rows)
    team_ids = {t[0] for t in sport.sample.TEAMS}
    assert all(r["home"] in team_ids and r["away"] in team_ids for r in rows)


def test_the_sample_players_are_made_up_first_names_with_an_initial(sport):
    from scripts.core.fmt import is_first_last
    players = parse_yaml(generate(sport, SEASONS[0])["players.yml"])
    assert len(players) >= 5 * len(sport.sample.TEAMS) and all(is_first_last(p["name"]) for p in players)
    assert len({p["id"] for p in players}) == len(players)
    assert any(p.get("number") == "00" for p in players), "a jersey 00 exercises the strict loader"
    assert any(p.get("team") is None and p.get("sub") is True for p in players)


# ------------------------------------------------------------------ paths that point somewhere

def walk(node, path=()):
    """Every path in a sheet (containers and leaves), as tuples."""
    yield path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, path + (i,))


def get(node, path):
    for key in path:
        if isinstance(node, dict):
            node = next((v for k, v in node.items() if str(k) == str(key)), KeyError)
            if node is KeyError:
                raise KeyError(key)
        elif isinstance(node, list) and str(key).isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            raise KeyError(key)
    return node


def resolves(sheet, at):
    """The path leads to a node, or to a missing key whose parent exists (a dict or a list)."""
    if at == "":
        return True
    parts = at.split(".")
    if "" in parts:
        return False
    try:
        get(sheet, parts)
        return True
    except KeyError:
        pass
    try:
        return isinstance(get(sheet, parts[:-1]), (dict, list))
    except KeyError:
        return False


def mutations(sheet):
    """Broken copies of a sheet: each node deleted, emptied, made negative, text, a block, a list; each block
    given an unknown key."""
    for path in walk(sheet):
        if not path:
            continue
        for how in ("delete", "none", "minus", "text", "block", "list"):
            copy_ = copy.deepcopy(sheet)
            parent = get(copy_, path[:-1])
            if how == "delete":
                del parent[path[-1]]
            else:
                parent[path[-1]] = {"none": None, "minus": -1, "text": "x", "block": {}, "list": []}[how]
            yield f"{how} {path}", copy_
    for path in walk(sheet):
        if isinstance(get(sheet, path), dict):
            copy_ = copy.deepcopy(sheet)
            get(copy_, path)["zzz"] = 1
            yield f"unknown key under {path}", copy_
    yield "not a block", "hello"
    yield "empty", {}
    yield "none", None


def collected(sport, choose=None):
    got = []
    generate(sport, SEASONS[0], choose, collect=got)
    return got


def test_every_problem_path_points_into_the_file_and_nothing_is_changed(sport):
    for choose in variants(sport):
        samples = collected(sport, choose)
        assert samples
        for sheet, ctx, _ in samples[:: max(1, len(samples) // 4)]:
            for folder in ("games", "drafts"):
                ctx = replace(ctx, folder=folder)
                for what, broken in mutations(sheet):
                    sheet_before, ctx_before = copy.deepcopy(broken), copy.deepcopy(ctx)
                    problems = call_sport("check", sport.rules.check, broken, ctx)
                    assert broken == sheet_before and ctx == ctx_before, f"check() changed its input ({what})"
                    for p in problems:
                        assert resolves(broken, p.at), f"{sport.id}: {what}: {p.at!r} is not in the sheet ({p.message})"
                        assert p.message and p.message == p.message.strip()


def test_a_draft_is_never_stricter_than_a_finished_sheet(sport):
    sheet, ctx, _ = collected(sport)[0]
    for what, broken in mutations(sheet):
        final = call_sport("check", sport.rules.check, broken, replace(ctx, folder="games"))
        draft = call_sport("check", sport.rules.check, broken, replace(ctx, folder="drafts"))
        assert sum(p.level == "error" for p in draft) <= sum(p.level == "error" for p in final), what


# ------------------------------------------------------------------ present, read, derive

def test_present_uses_only_known_blocks_and_cell_flags_and_changes_nothing(sport):
    for choose in variants(sport):
        for sheet, ctx, _ in collected(sport, choose):
            ctx_before = copy.deepcopy(ctx)
            sheet_before = copy.deepcopy(sheet)
            reading = call_sport("read", sport.rules.read, sheet, ctx)
            assert isinstance(reading, Reading)
            reading_before = copy.deepcopy(reading)
            shown = call_sport("present", sport.rules.present, reading, ctx)
            assert sheet == sheet_before and ctx == ctx_before and reading == reading_before
            assert set(shown) <= set(PRESENT_KEYS)
            assert all(block["type"] in BLOCK_TYPES for block in shown.get("blocks", []))
            line = shown.get("line_score")
            if line:
                assert set(line["rows"]) == {"home", "away"}
                for column in line["columns"]:
                    assert set(column) <= LINE_COLUMN_KEYS
                for row in line["rows"].values():
                    assert len(row["cells"]) == len(line["columns"])
                    for cell in row["cells"]:
                        assert set(cell) <= LINE_CELL_KEYS and "v" in cell
                        assert all(cell[flag] is True for flag in cell if flag != "v")
            for side, path in reading.score.final_at.items():
                assert path.startswith("sheet.") and resolves({"sheet": sheet}, path), (side, path)


def test_derive_gives_only_declared_stats_and_changes_nothing(sport):
    spec = sport.spec
    declared = {s["key"] for s in spec["stats"]["derived"]}
    for group in (g for g in spec["stats"] if g not in STAT_RESERVED):
        keys = [s["key"] for s in spec["stats"][group]]
        for games in (0, 1, 7):
            counts = {"gp": games, **{key: 5 * (i + 1) for i, key in enumerate(keys)}}
            before = dict(counts)
            got = call_sport("derive", sport.rules.derive, counts, group)
            assert counts == before and set(got) <= declared


def test_the_sample_function_changes_nothing_it_is_given(sport):
    import random
    for sheet, ctx, game in collected(sport)[:6]:
        assert isinstance(game, SampleGame)
        ctx_before, game_before = copy.deepcopy(ctx), copy.deepcopy(game)
        again = sport.sample.sheet(random.Random(3), game, ctx)
        assert ctx == ctx_before and game == game_before
        assert call_sport("check", sport.rules.check, again, ctx) == []


# ------------------------------------------------------------------ the files on disk

def test_the_committed_sample_data_is_what_make_sample_writes():
    made = make_sample.generate_all(ROOT)
    assert sorted(made) == ["sample-2025-26", "sample-2026-27"]
    assert make_sample.differences(ROOT, made) == []


def test_make_sample_writes_the_same_bytes_every_time_and_the_loader_finds_nothing(tmp_path):
    for name in ("league.yml",):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "sports", tmp_path / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "data").mkdir()
    shutil.copy(ROOT / "data" / "seasons.yml", tmp_path / "data" / "seasons.yml")
    shutil.copytree(ROOT / "data" / "2026-27", tmp_path / "data" / "2026-27")
    assert make_sample.main(["--root", str(tmp_path), "--no-loader"]) == 0
    first = {s: make_sample.files_on_disk(tmp_path / "data" / s) for s in ("sample-2026-27", "sample-2025-26")}
    assert make_sample.main(["--root", str(tmp_path), "--no-loader"]) == 0
    assert first == {s: make_sample.files_on_disk(tmp_path / "data" / s) for s in first}
    assert make_sample.main(["--root", str(tmp_path), "--check"]) == 0
    assert first == {s: make_sample.generate_all(tmp_path)[s] for s in first}
    assert make_sample.run_loader(tmp_path) == []


def test_the_loader_finds_no_problem_in_the_written_sample_season():
    """The final check of package 2: the real data folder (the empty current season, the sample stand-in and
    the past sample season) loads with ZERO problems, warnings included."""
    assert make_sample.run_loader(ROOT) == []
