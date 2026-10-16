"""Basketball against the Masters site it was ported from (docs/stage-5-basketball-spec.md, section 8). LOCAL ONLY.

    MASTERS_SITE=/path/to/tb-masters-basketball/website python -m pytest tests/test_masters_parity.py -s

Skipped unless MASTERS_SITE names a checkout of the Masters repository, and never needed in CI (the Masters repo
is a reference, not a dependency). Nothing is written into that checkout (a test checks), and nothing converted
from its data is written outside pytest's temporary folders. `-s` shows the report of known differences at the end.

What is compared

1. The Masters sheet fixtures (tests/fixtures/sheets/*): each is converted, checked by the basketball rules,
   and our problems must have the same levels at the mapped paths as the `expected.json` Masters keeps for it,
   and our numbers must equal Masters' lines.
2. The Masters data (`data/`, every season): Masters' own `build_stats.py` and our converter + `scripts/build.py`
   (with the Masters preset of spec 3.4 in league.yml) are run on the same files, and per season the test compares
   the standings (GP W L T PTS PF PA QW, and the order where no name or head-to-head-skip tiebreak was used),
   every player's GP PTS FTM FTA PPG FT% techs and flagrants, the leaderboards (values and ranks; the order inside
   a rank is ignored) and every game's quarter scores and final.

Known differences are listed in KNOWN below, each with the reason; the test passes when every difference found is
a listed one, and the report prints how many of each were seen. A difference that is not listed fails the test.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASKETBALL = ROOT / "sports" / "basketball"
MASTERS_SITE = os.environ.get("MASTERS_SITE", "").strip()

pytestmark = [
    pytest.mark.skipif(not MASTERS_SITE, reason="local only: set MASTERS_SITE to a checkout of "
                                                "tb-masters-basketball/website to compare with the Masters site"),
    pytest.mark.skipif(not (BASKETBALL / "rules.py").is_file(), reason="the basketball sport folder is not here yet"),
]

# --------------------------------------------------------------------------- the known differences

# Each key: why the two sites differ (spec section and reason). `found` counts what the run saw; a difference whose
# key is not here is a failure, so a new one cannot hide.
KNOWN = {
    "standings-name-order": (
        "3.4",
        "Teams still level after the last tiebreaker share a rank in scorers-table; Masters ordered them by name. "
        "The order inside such a group is not compared."),
    "standings-h2h-rule": (
        "3.4",
        "Head-to-head is skipped unless every pair of tied teams has met (Masters: unless each tied team has met at "
        "least one of the others). Where the two rules disagree the order inside the group is not compared."),
    "zero-points-unranked": (
        "4.2",
        "A player who played but scored 0 is on Masters' Points (and PPG) lists but not on scorers-table's boards: the "
        "core ranks a 0 only where a board says zero: true (FT% does). They would be last, so no one else's rank moves."),
    "order-inside-a-rank": (
        "4.2",
        "Inside a shared rank Masters lists players by points, then name; the core lists equal values by player label "
        "('#38 Terry N.' before '#5 Mark D.': the jersey number, as text, comes first; spec 4.2 says 'by name'). "
        "Ranks and values are the same; only the order inside a shared rank differs. Not compared."),
    "no-games-dash": (
        "4.3",
        "A team that has not played shows PF and PA as a dash (null in the JSON) where Masters showed 0."),
    "forfeit-no-line-score": (
        "3.3",
        "A forfeit has no sheet, so its game page has no line score (Masters showed 1-1-1-1 for the winner and 0 "
        "for the loser). The final score and the standings points (7 under the preset) are compared and agree."),
    "review-warnings": (
        "2.2",
        "Masters reports one warning per `review` entry, at the box it names; the core reports one warning, at "
        "`review`, for a draft that still has review notes."),
}

FOUND: Counter = Counter()
COMPARED: Counter = Counter()        # what the run looked at, so a pass can be seen to mean something
DETAILS: dict[str, list[str]] = defaultdict(list)


def known(key: str, detail: str) -> None:
    assert key in KNOWN, key
    FOUND[key] += 1
    if len(DETAILS[key]) < 6:
        DETAILS[key].append(detail)


# --------------------------------------------------------------------------- helpers

def _snapshot(site: Path) -> dict:
    """Name, size and mtime of every file in the places the Masters build could write to."""
    seen = {}
    for sub in ("scripts", "data", "_data", "_games", "_players", "_teams", "_archive", "calendar", "sheets", "enter"):
        for path in (site / sub).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                st = path.stat()
                seen[path.relative_to(site).as_posix()] = (st.st_size, st.st_mtime_ns)
    return seen


def _round1(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _load_module(path: Path, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


convert_masters = _load_module(BASKETBALL / "convert_masters.py", "convert_masters_parity")

PRESET_LEAGUE = (
    "name: Masters Parity League\nsport: basketball\ntimezone: America/Toronto\nsample_data: @SAMPLE@\n"
    "preview: false\n"
    # the preset as the converter prints it, with PF and PA added to the columns so they can be compared
    + convert_masters.MASTERS_PRESET.replace("columns: [gp, w, l, t, pw, pts, diff]",
                                             "columns: [gp, w, l, t, pw, pts, pf, pa, diff]"))


def make_root(folder: Path, sample: bool = False) -> Path:
    """A repository root of its own: a league.yml with the Masters preset, and this repository's sports/."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "league.yml").write_text(PRESET_LEAGUE.replace("@SAMPLE@", str(sample).lower()), encoding="utf-8")
    link = folder / "sports"
    if not link.exists():
        link.symlink_to(ROOT / "sports")
    return folder


