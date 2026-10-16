#!/usr/bin/env python3
"""Turn a Masters Basketball League data folder into a scorers-table data folder.

    python sports/basketball/convert_masters.py --from <masters>/data --to <folder> [--photos]

The Masters site (tb-masters-basketball/website) keeps its numbers in `data/`: `seasons.yml`, and per
season `teams.yml`, `players.yml`, `schedule.csv`, `games/`, `drafts/` and `sheets/`. This script writes the
same league in scorers-table's shape (docs/stage-5-basketball-spec.md, sections 2.2 and 2.4):

    seasons.yml     gym -> venue, gym_address -> venue_address, ppg_min_games and ft_min_attempts ->
                    overrides.stats.minimums
    teams.yml       short -> code, colour_slot -> slot; colour_light / colour_dark (a record only) dropped
    players.yml     display -> name
    schedule.csv    gym -> venue; every other column as it was
    games/, drafts/ the game file envelope (game_id, status, home, away, scorekeeper, checked_by, review,
                    forfeit) stays at the top; `teams.<team id>.players` becomes `sheet.players.<side>`,
                    `running`, `lines` and `boxes` move under `sheet` keyed by `home` / `away` instead of
                    team ids, and a Notes entry's `team` becomes `side`. `form` is dropped (no printed
                    sheet yet). A `review` path is mapped the same way (`running.bb.14` becomes
                    `sheet.running.away.14`), so the entry page can still point at the box.
    sheets/         copied with --photos

What is NOT carried over, and said so:
  * A forfeit file's `notes` (e.g. "bb had three players at 9:55"): a forfeit has no sheet, and the
    envelope's notes are published on the game page, which Masters never did. Each one is printed.
  * Photos in a format scorers-table does not publish (.heic), and any season key it has no place for.

It also prints the `league.yml` lines of the Masters standings preset (spec 3.4).

The script only converts; it does not check the sheets. Run `python scripts/build.py --check --data <folder>`
(with a league.yml that has the preset) to have the basketball rules check the result.

It refuses to write into a folder that already has files. Converted Masters data names real players: it must
never be committed to scorers-table (spec 2.4); write it to a temporary folder.

Standard library plus PyYAML only.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SEASONS_FILE = "seasons.yml"
TEAM_FILE, PLAYER_FILE, SCHEDULE_FILE = "teams.yml", "players.yml", "schedule.csv"
GAME_FOLDERS = ("games", "drafts")
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".pdf")
SIDES = ("home", "away")
SHEET_PARTS = ("running", "lines", "boxes")            # keyed by team id in Masters, by side here
MINIMUM_KEYS = ("ppg_min_games", "ft_min_attempts")
SEASON_KEYS = ("id", "label", "current", "sample", "stands_in_for", "gym", "gym_address", *MINIMUM_KEYS)
TEAM_KEYS = ("id", "name", "short", "colour_slot", "colour_light", "colour_dark")
PLAYER_KEYS = ("id", "display", "team", "sub", "number")
# The envelope keys a game file keeps at the top, in the order they are written.
ENVELOPE_ORDER = ("game_id", "status", "home", "away", "forfeit", "scorekeeper", "checked_by", "review")
MASTERS_ONLY_KEYS = ("form",)                          # dropped silently: spec 2.2
SHEET_KEY_ORDER = ("players", "running", "lines", "boxes", "notes")

# The league.yml lines of the Masters standings (spec 3.4), printed after a conversion.
MASTERS_PRESET = """\
rules: {overtime: overtime}           # level after Q4: overtime (league rule 4)
standings:
  points: {win: 3, tie: 0, loss: 0}   # 3 for a win; a tie gives no game points
  period_points: 1                    # 1 per quarter won; a tied quarter gives nobody a point
  ties: true                          # a game still tied after overtime stands (regular season)
  forfeit: {score: per_period}        # 1-0 in every quarter: 4-0, and 7 points to the winner
  tiebreakers: [head_to_head, diff]
  columns: [gp, w, l, t, pw, pts, diff]
