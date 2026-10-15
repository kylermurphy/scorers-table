"""The loader: reads `data/seasons.yml` and every season folder, checks all of it, and hands back what the rest
of the build computes from (docs/stage-4-spec.md, sections 2.2 to 2.4 and 4, stage 2 and 3).

    load_data(root, league, sport_def, *, today=None, data_dir=None) -> LoadedData

* Every file is read with `problems.read_yaml` (dates and leading-zero numbers arrive as text), every problem
  names its file and a path inside it (list rows count from 0; for `schedule.csv` row 0 is the first line
  under the header and the message adds the spreadsheet line), and ALL problems are reported, not the first.
* The sport's `check` and `read` are called through `call_sport`; a sport bug is an `InternalError` (exit 2)
  and is not caught here.
* `drafts/` is never opened. `games/<id>.yml` are finished sheets only.
* A season folder may be empty (a new league's current season): a missing `teams.yml`, `players.yml` or
  `schedule.csv` is the same as an empty one.

A season's teams, players, schedule rows and games are kept in the result even when other things are wrong,
except that a game file with any error is left out of `LoadedSeason.games` (so whoever computes from `games`
can trust each one). With errors in `LoadedData.problems`, the build stops before it computes anything.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.core.config import Settings, effective_settings
from scripts.core.fmt import is_first_last, parse_date, parse_time
from scripts.core.model import League, Player, Problem, Reading, SportContext, SportDef, Team
from scripts.core.problems import (
    Checker, call_sport, display_path, has_errors, join_path, read_yaml, suggest, with_prefix,
)

DATA_DIR_NAME = "data"
SEASONS_FILE = "seasons.yml"
SEASON_KEYS = ("id", "label", "current", "venue", "venue_address", "sample", "stands_in_for", "as_of", "overrides")
TEAM_KEYS = ("id", "name", "code", "slot", "colour")
PLAYER_KEYS = ("id", "name", "team", "number", "sub", "position")
SCHEDULE_REQUIRED = ("game_id", "date", "time", "home", "away")
SCHEDULE_COLUMNS = (*SCHEDULE_REQUIRED, "venue", "surface", "type", "round", "week", "status", "moved_from")
ENVELOPE_KEYS = ("game_id", "status", "home", "away", "checked_by", "scorekeeper", "notes", "review", "photo",
                 "forfeit", "sheet")
GAME_TYPES = ("regular", "playoff")
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".pdf")
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")
CODE_RE = re.compile(r"[A-Z0-9]{2,4}")
NUMBER_RE = re.compile(r"0|00|[1-9][0-9]?")
SLOTS = 6


# ------------------------------------------------------------------ what comes back

@dataclass(frozen=True)
class SeasonDef:
    """One entry of seasons.yml, checked."""
    id: str
    label: str
    index: int                              # its row in seasons.yml
    current: bool = False
    sample: bool = False
    stands_in_for: str | None = None
    as_of: dt.date | None = None            # "today" for a sample season
    venue: str | None = None
    venue_address: str | None = None
    overrides: Any = None                   # the raw `overrides:` map (already applied in `settings`)
    settings: Settings | None = None        # the league's settings with this season's overrides


@dataclass(frozen=True)
class ScheduleRow:
    """One row of schedule.csv, parsed. `home`/`away` are team ids, or free text on a playoff row whose teams
    are not known yet (`teams_known` says which)."""
    game_id: str
    date: dt.date
    time: dt.time
    home: str
    away: str
    row: int                                # index among the data rows (0 = first line under the header)
    line: int                               # spreadsheet line number
    venue: str | None = None                # None: the season's venue
    surface: str | None = None
    type: str = "regular"
    round: str | None = None
    week: int | None = None                 # the file's value, or counted from the regular-season dates
    status: str = ""                        # "" or "cancelled"
    moved_from: dt.date | None = None
    teams_known: bool = True

    @property
    def cancelled(self) -> bool:
        return self.status == "cancelled"


@dataclass(frozen=True)
class LoadedGame:
    """A finished game: the schedule row, the file's envelope and (unless forfeited) the sport's Reading."""
    id: str
    season: str
    file: str                               # "data/2026-27/games/2026-11-05-1.yml"
    row: ScheduleRow
    home: str                               # team ids, equal to the schedule row's
    away: str
    checked_by: str
    context: SportContext
    scorekeeper: str | None = None
    notes: tuple[str, ...] = ()
    photo: str | None = None                # path inside the season folder ("sheets/2026-11-05-1.jpg") or None
    forfeit: str | None = None              # the team id that forfeited
    sheet: dict | None = None
    reading: Reading | None = None


@dataclass(frozen=True)
class LoadedSeason:
    season: SeasonDef
    settings: Settings
    today: dt.date                          # the season's as_of for a sample season, else the real date
    teams: dict[str, Team]
    players: dict[str, Player]
    schedule: list[ScheduleRow]             # in file order
    games: dict[str, LoadedGame]            # game id -> game, in file-name order
    byes: dict[dt.date, tuple[str, ...]]    # regular-season day -> team ids with no game that day (worked out)
    folder: str                             # "data/2026-27"


@dataclass
class LoadedData:
    seasons: list[SeasonDef]                # seasons.yml, in order
    loaded: dict[str, LoadedSeason]         # season id -> contents
    active: str | None                      # the season every page shows (None when seasons.yml is wrong)
    shown: list[str]                        # active + the archive's seasons, in seasons.yml order
    today: dt.date                          # the real date in the league's time zone, or `today=`
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not has_errors(self.problems)


# ------------------------------------------------------------------ the entry point

def load_data(root: Path, league: League, sport_def: SportDef, *, today: dt.date | None = None,
              data_dir: Path | None = None) -> LoadedData:
    """Load and check `<root>/data/seasons.yml` and every season it lists. `root` is the repository root
    (problem files are shown relative to it); `data_dir` replaces `<root>/data`. `today` replaces the clock
    (tests). Returns everything it found plus ALL problems; nothing is written."""
    root = Path(root)
    data_dir = Path(data_dir) if data_dir else root / DATA_DIR_NAME
    today = today or dt.datetime.now(ZoneInfo(league.timezone)).date()
    seasons, problems = load_seasons(data_dir, root, league)
    loaded: dict[str, LoadedSeason] = {}
    for season in seasons:
        content, found = load_season(data_dir, root, season, league, sport_def, today)
        loaded[season.id] = content
        problems.extend(found)
    active = choose_active(seasons, league.sample_data)
    shown = shown_seasons(seasons, league.sample_data)
    problems.extend(check_unique_game_ids(loaded, shown))
    return LoadedData(seasons, loaded, active.id if active else None, shown, today, problems)


def choose_active(seasons: list[SeasonDef], sample_mode: bool) -> SeasonDef | None:
    """The season every page shows: the current one, or in sample mode the sample season that stands in for it."""
    current = next((s for s in seasons if s.current), None)
    if current is None:
        return None
    if sample_mode:
        stand_in = next((s for s in seasons if s.stands_in_for == current.id), None)
        if stand_in:
            return stand_in
    return current


def shown_seasons(seasons: list[SeasonDef], sample_mode: bool) -> list[str]:
    """Ids of the seasons the site shows, in seasons.yml order (spec 4.3): the active one, every past season,
    and other sample seasons only in sample mode. The real current season and its stand-in never both appear."""
    active = choose_active(seasons, sample_mode)
    if active is None:
        return []
    shown = []
    for s in seasons:
        if s.id == active.id:
            shown.append(s.id)
        elif s.current or s.stands_in_for:
            continue
        elif s.sample and not sample_mode:
            continue
        else:
            shown.append(s.id)
    return shown


# ------------------------------------------------------------------ seasons.yml

def load_seasons(data_dir: Path, root: Path, league: League) -> tuple[list[SeasonDef], list[Problem]]:
    """Check seasons.yml (spec 2.2). Returns the seasons that are usable (a valid, unique id and a folder)."""
    path = data_dir / SEASONS_FILE
    file = display_path(path, root)
    raw, problems = read_yaml(path, file)
    if problems:
        return [], problems
    c = Checker(file)
    items = c.sequence(raw if raw is not None else [], "")
    if items is not None and not items:
        c.error("", "lists no season. Add at least one, like '- {id: 2026-27, label: \"2026–27\", current: true}'.")
    seasons: list[SeasonDef] = []
    all_ids: set[str] = set()
    for i, item in enumerate(items or []):
        season = _season_entry(c, i, item, data_dir, league, file, seasons, all_ids)
        if season:
            seasons.append(season)
    if items:
        _season_rules(c, seasons, all_ids, league)
    return seasons, c.problems


def _season_entry(c: Checker, i: int, item: Any, data_dir: Path, league: League, file: str,
                  seen: list[SeasonDef], all_ids: set[str]) -> SeasonDef | None:
    at = str(i)
    if c.mapping(item, at, allowed=SEASON_KEYS, required=("id",)) is None:
        return None
    sid = c.ident(item["id"], join_path(at, "id")) if "id" in item else None
    usable = sid is not None
    if sid is not None:
        if sid in all_ids:
            c.error(join_path(at, "id"), f"{sid!r} is listed twice. Every season needs its own id.")
            usable = False
        all_ids.add(sid)
        if not (data_dir / sid).is_dir():
            c.error(join_path(at, "id"), f"{sid!r} has no folder. Create data/{sid}/ (it may be empty).")
            usable = False
    label = c.text(item["label"], join_path(at, "label")) if "label" in item else sid
    flags = {k: (c.boolean(item[k], join_path(at, k)) if k in item else False) for k in ("current", "sample")}
    if flags["current"] and flags["sample"]:
        c.error(join_path(at, "current"), "cannot be true for a sample season. A sample season is never the current one.")
    stands_in = c.ident(item["stands_in_for"], join_path(at, "stands_in_for")) if "stands_in_for" in item else None
    if "stands_in_for" in item and not flags["sample"]:
        c.error(join_path(at, "stands_in_for"), "only a sample season can stand in for another. Add 'sample: true' to this season.")
    as_of = _season_as_of(c, item, at, flags["sample"])
    venue, address = (c.text(item[k], join_path(at, k), allow_empty=(k == "venue_address")) if k in item else None
                      for k in ("venue", "venue_address"))
    settings, found = effective_settings(league, item.get("overrides"), file=file, at=join_path(at, "overrides"))
    c.problems.extend(found)
    if not usable:
        return None
    return SeasonDef(sid, label or sid, i, flags["current"], flags["sample"], stands_in, as_of, venue or None,
                     address or None, item.get("overrides"), settings)


def _season_as_of(c: Checker, item: dict, at: str, sample: bool) -> dt.date | None:
    if "as_of" not in item:
        return None
    path = join_path(at, "as_of")
    if not sample:
        c.error(path, "only a sample season has as_of ('today' for made-up data). Remove it, or add 'sample: true'.")
        return None
    value = parse_date(item["as_of"]) if isinstance(item["as_of"], str) else None
    if value is None:
        c.error(path, f"{item['as_of']!r} is not a date. Write it as YYYY-MM-DD, like 2026-11-20.")
    return value


def _season_rules(c: Checker, seasons: list[SeasonDef], all_ids: set[str], league: League) -> None:
    current = [s for s in seasons if s.current]
    if not current:
        c.error("", "has no current season. Exactly one season needs 'current: true'.")
    for extra in current[1:]:
        c.error(join_path(extra.index, "current"), f"{current[0].id!r} is already the current season. Exactly one season is current.")
    stand_ins: dict[str, str] = {}
    for s in seasons:
        target = s.stands_in_for
        if target is None:
            continue
        at = join_path(s.index, "stands_in_for")
        if target == s.id:
            c.error(at, "a season cannot stand in for itself.")
        elif target not in all_ids:
            c.error(at, f"{target!r} is not a season in this file. Use the id of the season it replaces.")
        elif any(o.id == target and o.sample for o in seasons):
            c.error(at, f"{target!r} is itself a sample season. A sample season stands in for a real one.")
        elif target in stand_ins:
            c.error(at, f"{stand_ins[target]!r} already stands in for {target!r}. At most one sample season does.")
        else:
            stand_ins[target] = s.id
    if league.sample_data and len(current) == 1 and current[0].id not in stand_ins:
        c.error("", f"has no sample season standing in for {current[0].id!r}, but sample_data is on in league.yml. "
                    f"Add a sample season with 'stands_in_for: {current[0].id}', or set sample_data: false.")


# ------------------------------------------------------------------ one season

def load_season(data_dir: Path, root: Path, season: SeasonDef, league: League, sport_def: SportDef,
                today: dt.date) -> tuple[LoadedSeason, list[Problem]]:
    folder = data_dir / season.id
    shown = display_path(folder, root)
    settings = season.settings or effective_settings(league)[0]
    teams, problems = load_teams(folder / "teams.yml", f"{shown}/teams.yml")
    players, found = load_players(folder / "players.yml", f"{shown}/players.yml", teams, sport_def)
    problems += found
    rows, found = load_schedule(folder / "schedule.csv", f"{shown}/schedule.csv", teams, sport_def)
    problems += found
    ctx = _GameContext(folder, shown, season, settings, sport_def, teams, players, {r.game_id: r for r in rows})
    games, found = load_games(ctx)
    problems += found
    content = LoadedSeason(season, settings, season.as_of if season.sample and season.as_of else today, teams, players,
                           rows, games, work_out_byes(rows, teams), shown)
    return content, problems


def _read_list(path: Path, file: str) -> tuple[list, list[Problem]]:
    """The rows of a YAML list file. A missing or empty file is an empty list (a new season has none yet)."""
    if not path.is_file():
        return [], []
    raw, problems = read_yaml(path, file)
    if problems:
        return [], problems
    c = Checker(file)
    items = c.sequence(raw if raw is not None else [], "")
    return items or [], c.problems


# ------------------------------------------------------------------ teams.yml

def load_teams(path: Path, file: str) -> tuple[dict[str, Team], list[Problem]]:
    items, problems = _read_list(path, file)
    c = Checker(file)
    c.problems.extend(problems)
    teams: dict[str, Team] = {}
    names: dict[str, int] = {}
    codes: dict[str, int] = {}
    row_of: dict[str, int] = {}
    for i, item in enumerate(items):
        if c.mapping(item, str(i), allowed=TEAM_KEYS, required=("id", "name", "code")) is None:
            continue
        tid = c.ident(item["id"], join_path(i, "id")) if "id" in item else None
        if tid in teams:
            c.error(join_path(i, "id"), f"{tid!r} is already a team id (row {row_of[tid]}). Ids must be unique.")
            tid = None
        name = c.text(item["name"], join_path(i, "name")) if "name" in item else None
        _unique(c, names, (name or "").strip().casefold(), i, "name", name)
        code = c.pattern(item["code"], join_path(i, "code"), CODE_RE, "2 to 4 capital letters or digits, like 'OTT'") \
            if "code" in item else None
        _unique(c, codes, code, i, "code", code)
        slot = c.integer(item["slot"], join_path(i, "slot"), 1, SLOTS) if "slot" in item else None
        colour = None
        if "colour" in item and c.pattern(item["colour"], join_path(i, "colour"), HEX_RE, "a colour like '#7A4A1E'"):
            colour = item["colour"].upper()
        if tid is not None:
            teams[tid] = Team(tid, name or tid, code or tid.upper()[:4], slot or (i % SLOTS) + 1, colour)
            row_of[tid] = i
    return teams, c.problems


def _unique(c: Checker, seen: dict[str, int], key: str | None, i: int, what: str, shown: str | None) -> None:
    if not key:
        return
    if key in seen:
        c.error(join_path(i, what), f"{shown!r} is already used by row {seen[key]}. Each team needs its own {what}.")
    else:
        seen[key] = i


# ------------------------------------------------------------------ players.yml

def load_players(path: Path, file: str, teams: dict[str, Team],
                 sport_def: SportDef) -> tuple[dict[str, Player], list[Problem]]:
    items, problems = _read_list(path, file)
    c = Checker(file)
    c.problems.extend(problems)
    players: dict[str, Player] = {}
    row_of: dict[str, int] = {}
    for i, item in enumerate(items):
        if c.mapping(item, str(i), allowed=PLAYER_KEYS, required=("id", "name")) is None:
            continue
        player = _player_row(c, i, item, teams, sport_def)
        if player is None:
            continue
        if player.id in players:
            c.error(join_path(i, "id"), f"{player.id!r} is already a player id (row {row_of[player.id]}). Ids must be unique.")
        else:
            players[player.id] = player
            row_of[player.id] = i
    _player_rules(c, players, row_of)
    return players, c.problems


def _player_row(c: Checker, i: int, item: dict, teams: dict[str, Team], sport_def: SportDef) -> Player | None:
    pid = c.ident(item["id"], join_path(i, "id")) if "id" in item else None
    name = None
    if "name" in item:
        if is_first_last(item["name"]):
            name = item["name"]
        else:
            c.error(join_path(i, "name"), f"{item['name']!r} should be 'First L.' (a first name and the last initial, "
                                          "never a full name).")
    sub = c.boolean(item["sub"], join_path(i, "sub")) if "sub" in item else False
    team = item.get("team")
    if team is not None:
        team = c.ident(team, join_path(i, "team"))
        if team is not None and team not in teams:
            hint = suggest(team, teams)
            c.error(join_path(i, "team"), f"{team!r} is not a team id in teams.yml." + (f" Did you mean {hint!r}?" if hint else ""))
    elif not sub:
        c.error(join_path(i, "team"), "is empty, so this player is a spare with no team. Give a team, or add 'sub: true'.")
    number = _player_number(c, i, item["number"]) if item.get("number") is not None else None
    position = _player_position(c, i, item["position"], sport_def) if "position" in item else None
    if pid is None:
        return None
    return Player(pid, name or "[placeholder]", team, number, bool(sub), position)


def _player_number(c: Checker, i: int, value: Any) -> str | None:
    text = str(value) if isinstance(value, int) and not isinstance(value, bool) else value
    if isinstance(text, str) and NUMBER_RE.fullmatch(text):
        return text
    c.error(join_path(i, "number"), f"{value!r} should be a jersey number from 0 to 99, or \"00\" in quotes.")
    return None


def _player_position(c: Checker, i: int, value: Any, sport_def: SportDef) -> str | None:
    positions = sport_def.spec.get("positions") or []
    at = join_path(i, "position")
    if not positions:
        c.error(at, f"is not used in {sport_def.name}: this sport has no positions. Remove the line.")
        return None
    return c.choice(value, at, positions)


def _player_rules(c: Checker, players: dict[str, Player], row_of: dict[str, int]) -> None:
    """Same 'First L.' on one team: both need numbers. Two regulars on a team cannot share a number."""
    by_name: dict[tuple, list[Player]] = {}
    by_number: dict[tuple, Player] = {}
    for p in players.values():
        if p.name != "[placeholder]":
            by_name.setdefault((p.team, p.name), []).append(p)
        if p.number is not None and not p.sub and p.team is not None:
            first = by_number.get((p.team, p.number))
            if first:
                c.error(join_path(row_of[p.id], "number"), f"{p.number} is already {first.name}'s number on {p.team} "
                        f"(row {row_of[first.id]}). Two regular players cannot share a number; mark a spare 'sub: true'.")
            else:
                by_number[(p.team, p.number)] = p
    for (team, name), group in by_name.items():
        if len(group) > 1:
            for p in (p for p in group if p.number is None):
                others = ", ".join(o.id for o in group if o is not p)
                c.error(join_path(row_of[p.id], "number"), f"is missing. {name!r} is also {others} on "
                        f"{team or 'no team'}; give each a jersey number so the site can tell them apart.")


# ------------------------------------------------------------------ schedule.csv

def load_schedule(path: Path, file: str, teams: dict[str, Team],
                  sport_def: SportDef) -> tuple[list[ScheduleRow], list[Problem]]:
    c = Checker(file)
    if not path.is_file():
        return [], []
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        c.error("", "is not saved as UTF-8 text. Export it again as 'CSV UTF-8'.")
        return [], c.problems
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    while header is not None and not any(cell.strip() for cell in header):
        header = next(reader, None)
    if header is None:
        return [], []
    columns = _check_header(c, [h.strip() for h in header])
    if columns is None:
        return [], c.problems
    rows: list[ScheduleRow] = []
    first_row: dict[str, int] = {}
    for i, cells in enumerate(reader):
        if not any(cell.strip() for cell in cells):
            continue                                    # a blank line in the middle of the sheet
        row = _schedule_row(c, i, reader.line_num, columns, cells, teams)
        if row is None:
            continue
        if row.game_id in first_row:
            c.error(join_path(i, "game_id"), f"{row.game_id!r} is already used on row {first_row[row.game_id]}"
                    f" (spreadsheet line {row.line}). Every game needs its own game_id.")
            continue
        first_row[row.game_id] = i
        rows.append(row)
    _check_games_per_day(c, rows, sport_def.spec.get("games_per_day", 1))
    return _number_weeks(rows), c.problems


def _check_header(c: Checker, header: list[str]) -> list[str] | None:
    ok = True
    for name in header:
        if name not in SCHEDULE_COLUMNS:
            hint = suggest(name, SCHEDULE_COLUMNS)
            c.error(join_path("header", name), f"{name!r} is not a column here." + (f" Did you mean {hint!r}?" if hint else "")
                    + f" Columns: {', '.join(SCHEDULE_COLUMNS)}.")
            ok = False
    for name in SCHEDULE_REQUIRED:
        if name not in header:
            c.error(join_path("header", name), f"is required. The first line must have a '{name}' column.")
            ok = False
    for name in dict.fromkeys(header):
        if header.count(name) > 1:
            c.error(join_path("header", name), f"column {name!r} is written twice in the first line.")
            ok = False
    return header if ok else None


def _schedule_row(c: Checker, i: int, line: int, columns: list[str], cells: list[str],
                  teams: dict[str, Team]) -> ScheduleRow | None:
    if len(cells) > len(columns) and any(x.strip() for x in cells[len(columns):]):
        c.error(str(i), f"has {len(cells)} cells but the first line names only {len(columns)} columns (spreadsheet line {line}).")
    cell = {name: (cells[k].strip() if k < len(cells) else "") for k, name in enumerate(columns)}
    problems_before = len(c.problems)

    def err(column: str, message: str) -> None:
        c.error(join_path(i, column), f"{message} (spreadsheet line {line}).")

    for name in SCHEDULE_REQUIRED:
        if not cell[name]:
            err(name, "is required but empty")
    gid = cell["game_id"]
    if gid and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", gid):
        err("game_id", f"{gid!r} should be lower-case letters and digits joined by hyphens, like 2026-11-05-1")
        gid = ""
    day = _date_cell(err, "date", cell["date"]) if cell["date"] else None
    when = None
    if cell["time"]:
        when = parse_time(cell["time"])
        if when is None:
            err("time", f"{cell['time']!r} is not a time. Write 24 hours, like 19:00")
    kind = cell.get("type", "") or "regular"
    if kind not in GAME_TYPES:
        err("type", f"{kind!r} is not allowed. Use regular or playoff (or leave it blank)")
        kind = "regular"
    known = _check_sides(err, cell, kind, teams)
    status = cell.get("status", "").lower()
    if status not in ("", "cancelled"):
        err("status", f"{cell['status']!r} is not allowed. Leave it blank, or write cancelled")
        status = ""
    week = _week_cell(err, cell.get("week", ""))
    moved = _date_cell(err, "moved_from", cell["moved_from"]) if cell.get("moved_from") else None
    if len(c.problems) > problems_before or not gid or day is None or when is None:
        return None
    return ScheduleRow(gid, day, when, cell["home"], cell["away"], i, line, cell.get("venue") or None,
                       cell.get("surface") or None, kind, cell.get("round") or None, week, status, moved, known)


def _date_cell(err, column: str, text: str) -> dt.date | None:
    value = parse_date(text)
    if value is None:
        err(column, f"{text!r} is not a date. Write it as YYYY-MM-DD, like 2026-11-05")
    return value


def _week_cell(err, text: str) -> int | None:
    if not text:
        return None
    if text.isdigit() and int(text) >= 1:
        return int(text)
    err("week", f"{text!r} should be a whole number from 1, or blank")
    return None


def _check_sides(err, cell: dict[str, str], kind: str, teams: dict[str, Team]) -> bool:
    """Both sides must be team ids; only a playoff row may hold other text (TBD, 1st, Winner SF1).
    Returns whether both are known teams."""
    for side in ("home", "away"):
        value = cell[side]
        if value and value not in teams and kind != "playoff":
            hint = suggest(value, teams)
            err(side, f"{value!r} is not a team id in teams.yml" + (f". Did you mean {hint!r}?" if hint else "")
                + ". (Only a playoff game may name a team that is not known yet, like TBD or 1st)")
    known = all(cell[side] in teams for side in ("home", "away"))
    if known and cell["home"] == cell["away"]:
        err("away", f"{cell['away']!r} cannot play itself")
    return known


def _check_games_per_day(c: Checker, rows: list[ScheduleRow], limit: int) -> None:
    seen: dict[tuple[str, dt.date], list[ScheduleRow]] = {}
    for r in rows:
        if r.cancelled or not r.teams_known:
            continue
        for side in ("home", "away"):
            team = getattr(r, side)
            earlier = seen.setdefault((team, r.date), [])
            if len(earlier) >= limit:
                c.error(join_path(r.row, side), f"{team!r} already plays {len(earlier)} game"
                        f"{'' if len(earlier) == 1 else 's'} on {r.date.isoformat()} ({earlier[0].game_id}), "
                        f"and this sport allows {limit} a day (spreadsheet line {r.line}). "
                        "Move one game, or mark it cancelled.")
            earlier.append(r)


def _number_weeks(rows: list[ScheduleRow]) -> list[ScheduleRow]:
    """A blank `week` on a regular-season row is its date's place (1, 2, ...) among the regular-season dates,
    cancelled games included. A blank week on a playoff row stays blank."""
    dates = sorted({r.date for r in rows if r.type == "regular"})
    place = {d: n for n, d in enumerate(dates, start=1)}
    return [replace(r, week=place[r.date]) if r.week is None and r.type == "regular" else r for r in rows]


def work_out_byes(rows: list[ScheduleRow], teams: dict[str, Team]) -> dict[dt.date, tuple[str, ...]]:
    """For each regular-season day that has a game played or planned (not all cancelled), the teams (in
    teams.yml order) in no regular-season game that day. A cancelled game still counts as the team's game,
    so a team whose game was cancelled is not shown as having a bye. Never read from a file."""
    by_day: dict[dt.date, list[ScheduleRow]] = {}
    for r in rows:
        if r.type == "regular":
            by_day.setdefault(r.date, []).append(r)
    byes: dict[dt.date, tuple[str, ...]] = {}
    for day, games in sorted(by_day.items()):
        if all(g.cancelled for g in games):
            continue
        busy = {t for g in games for t in (g.home, g.away)}
        resting = tuple(t for t in teams if t not in busy)
        if resting:
            byes[day] = resting
    return byes


# ------------------------------------------------------------------ games/<id>.yml

@dataclass(frozen=True)
class _GameContext:
    """What checking the games of one season needs to know."""
    folder: Path
    shown: str                              # "data/2026-27"
    season: SeasonDef
    settings: Settings
    sport_def: SportDef
    teams: dict[str, Team]
    players: dict[str, Player]
    rows: dict[str, ScheduleRow]


def load_games(ctx: _GameContext) -> tuple[dict[str, LoadedGame], list[Problem]]:
    """Every `games/*.yml`: the envelope, then the sport's check and read. `drafts/` is never opened."""
    games_dir = ctx.folder / "games"
    games: dict[str, LoadedGame] = {}
    problems: list[Problem] = []
    if not games_dir.is_dir():
        return games, problems
    for path in sorted(games_dir.iterdir()):
        file = f"{ctx.shown}/games/{path.name}"
        if path.suffix != ".yml":
            if path.is_file():
                problems.append(Problem("warning", "", "is not a .yml file, so it is ignored. Game files are "
                                                       "named <game_id>.yml.", file))
            continue
        game, found = _load_game_file(path, file, ctx)
        problems.extend(found)
        if game and not has_errors(found):
            games[game.id] = game
    return games, problems