@pytest.fixture(scope="module")
def site():
    path = Path(MASTERS_SITE).expanduser().resolve()
    if not (path / "scripts" / "build_stats.py").is_file() or not (path / "data" / "seasons.yml").is_file():
        pytest.fail(f"MASTERS_SITE={MASTERS_SITE!r} is not a checkout of tb-masters-basketball/website "
                    "(no scripts/build_stats.py or data/seasons.yml)")
    before = _snapshot(path)
    yield path
    assert _snapshot(path) == before, "the parity run changed files inside the Masters checkout"


# --------------------------------------------------------------------------- 1. the sheet fixtures

def _fixture_cases(site: Path) -> list[str]:
    folder = site / "tests" / "fixtures" / "sheets"
    return sorted(p.name for p in folder.iterdir() if (p / "sheet.yml").exists()) if folder.is_dir() else []


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames:
        folder = Path(MASTERS_SITE).expanduser() / "tests" / "fixtures" / "sheets" if MASTERS_SITE else None
        cases = sorted(p.name for p in folder.iterdir() if (p / "sheet.yml").exists()) \
            if folder is not None and folder.is_dir() else []
        metafunc.parametrize("case", cases)


@pytest.fixture(scope="module")
def sport_and_league(tmp_path_factory):
    """The basketball sport and the league settings of the Masters preset."""
    from scripts.core.config import load_league
    from scripts.core.sports import load_sport
    root = make_root(tmp_path_factory.mktemp("preset-root"))
    league, problems = load_league(root / "league.yml", sports_root=root / "sports", root=root)
    assert league is not None, problems
    sport, found = load_sport("basketball", root / "sports", root=root)
    assert sport is not None, found
    return sport, league


def _converted_fixture(site: Path, case: str, tmp: Path, folder: str):
    """The fixture's sheet, converted by the converter into scorers-table's shape, with its teams and players."""
    src = site / "tests" / "fixtures" / "sheets"
    data = tmp / "masters"
    season = data / "2026-27"
    (season / folder).mkdir(parents=True)
    (data / "seasons.yml").write_text("- {id: 2026-27, label: '2026-27', current: true}\n", encoding="utf-8")
    for name in ("teams.yml", "players.yml", "schedule.csv"):
        (season / name).write_text((src / "season" / name).read_text(encoding="utf-8"), encoding="utf-8")
    sheet = yaml.safe_load((src / case / "sheet.yml").read_text(encoding="utf-8"))
    (season / folder / f"{sheet['game_id']}.yml").write_text((src / case / "sheet.yml").read_text(encoding="utf-8"),
                                                              encoding="utf-8")
    out = tmp / "converted"
    result = convert_masters.convert(data, out)
    converted = yaml.safe_load((out / "2026-27" / folder / f"{sheet['game_id']}.yml").read_text(encoding="utf-8"))
    return sheet, converted, out / "2026-27", result