"""


class ConvertError(Exception):
    """The conversion cannot go ahead; nothing was written. `problems` lists every reason."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Result:
    """What a conversion did (everything is also printed by main)."""
    files: list[str] = field(default_factory=list)             # written files, relative to the output folder
    omitted: list[str] = field(default_factory=list)           # content left out on purpose, one line each
    warnings: list[str] = field(default_factory=list)          # things worth a look
    league_yml: str = MASTERS_PRESET


# ------------------------------------------------------------------------------ YAML out

def _scalar(value) -> str:
    """One YAML scalar on one line, quoted as flow style needs ("00", "yes", "a: b", "St. Pat's, Thunder Bay").
    Dumped inside a one-item list so PyYAML applies the flow-context quoting rules (commas and brackets)."""
    if isinstance(value, str) and ("\n" in value or "\r" in value or "\t" in value):
        return json.dumps(value, ensure_ascii=False)         # one line: JSON strings are valid YAML
    text = yaml.safe_dump([value], default_flow_style=True, width=10 ** 9, allow_unicode=True).rstrip("\n")
    return text[1:-1]


def _flow(value) -> str:
    """Any value as one-line YAML flow style ({a: 1, b: [1, 2]})."""
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_scalar(k)}: {_flow(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    return _scalar(value)


def _block_list(items, indent: int) -> list[str]:
    pad = " " * indent
    return [f"{pad}- {_flow(item)}" for item in items]


def _block_map(value: dict, indent: int, *, list_values: bool = False) -> list[str]:
    """`key: {flow}` per entry; with list_values, `key:` and a block list of flow rows beneath it."""
    pad = " " * indent
    out: list[str] = []
    for key, item in value.items():
        if list_values and isinstance(item, list) and item:
            out.append(f"{pad}{_scalar(key)}:")
            out += _block_list(item, indent + 2)
        else:
            out.append(f"{pad}{_scalar(key)}: {_flow(item)}")
    return out


def dump_game(game: dict) -> str:
    """A game file as compact YAML in the documented key order (spec 2.1): the envelope, then `sheet:`."""
    out: list[str] = []
    for key in (*ENVELOPE_ORDER, "sheet"):
        if key not in game:
            continue
        value = game[key]
        if key == "review" and isinstance(value, list) and value:
            out.append(f"{key}:")
            out += _block_list(value, 2)
        elif key == "sheet" and isinstance(value, dict):
            out.append("sheet:")
            for part in (*SHEET_KEY_ORDER, *(k for k in value if k not in SHEET_KEY_ORDER)):
                if part not in value:
                    continue
                item = value[part]
                if part == "players" and isinstance(item, dict):
                    out.append("  players:")
                    out += _block_map(item, 4, list_values=True)
                elif part in SHEET_PARTS and isinstance(item, dict):
                    out.append(f"  {part}:")
                    out += _block_map(item, 4)
                elif part == "notes" and isinstance(item, list) and item:
                    out.append("  notes:")
                    out += _block_list(item, 4)
                else:
                    out.append(f"  {_scalar(part)}: {_flow(item)}")
        else:
            out.append(f"{key}: {_flow(value)}")
    for key in game:                                         # unknown envelope keys: kept at the end, to be checked
        if key not in ENVELOPE_ORDER and key != "sheet":
            out.append(f"{_scalar(key)}: {_flow(game[key])}")
    return "\n".join(out) + "\n"


def dump_list(header: str, rows: list[dict]) -> str:
    """seasons.yml, teams.yml, players.yml: a comment line, then one flow mapping per line."""
    lines = [f"# {header}"] + [f"- {_flow(row)}" for row in rows]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------ reading

def _read_yaml(path: Path, problems: list[str]):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"{path}: file is missing")
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        problems.append(f"{path}: not valid YAML ({exc})")
    return None


def _read_list(path: Path, problems: list[str]) -> list[dict]:
    raw = _read_yaml(path, problems)
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(r, dict) for r in raw):
        problems.append(f"{path}: should be a list of mappings")
        return []
    return raw