def _load_game_file(path: Path, file: str, ctx: _GameContext) -> tuple[LoadedGame | None, list[Problem]]:
    raw, problems = read_yaml(path, file)
    if problems:
        return None, problems
    c = Checker(file)
    if raw is None:
        c.error("", "This file is empty. A game file starts with game_id, status, home, away and checked_by.")
        return None, c.problems
    if c.mapping(raw, "", allowed=ENVELOPE_KEYS, required=("game_id", "status", "home", "away", "checked_by")) is None:
        return None, c.problems
    row = _envelope_row(c, raw, path.stem, ctx)
    _envelope_status(c, raw)
    _envelope_sides(c, raw, row)
    checked_by = _name_field(c, raw, "checked_by")
    scorekeeper = _name_field(c, raw, "scorekeeper")
    notes = _envelope_notes(c, raw)
    _envelope_review(c, raw)
    photo = _envelope_photo(c, raw, path.stem, ctx.folder)
    forfeit = _envelope_forfeit(c, raw, row)
    sheet = _envelope_sheet(c, raw, forfeit)
    sheet_ctx = _sport_context(ctx, row)
    reading = None
    if sheet is not None and sheet_ctx is not None:
        reading = _check_and_read(c, sheet, sheet_ctx, ctx.sport_def)
    if row is None or sheet_ctx is None or not c.ok:
        return None, c.problems
    return LoadedGame(row.game_id, ctx.season.id, file, row, row.home, row.away, checked_by or "", sheet_ctx,
                      scorekeeper, tuple(notes), photo, forfeit, sheet, reading), c.problems