def _context(sport, league, season_dir: Path, converted: dict, folder: str, game_type: str):
    from scripts.core.loader import load_players, load_teams
    from scripts.core.model import SportContext
    teams, problems = load_teams(season_dir / "teams.yml", "teams.yml")
    assert not problems, problems
    players, problems = load_players(season_dir / "players.yml", "players.yml", teams, sport)
    assert not problems, problems
    return SportContext(sport.spec, league.rules, teams, players, {"home": converted["home"], "away": converted["away"]},
                        game_type, folder)


def _map_masters_at(at: str, masters_game: dict) -> str:
    sides = {masters_game.get("home"): "home", masters_game.get("away"): "away"}
    mapped = convert_masters.map_review_path(at, sides)
    return mapped[len("sheet."):] if mapped.startswith("sheet.") else mapped


def test_the_fixture_cases_are_there(site):
    assert len(_fixture_cases(site)) >= 10, "the Masters sheet fixtures are missing"


def test_fixture(site, sport_and_league, case, tmp_path):
    """Same levels at the mapped paths as Masters' expected.json; and our numbers are Masters' lines."""
    sport, league = sport_and_league
    expected = json.loads((site / "tests" / "fixtures" / "sheets" / case / "expected.json").read_text(encoding="utf-8"))
    folder = expected.get("folder", "games")
    sheet, converted, season_dir, _ = _converted_fixture(site, case, tmp_path, folder)
    COMPARED["sheet fixtures"] += 1
    if "forfeit" in sheet:
        # A forfeit is the core's: the file has the envelope and no sheet, and the notes are left out and printed.
        assert converted.get("forfeit") == sheet["forfeit"] and "sheet" not in converted and "notes" not in converted
        assert expected["game"]["forfeit"] == sheet["forfeit"] and expected["game"]["lines"] == []
        return
    schedule_type = "regular"
    ctx = _context(sport, league, season_dir, converted, folder, schedule_type)
    problems = sport.rules.check(converted["sheet"], ctx)

    ours = Counter((p.level, p.at) for p in problems)
    theirs = Counter()
    for p in expected["problems"]:
        if p["at"] and p["message"].startswith("to review:"):
            known("review-warnings", f"{case}: {p['at']}")
            continue
        if p["at"] in ("checked_by", "status", "game_id", "form", "review", "home", "away", "forfeit"):
            continue                                       # the header: the core's checks, not the sport's
        theirs[(p["level"], _map_masters_at(p["at"], sheet))] += 1
    assert ours == theirs, (f"{case}: problems differ\n  ours:   {sorted(ours.items())}\n"
                            f"  masters: {sorted(theirs.items())}")

    if expected["game"] is None:
        assert any(p.level == "error" for p in problems)
        return
    assert not any(p.level == "error" for p in problems), problems
    reading = sport.rules.read(converted["sheet"], ctx)
    game = expected["game"]
    home, away = sheet["home"], sheet["away"]
    side_of = {home: "home", away: "away"}
    assert reading.score.final == {side_of[t]: v for t, v in game["final"].items()}, case
    for tid, quarters in game["quarters"].items():
        running = reading.score.periods[side_of[tid]]
        per = [quarters[0]] + [b - a for a, b in zip(quarters, quarters[1:])]
        assert running == per, case
    assert (reading.score.decided_in == "overtime") == bool(game["ot"]), case
    mine = {l.player: (l.side, l.counts) for l in reading.lines}
    assert set(mine) == {l["player"] for l in game["lines"]}, case
    for line in game["lines"]:
        side, counts = mine[line["player"]]
        assert side == side_of[line["team"]]
        for key in ("pts", "ftm", "fta", "pf", "tech", "flagrant"):
            assert counts[key] == line[key], (case, line["player"], key)
    if game.get("tie") is not None:
        assert (reading.score.final["home"] == reading.score.final["away"]) == bool(game["tie"]), case