# ------------------------------------------------------------------------------ the small files

def convert_seasons(seasons: list[dict], result: Result) -> list[dict]:
    out = []
    for s in seasons:
        row: dict = {"id": s["id"]}
        if "label" in s:
            row["label"] = s["label"]
        for key in ("current", "sample"):
            if s.get(key):
                row[key] = True
        if s.get("stands_in_for"):
            row["stands_in_for"] = s["stands_in_for"]
        if s.get("gym") is not None:
            row["venue"] = s["gym"]
        if s.get("gym_address") is not None:
            row["venue_address"] = s["gym_address"]
        minimums = {k: s[k] for k in MINIMUM_KEYS if k in s}
        if minimums:
            row["overrides"] = {"stats": {"minimums": minimums}}
        for key in s:
            if key not in SEASON_KEYS:
                result.omitted.append(f"{SEASONS_FILE}: season {s['id']}: '{key}' has no place in scorers-table; left out")
        out.append(row)
    return out


def convert_teams(teams: list[dict], result: Result, where: str) -> list[dict]:
    out = []
    for t in teams:
        row = {"id": t.get("id"), "name": t.get("name"), "code": t.get("short")}
        if "colour_slot" in t:
            row["slot"] = t["colour_slot"]
        out.append({k: v for k, v in row.items() if v is not None})
        for key in t:
            if key not in TEAM_KEYS:
                result.omitted.append(f"{where}: team {t.get('id')}: '{key}' has no place in scorers-table; left out")
    return out


def convert_players(players: list[dict], result: Result, where: str) -> list[dict]:
    out = []
    for p in players:
        row = {"id": p.get("id"), "name": p.get("display"), "team": p.get("team")}
        if p.get("sub"):
            row["sub"] = True
        if p.get("number") is not None:
            row["number"] = p["number"]
        out.append({k: v for k, v in row.items() if v is not None or k == "team"})
        for key in p:
            if key not in PLAYER_KEYS:
                result.omitted.append(f"{where}: player {p.get('id')}: '{key}' has no place in scorers-table; left out")
    return out


def convert_schedule(text: str) -> str:
    """schedule.csv with the `gym` column named `venue`; every other column and cell as it was."""
    rows = list(csv.reader(io.StringIO(text.removeprefix("﻿"), newline="")))
    if rows:
        rows[0] = ["venue" if cell.strip() == "gym" else cell.strip() for cell in rows[0]]
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


# ------------------------------------------------------------------------------ game files

def _side(team, sides: dict):
    """A team id as its side. A value that is not one of the game's two teams is kept as written, so the
    basketball check reports it at the box where Masters did."""
    try:
        return sides.get(team, team)
    except TypeError:                                         # an unhashable value: kept as it is
        return team


def _by_side(value, sides: dict):
    """A mapping keyed by team id, re-keyed by side. Anything else is kept as it is."""
    if not isinstance(value, dict):
        return value
    return {_side(k, sides): v for k, v in value.items()}


def map_review_path(at, sides: dict, *, forfeit: bool = False):
    """A Masters `review.at` path as the scorers-table path to the same box.

    running.bb.14 -> sheet.running.away.14; teams.aa.players.3.ft.2 -> sheet.players.home.3.ft.2;
    lines.aa.1 -> sheet.lines.home.1; boxes.aa.final -> sheet.boxes.home.final; notes.0.team ->
    sheet.notes.0.side. The header paths (game_id, status, home, away, scorekeeper, checked_by, forfeit,
    review) stay; `form` becomes the whole file (""). A path it does not know is left as written."""
    if not isinstance(at, str):
        return at
    parts = at.split(".")
    head = parts[0]
    if head == "form":
        return ""
    if head == "teams":
        if len(parts) == 1:
            return "sheet.players"
        if len(parts) == 2:
            return ".".join(["sheet", "players", str(_side(parts[1], sides))])
        if parts[2] == "players":
            return ".".join(["sheet", "players", str(_side(parts[1], sides)), *parts[3:]])
        return at
    if head in SHEET_PARTS:
        if len(parts) == 1:
            return f"sheet.{head}"
        return ".".join(["sheet", head, str(_side(parts[1], sides)), *parts[2:]])
    if head == "notes":
        if forfeit:                                           # envelope notes of a forfeit: no sheet to point into
            return at
        return ".".join(["sheet", *("side" if (i == 2 and p == "team") else p for i, p in enumerate(parts))])
    return at