def _envelope_row(c: Checker, raw: dict, stem: str, ctx: _GameContext) -> ScheduleRow | None:
    gid = c.ident(raw["game_id"], "game_id") if "game_id" in raw else None
    if gid is not None and gid != stem:
        c.error("game_id", f"{gid!r} does not match the file name {stem}.yml. Name the file after the game_id.")
    row = ctx.rows.get(stem)             # the file name is the game's identity; game_id must agree with it
    if row is None and gid is not None:
        hint = suggest(stem, ctx.rows)
        c.error("game_id", f"{stem!r} is not a game in schedule.csv." + (f" Did you mean {hint!r}?" if hint else "")
                + " Add the game to the schedule first.")
    elif row is not None and row.cancelled:
        c.error("game_id", f"{row.game_id!r} is marked cancelled in schedule.csv, so it cannot have a game file. "
                           "Delete this file, or clear the cancelled status.")
    return row


def _envelope_status(c: Checker, raw: dict) -> None:
    if "status" not in raw:
        return
    if raw["status"] == "draft":
        c.error("status", "is 'draft', but the build reads only finished sheets. Move the file to drafts/, "
                          "or finish it and write 'status: final'.")
    else:
        c.choice(raw["status"], "status", ("final",))


def _envelope_sides(c: Checker, raw: dict, row: ScheduleRow | None) -> None:
    sides = [c.ident(raw[k], k) if k in raw else None for k in ("home", "away")]
    if row is not None and None not in sides and (row.home, row.away) != tuple(sides):
        c.error("home", f"{sides[0]}/{sides[1]} doesn't match schedule.csv ({row.home}/{row.away}). "
                        "Fix the file, or the schedule row.")