_MASTERS_DRAFTS = """
import json, pathlib, sys
sys.dont_write_bytecode = True
site = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(site / "scripts"))
import yaml, build_stats, sheet_rules
out = {}
for season in yaml.safe_load((site / "data" / "seasons.yml").read_text(encoding="utf-8")):
    folder = site / "data" / season["id"]
    problems = []
    teams = build_stats.load_teams(folder, problems)
    players = build_stats.load_players(folder, teams, problems)
    schedule = build_stats.load_schedule(folder, teams, problems)
    for path in sorted((folder / "drafts").glob("*.yml")) if (folder / "drafts").is_dir() else []:
        sheet = yaml.safe_load(path.read_text(encoding="utf-8"))
        ctx = {"stem": path.stem, "folder": "drafts", "teams": teams, "players": players, "schedule": schedule}
        out[season["id"] + "/" + path.name] = sheet_rules.check(sheet, ctx)[1]
print(json.dumps(out))
"""


def test_the_drafts_in_the_masters_data(site, sport_and_league, tmp_path):
    """Drafts are never built, so the build comparison below does not see them: run Masters' check and ours on each
    draft (the sample seasons' two, and any the real season has) and compare levels at the mapped paths."""
    sport, league = sport_and_league
    done = subprocess.run([sys.executable, "-c", _MASTERS_DRAFTS, str(site)], capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    theirs_by_file = json.loads(done.stdout)
    out = tmp_path / "converted"
    convert_masters.convert(site / "data", out)
    from scripts.core.loader import load_players, load_teams
    from scripts.core.model import SportContext
    compared = 0
    for key, theirs in theirs_by_file.items():
        sid, name = key.split("/")
        folder = out / sid
        teams, found = load_teams(folder / "teams.yml", "teams.yml")
        players, more = load_players(folder / "players.yml", "players.yml", teams, sport)
        assert not found and not more, (found, more)
        game = yaml.safe_load((folder / "drafts" / name).read_text(encoding="utf-8"))
        masters_game = yaml.safe_load((site / "data" / sid / "drafts" / name).read_text(encoding="utf-8"))
        ctx = SportContext(sport.spec, league.rules, teams, players, {"home": game["home"], "away": game["away"]},
                           "regular", "drafts")
        ours = Counter((p.level, p.at) for p in sport.rules.check(game["sheet"], ctx))
        want = Counter()
        for p in theirs:
            if p["message"].startswith("to review:"):
                known("review-warnings", f"{key}: {p['at']}")
            elif p["at"] not in ("checked_by", "status", "game_id", "form", "review", "home", "away", "forfeit"):
                want[(p["level"], _map_masters_at(p["at"], masters_game))] += 1
        assert ours == want, f"{key}: problems differ\n  ours {sorted(ours.items())}\n  masters {sorted(want.items())}"
        COMPARED["drafts"] += 1
        compared += 1
    assert compared


# --------------------------------------------------------------------------- 2. the Masters data, built twice

def _fixture_games_dataset(site: Path, tmp: Path) -> Path:
    """A Masters data folder made of the sheet fixtures that are valid final games, one game a week between aa and
    bb: overtime, a tie after overtime, a game over 100 points, a forfeit, a free-throw warning, plus a playoff game
    (the clean sheet again). Every shape the Masters sample seasons do not have, run through both builds."""
    import datetime as dt
    src = site / "tests" / "fixtures" / "sheets"
    data = tmp / "fixture-data"
    season = data / "2026-27"
    (season / "games").mkdir(parents=True)
    (data / "seasons.yml").write_text(
        "- {id: 2026-27, label: '2026-27', current: true, gym: Test Gym, ppg_min_games: 0, ft_min_attempts: 5}\n",
        encoding="utf-8")
    for name in ("teams.yml", "players.yml"):
        (season / name).write_text((src / "season" / name).read_text(encoding="utf-8"), encoding="utf-8")
    cases = []
    for case in sorted(p.name for p in src.iterdir() if (p / "sheet.yml").exists()):
        expected = json.loads((p := src / case / "expected.json").read_text(encoding="utf-8"))
        if expected["game"] is not None and expected.get("folder", "games") == "games":
            cases.append((case, "regular"))
    cases.append(("clean", "playoff"))
    rows = ["game_id,date,time,gym,home,away,type,week,status,round"]
    for i, (case, kind) in enumerate(cases):
        day = dt.date(2026, 10, 17) + dt.timedelta(days=7 * i)
        gid = f"{day.isoformat()}-g1"
        text = (src / case / "sheet.yml").read_text(encoding="utf-8").replace("2026-10-17-g1", gid)
        (season / "games" / f"{gid}.yml").write_text(text, encoding="utf-8")
        rows.append(f"{gid},{day.isoformat()},09:45,,aa,bb,{kind},{i + 1},,{'Final' if kind == 'playoff' else ''}")
    (season / "schedule.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return data


def _tiebreak_dataset(tmp: Path) -> Path:
    """A Masters data folder of forfeits (the only games that need no sheet), arranged so that three teams finish
    level on points and two of them never met: aa beat cc, cc beat ee, ee beat dd. Masters uses head-to-head here
    (every tied team met at least one of the others); scorers-table skips it (not every pair met)."""
    data = tmp / "tiebreak-data"
    season = data / "2026-27"
    (season / "games").mkdir(parents=True)
    (data / "seasons.yml").write_text("- {id: 2026-27, label: '2026-27', current: true, gym: Test Gym}\n",
                                      encoding="utf-8")
    teams = ["aa", "cc", "dd", "ee"]
    (season / "teams.yml").write_text("".join(
        f"- {{id: {t}, name: Team {t.upper()}, short: {t.upper()}, colour_slot: {i + 1}}}\n" for i, t in enumerate(teams)),
        encoding="utf-8")
    (season / "players.yml").write_text("[]\n", encoding="utf-8")
    games = [("2026-10-17", "g1", "aa", "cc", "cc"), ("2026-10-17", "g2", "ee", "dd", "dd"),
             ("2026-10-24", "g1", "cc", "ee", "ee")]
    rows = ["game_id,date,time,gym,home,away,type,week,status,round"]
    for day, n, home, away, loser in games:
        gid = f"{day}-{n}"
        week = 1 if day == "2026-10-17" else 2
        rows.append(f"{gid},{day},{'09:45' if n == 'g1' else '11:15'},,{home},{away},regular,{week},,")
        (season / "games" / f"{gid}.yml").write_text(
            f"game_id: {gid}\nform: MBL-SS6\nstatus: final\nhome: {home}\naway: {away}\nforfeit: {loser}\n"
            "checked_by: Lee M.\n", encoding="utf-8")
    (season / "schedule.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return data


@pytest.fixture(scope="module", params=["masters-data", "fixture-games", "tiebreaks"])
def runs(request, site, tmp_path_factory):
    """Masters' build_stats.py and our converter + build.py on the same data. Returns the two computed folders."""
    tmp = tmp_path_factory.mktemp("parity")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    masters_data = {"masters-data": lambda: site / "data", "fixture-games": lambda: _fixture_games_dataset(site, tmp),
                    "tiebreaks": lambda: _tiebreak_dataset(tmp)}[request.param]()
    # ---- Masters, into a folder of ours (its --root gets the stub pages and calendars)
    (tmp / "m-root").mkdir()
    config = tmp / "m-config.yml"
    config.write_text("sample_data: false\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(site / "scripts" / "build_stats.py"), "--data", str(masters_data),
                           "--out", str(tmp / "m-out"), "--root", str(tmp / "m-root"), "--config", str(config)],
                          capture_output=True, text=True, env=env, cwd=tmp)
    assert done.returncode == 0, f"the Masters build failed:\n{done.stdout}\n{done.stderr}"
    # ---- ours: converted data, built in real mode (the current season) and in sample mode (the sample seasons)
    data = tmp / "o-data"
    result = convert_masters.convert(masters_data, data)
    seasons = yaml.safe_load((masters_data / "seasons.yml").read_text(encoding="utf-8"))
    modes = [("real", False)] + ([("sample", True)] if any(s.get("sample") for s in seasons) else [])
    ours = {}
    for mode, sample in modes:
        root = make_root(tmp / f"o-root-{mode}", sample=sample)
        out = tmp / f"o-out-{mode}"
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "--root", str(root), "--data", str(data),
                               "--out", str(out), "--today", "2027-06-01"],
                              capture_output=True, text=True, env=env, cwd=tmp)
        assert done.returncode == 0, f"our build failed ({mode} mode):\n{done.stdout}\n{done.stderr}"
        ours[mode] = out / "_data" / "computed"
    return {"name": request.param, "masters": tmp / "m-out", "ours": ours, "seasons": seasons, "converted": result,
            "forfeits": sum(1 for f in result.omitted if "a forfeit has no sheet" in f)}