def _map_review(review, sides: dict, forfeit: bool):
    if not isinstance(review, list):
        return review
    out = []
    for item in review:
        if isinstance(item, dict) and "at" in item:
            item = {**item, "at": map_review_path(item["at"], sides, forfeit=forfeit)}
        out.append(item)
    return out


def _map_note(note, sides: dict):
    """A Notes entry: `team` becomes `side` (a team that is not in the game is kept as written)."""
    if not isinstance(note, dict) or "team" not in note:
        return note
    return {("side" if k == "team" else k): (_side(v, sides) if k == "team" else v) for k, v in note.items()}


def convert_game(raw: dict, where: str, result: Result) -> dict:
    """One Masters game file (a mapping) as a scorers-table game file (a mapping)."""
    home, away = raw.get("home"), raw.get("away")
    sides: dict = {}
    if isinstance(home, str):
        sides[home] = "home"
    if isinstance(away, str) and away != home:
        sides[away] = "away"
    forfeit = "forfeit" in raw
    out: dict = {}
    for key, value in raw.items():
        if key in MASTERS_ONLY_KEYS or key in ("teams", "running", "lines", "boxes"):
            continue
        if key == "notes":
            if forfeit:
                for n, note in enumerate(value if isinstance(value, list) else [value]):
                    text = note.get("text") if isinstance(note, dict) else note
                    result.omitted.append(f"{where}: notes.{n}: {str(text)!r} (a forfeit has no sheet; the game page "
                                          "would publish it, so it is left out)")
                continue
            continue                                          # a non-forfeit's notes go under sheet, below
        if key == "review":
            out["review"] = _map_review(value, sides, forfeit)
        else:
            out[key] = value
    if forfeit:
        return out
    sheet: dict = {}
    teams = raw.get("teams")
    if "teams" in raw:
        if isinstance(teams, dict):
            players = {}
            for tid, entry in teams.items():
                if isinstance(entry, dict) and set(entry) == {"players"}:
                    players[_side(tid, sides)] = entry["players"]
                else:                                         # anything else about a team: kept, to be reported
                    players[_side(tid, sides)] = entry
            sheet["players"] = players
        else:
            sheet["players"] = teams
    for part in SHEET_PARTS:
        if part in raw:
            sheet[part] = _by_side(raw[part], sides)
    if "notes" in raw:
        notes = raw["notes"]
        sheet["notes"] = [_map_note(n, sides) for n in notes] if isinstance(notes, list) else notes
    out["sheet"] = sheet
    return out


# ------------------------------------------------------------------------------ the whole folder