def _name_field(c: Checker, raw: dict, key: str) -> str | None:
    if key not in raw:
        return None
    if is_first_last(raw[key]):
        return raw[key]
    c.error(key, f"{raw[key]!r} should be 'First L.' (a first name and the last initial, never a full name).")
    return None


def _envelope_notes(c: Checker, raw: dict) -> list[str]:
    notes: list[str] = []
    for i, note in enumerate(c.sequence(raw["notes"], "notes") or [] if "notes" in raw else []):
        if c.mapping(note, join_path("notes", i), required=("text",)) is not None and "text" in note:
            text = c.text(note["text"], join_path("notes", i, "text"))
            if text:
                notes.append(text)
    return notes


def _envelope_review(c: Checker, raw: dict) -> None:
    items = c.sequence(raw["review"], "review") if "review" in raw else None
    for i, item in enumerate(items or []):
        if c.mapping(item, join_path("review", i), required=("at", "note")) is not None:
            for k in ("at", "note"):
                if k in item:
                    c.text(item[k], join_path("review", i, k))
    if items:
        c.warning("review", "still has review notes. They belong to drafts; clear them once the sheet is checked.")


def _envelope_photo(c: Checker, raw: dict, stem: str, folder: Path) -> str | None:
    """The photo: `photo:` (a path inside the season folder) or by convention `sheets/<game_id>.*`."""
    if "photo" in raw:
        text = c.text(raw["photo"], "photo")
        if text is None:
            return None
        path = Path(text)
        if path.is_absolute() or ".." in path.parts or text.startswith("/"):
            c.error("photo", f"{text!r} must be a path inside the season folder, like sheets/{stem}.jpg (no leading '/').")
            return None
        if not (folder / path).is_file():
            c.warning("photo", f"{text!r} is not in the season folder. Add the photo there, or remove the 'photo:' line.")
            return None
        return path.as_posix()
    for suffix in PHOTO_SUFFIXES:
        if (folder / "sheets" / f"{stem}{suffix}").is_file():
            return f"sheets/{stem}{suffix}"
    return None