def _seasons_to_compare(runs):
    """[(season id, masters folder, our folder)] for every season both sides computed."""
    pairs = []
    for s in runs["seasons"]:
        sid = s["id"]
        mine = next((d / sid for d in runs["ours"].values() if (d / sid / "standings.json").is_file()), None)
        if mine is not None and (runs["masters"] / sid / "standings.json").is_file():
            pairs.append((sid, runs["masters"] / sid, mine))
    return pairs


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_masters_season_is_compared(runs):
    ids = [sid for sid, _, _ in _seasons_to_compare(runs)]
    expected = [s["id"] for s in runs["seasons"]]
    assert ids == expected, f"seasons not computed by both sites: {sorted(set(expected) - set(ids))}"


# ---- standings

def _regular_pairs(masters_dir: Path) -> set:
    games = _json(masters_dir / "games.json")
    return {frozenset((g["home"], g["away"])) for g in games.values() if g["type"] == "regular"}


def test_standings(runs):
    compared = 0
    for sid, mdir, odir in _seasons_to_compare(runs):
        theirs = _json(mdir / "standings.json")["teams"]
        ours = {r["team"]: r for r in _json(odir / "standings.json")["rows"]}
        assert set(ours) == {t["team"] for t in theirs}, sid
        for t in theirs:
            v = ours[t["team"]]["values"]
            want = {"gp": t["gp"], "w": t["w"], "l": t["l"], "t": t["t"], "pts": t["points"], "pf": t["pf"],
                    "pa": t["pa"], "pw": t["qw"]}
            got = {k: v.get(k) for k in want}
            if t["gp"] == 0 and got["pf"] is None and got["pa"] is None:
                known("no-games-dash", f"{sid} {t['team']}: PF and PA are blank, not 0")
                got["pf"] = got["pa"] = 0
            assert got == want, f"{sid} {t['team']}: standings numbers differ\n  ours {got}\n  masters {want}"
            compared += 1
            COMPARED["standings rows"] += 1
        # the order, where the tiebreak rules agree
        pairs = _regular_pairs(mdir)
        by_points = defaultdict(list)
        for t in theirs:
            by_points[t["points"]].append(t)
        order_ours = [r["team"] for r in _json(odir / "standings.json")["rows"]]
        start = 0
        for points in sorted(by_points, reverse=True):
            group = by_points[points]
            size = len(group)
            teams = [t["team"] for t in group]
            window = order_ours[start:start + size]
            start += size
            assert set(window) == set(teams), f"{sid}: teams on {points} points are not together in our table"
            if size == 1:
                continue
            by_name = any(t["tiebreak"] == "name" for t in group)
            masters_h2h = all(any(frozenset((a, b)) in pairs for b in teams if b != a) for a in teams)
            ours_h2h = all(frozenset((a, b)) in pairs for a in teams for b in teams if a < b)
            if by_name:
                known("standings-name-order", f"{sid}: {teams} level on {points} after every tiebreak")
                continue
            if masters_h2h != ours_h2h:
                known("standings-h2h-rule", f"{sid}: {teams} on {points}: Masters head-to-head "
                                            f"{'used' if masters_h2h else 'skipped'}, ours {'used' if ours_h2h else 'skipped'}")
                continue
            assert window == teams, f"{sid}: order of {teams} on {points} points differs: ours {window}"
    assert compared