def convert(source: Path, target: Path, *, photos: bool = False) -> Result:
    """Convert the Masters data folder `source` into `target` (which must be empty or not exist yet).
    Raises ConvertError, having written nothing, when the input cannot be read or the target is not empty."""
    source, target = Path(source), Path(target)
    problems: list[str] = []
    if not source.is_dir():
        raise ConvertError([f"{source}: is not a folder. Point --from at the Masters site's data/ folder."])
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ConvertError([f"{target}: already has files in it. Convert into an empty (or new) folder; "
                            "this script never overwrites."])
    if _inside(target, source) or _inside(source, target):
        raise ConvertError([f"{target}: --to and --from must not contain each other."])
    result = Result()
    outputs: dict[str, str] = {}                              # relative path -> text
    copies: dict[str, Path] = {}                              # relative path -> photo to copy

    seasons = _read_list(source / SEASONS_FILE, problems)
    for i, s in enumerate(seasons):
        if not isinstance(s.get("id"), str):
            problems.append(f"{source / SEASONS_FILE}: season #{i + 1}: needs an 'id'")
    seasons = [s for s in seasons if isinstance(s.get("id"), str)]
    if not seasons and not problems:
        problems.append(f"{source / SEASONS_FILE}: lists no season")

    for s in seasons:
        sid = s["id"]
        folder = source / sid
        if not folder.is_dir():
            problems.append(f"{source / SEASONS_FILE}: season {sid}: folder {folder} does not exist")
            continue
        teams = _read_list(folder / TEAM_FILE, problems)
        players = _read_list(folder / PLAYER_FILE, problems)
        outputs[f"{sid}/{TEAM_FILE}"] = dump_list(f"Converted from Masters ({sid}) by convert_masters.py.",
                                                  convert_teams(teams, result, f"{sid}/{TEAM_FILE}"))
        outputs[f"{sid}/{PLAYER_FILE}"] = dump_list(f"Converted from Masters ({sid}) by convert_masters.py.",
                                                    convert_players(players, result, f"{sid}/{PLAYER_FILE}"))
        schedule = folder / SCHEDULE_FILE
        try:
            outputs[f"{sid}/{SCHEDULE_FILE}"] = convert_schedule(schedule.read_text(encoding="utf-8"))
        except FileNotFoundError:
            problems.append(f"{schedule}: file is missing")
        except UnicodeDecodeError:
            problems.append(f"{schedule}: is not UTF-8 text")
        for name in GAME_FOLDERS:
            for path in sorted((folder / name).glob("*.y*ml")) if (folder / name).is_dir() else []:
                raw = _read_yaml(path, problems)
                if raw is None:
                    continue
                if not isinstance(raw, dict):
                    problems.append(f"{path}: should be a game file (a mapping)")
                    continue
                where = f"{sid}/{name}/{path.name}"
                outputs[f"{sid}/{name}/{path.stem}.yml"] = dump_game(convert_game(raw, where, result))
        if photos and (folder / "sheets").is_dir():
            for path in sorted((folder / "sheets").iterdir()):
                if not path.is_file() or path.name.startswith("."):
                    continue                                  # .gitkeep and the like
                if path.suffix.lower() in PHOTO_SUFFIXES:
                    copies[f"{sid}/sheets/{path.name}"] = path
                else:
                    result.omitted.append(f"{sid}/sheets/{path.name}: scorers-table does not publish this photo "
                                          "format; not copied")
    if problems:
        raise ConvertError(problems)

    outputs[SEASONS_FILE] = dump_list("Converted from Masters by convert_masters.py. Add the Masters preset to "
                                      "league.yml (printed by the converter).", convert_seasons(seasons, result))
    for rel in sorted(outputs):
        _write(target / rel, outputs[rel].encode("utf-8"))
    for rel in sorted(copies):
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(copies[rel], dest)
    result.files = sorted([*outputs, *copies])
    return result


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ------------------------------------------------------------------------------ command line

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="source", type=Path, required=True, metavar="DIR",
                        help="the Masters site's data/ folder")
    parser.add_argument("--to", dest="target", type=Path, required=True, metavar="DIR",
                        help="the folder to write: scorers-table's data/ layout (must be empty or new)")
    parser.add_argument("--photos", action="store_true", help="also copy the score sheet photos (sheets/)")
    args = parser.parse_args(argv)
    try:
        result = convert(args.source, args.target, photos=args.photos)
    except ConvertError as exc:
        print(f"Nothing was written: {len(exc.problems)} problem(s).", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    games = sum(1 for f in result.files if "/games/" in f)
    drafts = sum(1 for f in result.files if "/drafts/" in f)
    print(f"Wrote {len(result.files)} files to {args.target} ({games} games, {drafts} drafts).")
    if result.omitted:
        print(f"\nLeft out ({len(result.omitted)}), so nothing is published by accident:")
        for line in result.omitted:
            print(f"  - {line}")
    print("\nAdd these lines to league.yml (the Masters standings and overtime rules):\n")
    print(result.league_yml)
    print("Converted Masters data names real players. Do not commit it to scorers-table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