def _envelope_forfeit(c: Checker, raw: dict, row: ScheduleRow | None) -> str | None:
    if "forfeit" not in raw:
        return None
    team = c.ident(raw["forfeit"], "forfeit")
    if team is not None and row is not None and team not in (row.home, row.away):
        c.error("forfeit", f"{team!r} is not one of the two teams in this game ({row.home}, {row.away}). "
                           "Write the id of the team that forfeited.")
        return None
    return team


def _envelope_sheet(c: Checker, raw: dict, forfeit: str | None) -> dict | None:
    if "forfeit" in raw:
        if "sheet" in raw:
            c.error("sheet", "must not be here: a forfeited game has no sheet. Remove the 'sheet:' block, or the 'forfeit:' line.")
        return None
    if "sheet" not in raw:
        c.error("sheet", "is required. Add the 'sheet:' block with the scores, or 'forfeit: <team id>' for a forfeit.")
        return None
    return c.mapping(raw["sheet"], "sheet", any_keys=True)


def _sport_context(ctx: _GameContext, row: ScheduleRow | None) -> SportContext | None:
    if row is None or not row.teams_known:
        return None
    return SportContext(ctx.sport_def.spec, ctx.settings.rules, ctx.teams, ctx.players,
                        {"home": row.home, "away": row.away}, row.type, "games")


def _check_and_read(c: Checker, sheet: dict, sheet_ctx: SportContext, sport_def: SportDef) -> Reading | None:
    """The sport's check (paths gain 'sheet.'), then its read when check found no errors."""
    found = call_sport("check", sport_def.rules.check, sheet, sheet_ctx)
    c.extend(with_prefix(found, "sheet"))
    if has_errors(found):
        return None
    return call_sport("read", sport_def.rules.read, sheet, sheet_ctx)


# ------------------------------------------------------------------ across seasons

def check_unique_game_ids(loaded: dict[str, LoadedSeason], shown: list[str]) -> list[Problem]:
    """A game id may appear once among the seasons the site shows (the real season and its sample never
    both show). The later row is the one reported."""
    first: dict[str, str] = {}
    problems: list[Problem] = []
    for sid in shown:
        season = loaded.get(sid)
        for row in season.schedule if season else []:
            if row.game_id in first:
                problems.append(Problem("error", join_path(row.row, "game_id"),
                                        f"{row.game_id!r} is also a game in season {first[row.game_id]!r}. Game ids "
                                        f"must be unique across the seasons the site shows (spreadsheet line {row.line}).",
                                        f"{season.folder}/schedule.csv"))
            else:
                first[row.game_id] = sid
    return problems