# ---- players

def _ours_players(odir: Path) -> dict:
    return _json(odir / "players.json")


def _group_totals(player: dict, playoffs: bool = False) -> dict:
    if playoffs:
        return ((player.get("playoffs") or {}).get("player") or {}).get("totals") or {}
    return ((player.get("groups") or {}).get("player") or {}).get("totals") or {}


def test_player_totals(runs):
    compared = 0
    for sid, mdir, odir in _seasons_to_compare(runs):
        theirs = _json(mdir / "players.json")
        ours = _ours_players(odir)
        playoff_theirs = _json(mdir / "playoffs.json")["players"]
        assert set(ours) == set(theirs), f"{sid}: different players"
        for pid, m in theirs.items():
            t = _group_totals(ours[pid])
            playoff = _group_totals(ours[pid], playoffs=True)
            mine = {
                "gp": t.get("gp", 0), "pts": t.get("pts", 0), "ftm": t.get("ftm", 0), "fta": t.get("fta", 0),
                "ppg": t.get("ppg"), "ft_pct": t.get("ft_pct"),
                "tech": t.get("tech", 0) + playoff.get("tech", 0),
                "flagrant": t.get("flagrant", 0) + playoff.get("flagrant", 0),
            }
            want = {k: m[k] for k in ("gp", "pts", "ftm", "fta", "ppg", "ft_pct", "tech", "flagrant")}
            assert mine == want, f"{sid} {pid}: totals differ\n  ours {mine}\n  masters {want}"
            compared += 1
            COMPARED["players"] += 1
        assert playoff_theirs is not None
    assert compared or runs["name"] == "tiebreaks"          # that dataset has forfeits only: no player has a game


# ---- leaderboards

def _board(odir: Path, stat: str) -> list:
    leaders = _json(odir / "leaders.json")
    boards = [b for b in leaders["boards"] if b["stat"] == stat]
    assert len(boards) == 1, f"no single leaderboard for {stat!r} in {odir}"
    return boards[0]["rows"]


def _compare_board(sid, name, stat, odir, masters_rows, value_of, rank_of=lambda r: r["rank"], zero_unranked=True):
    """A leaderboard against Masters': the rows our board shows (the top LEADERS_SHOWN ranks) and, for everyone, the
    rank on the player's page. Values and ranks; the order inside a rank is ignored. A 0 that Masters ranks and the
    core does not is a listed difference (it would be last)."""
    from scripts.core.compute_stats import LEADERS_SHOWN
    shown = {r["player"]: (r["rank"], r["display"]) for r in _board(odir, stat)}
    players = _json(odir / "players.json")
    ranks = {pid: p["groups"]["player"]["ranks"][stat] for pid, p in players.items()
             if stat in (p.get("groups", {}).get("player", {}).get("ranks") or {})}
    want_shown, want_ranks = {}, {}
    for r in masters_rows:
        value = value_of(r)
        if zero_unranked and value in ("0", "0.0"):
            if r["id"] not in ranks:
                known("zero-points-unranked", f"{sid} {name}: {r['id']} has {value}")
                continue
        want_ranks[r["id"]] = rank_of(r)
        if rank_of(r) <= LEADERS_SHOWN:
            want_shown[r["id"]] = (rank_of(r), value)
    assert shown == want_shown, (f"{sid} {name}: the board differs\n  only ours {sorted(set(shown.items()) - set(want_shown.items()))}"
                                 f"\n  only masters {sorted(set(want_shown.items()) - set(shown.items()))}")
    if stat != "tech":                                    # a player's page ranks: the board with player_rank on
        assert ranks == want_ranks, (f"{sid} {name}: ranks differ\n  ours {sorted(set(ranks.items()) - set(want_ranks.items()))}"
                                     f"\n  masters {sorted(set(want_ranks.items()) - set(ranks.items()))}")
    ours_order = [r["player"] for r in _board(odir, stat)]
    masters_order = [r["id"] for r in masters_rows if r["id"] in shown]
    if ours_order != masters_order:
        known("order-inside-a-rank", f"{sid} {name}")


def _competition_ranks(rows, key):
    """Masters lists technical fouls most first with no ranks: equal counts share a rank (1, 1, 3...)."""
    out, prev, rank = [], None, 0
    for i, r in enumerate(rows, start=1):
        if r[key] != prev:
            rank, prev = i, r[key]
        out.append({**r, "rank": rank})
    return out


def test_leaderboards(runs):
    compared = 0
    for sid, mdir, odir in _seasons_to_compare(runs):
        leaders = _json(mdir / "leaders.json")
        _compare_board(sid, "ppg", "ppg", odir, leaders["ppg"], lambda r: r["ppg_display"])
        _compare_board(sid, "pts", "pts", odir, leaders["points"], lambda r: str(r["pts"]))
        _compare_board(sid, "ft_pct", "ft_pct", odir, leaders["ft_pct"], lambda r: r["ft_pct_display"],
                       zero_unranked=False)
        _compare_board(sid, "tech", "tech", odir, _competition_ranks(leaders["technicals"], "tech"),
                       lambda r: str(r["tech"]), zero_unranked=False)
        compared += 1
        COMPARED["seasons with leaderboards"] += 1
    assert compared


# ---- games

def test_game_quarters_and_finals(runs):
    compared = 0
    for sid, mdir, odir in _seasons_to_compare(runs):
        theirs = _json(mdir / "games.json")
        ours = _json(odir / "games.json")
        assert set(ours) == set(theirs), f"{sid}: different games"
        for gid, m in theirs.items():
            o = ours[gid]
            assert (o["forfeit"] is not None) == (m["forfeit"] is not None), f"{sid} {gid}: forfeit differs"
            assert o["tie"] == m["tie"], f"{sid} {gid}: tie differs"
            if m["type"] == "regular":                     # Masters shows no standings points for a playoff game
                for side in ("home", "away"):
                    assert o["standings_points"][side] == m[f"{side}_team"]["standings_points"], \
                        f"{sid} {gid} {side}: standings points differ"
            for side in ("home", "away"):
                assert o[side]["score"] == m[f"{side}_team"]["score"], f"{sid} {gid} {side}: final differs"
            if o["line_score"] is None:
                assert m["forfeit"] is not None, f"{sid} {gid}: no line score"
                known("forfeit-no-line-score", f"{sid} {gid}: forfeit by {m['forfeit']}")
                compared += 1
                COMPARED["games"] += 1
                continue
            for side in ("home", "away"):
                mt, row = m[f"{side}_team"], o["line_score"]["rows"][side]
                cells = [c["v"] for c in row["cells"]]
                labels = [c["label"] for c in o["line_score"]["columns"]]
                if mt["ot"] is None:                       # Masters: None unless the game went to overtime
                    assert cells == mt["quarters"] and labels == ["Q1", "Q2", "Q3", "Q4"], \
                        f"{sid} {gid} {side}: quarters differ"
                else:                                      # ours: the overtime points are a fifth column, OT
                    assert cells == mt["quarters"] + [mt["ot"]] and labels == ["Q1", "Q2", "Q3", "Q4", "OT"], \
                        f"{sid} {gid} {side}: quarters or overtime differ"
                assert row["total"] == mt["score"], f"{sid} {gid} {side}: line score total differs"
            compared += 1
            COMPARED["games"] += 1
    assert compared


# ---- the report

def test_known_differences_report(runs):
    """Every difference found is one of KNOWN (the tests above fail otherwise). Printed with -s."""
    lines = ["", f"Masters parity ({runs['name']}): known differences seen so far in this run"]
    for key, (section, why) in KNOWN.items():
        lines.append(f"  [{key}] spec {section}: seen {FOUND[key]} time(s)")
        lines.append(f"      {why}")
        lines += [f"      e.g. {d}" for d in DETAILS[key]]
    lines.append("  compared so far: " + ", ".join(f"{n} {what}" for what, n in sorted(COMPARED.items())))
    print("\n".join(lines))
    assert set(FOUND) <= set(KNOWN)
