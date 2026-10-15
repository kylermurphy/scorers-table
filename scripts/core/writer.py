"""Writing a build to disk (docs/stage-4-spec.md 4 and 4.2): everything is staged first, then swapped in.

    write_output(out_root, output, photos=False) -> list of the folders written

* `_data/computed/` (JSON), the stub pages `_games/ _players/ _teams/ _archive/` (front matter only),
  `calendar/` (.ics) and, with `photos: true`, `sheets/`: each is built in a staging folder under
  `<out_root>/.build-tmp/` and then moved into place, replacing the old folder whole. A game that was removed
  from the data therefore loses its page, and a crash while staging leaves the old site untouched. (A folder swap
  is two renames, so a crash between them is possible but tiny; the old folder is put back if a swap fails.)
* The caller writes nothing unless the data had no problems: this module is only called after that check.
* JSON is written with 2-space indent, keys in the order the build made them (never sorted by chance),
  non-ASCII kept as it is, one trailing newline; the same data always gives the same bytes (the golden test).
* Stub pages are YAML front matter between `---` lines and nothing else (strings in double quotes).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.core.compute import BuildOutput

TMP_NAME = ".build-tmp"
COMPUTED = Path("_data") / "computed"
PAGE_FOLDERS = ("_games", "_players", "_teams", "_archive")
CALENDAR = "calendar"
SHEETS = "sheets"


def dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def front_matter(fields: dict[str, Any]) -> str:
    """'---\\nkey: "value"\\n---\\n'. A JSON string is a valid YAML double-quoted string."""
    lines = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()] + ["---"]
    return "\n".join(lines) + "\n"


def _put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def stage(output: BuildOutput, tmp: Path, photos: bool) -> dict[Path, Path]:
    """Build every folder under `tmp`. Returns {staged folder: final place relative to the output root}."""
    staged: dict[Path, Path] = {}
    data = tmp / "computed"
    data.mkdir(parents=True)
    for rel, value in output.data.items():
        _put(data / rel, dump_json(value))
    staged[data] = COMPUTED
    for folder in PAGE_FOLDERS:
        pages = tmp / folder
        pages.mkdir()
        for name, fields in output.pages.get(folder, {}).items():
            _put(pages / name, front_matter(fields))
        staged[pages] = Path(folder)
    calendars = tmp / CALENDAR
    calendars.mkdir()
    for name, text in output.calendars.items():
        _put(calendars / name, text)
    staged[calendars] = Path(CALENDAR)
    if photos:
        sheets = tmp / SHEETS
        sheets.mkdir()
        for source, name in output.sheets:
            shutil.copyfile(source, sheets / name)
        staged[sheets] = Path(SHEETS)
    return staged


def _swap_in(staged: dict[Path, Path], out_root: Path, trash: Path) -> list[Path]:
    """Move each staged folder into place, the old one into `trash`; put everything back if one move fails."""
    done: list[tuple[Path, Path | None]] = []
    try:
        for source, rel in staged.items():
            target = out_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            old = None
            if target.exists():
                old = trash / rel.as_posix().replace("/", "_")
                os.replace(target, old)
            done.append((target, old))
            os.replace(source, target)
    except BaseException:
        for target, old in reversed(done):
            shutil.rmtree(target, ignore_errors=True)
            if old is not None and old.exists():
                os.replace(old, target)
        raise
    return [target for target, _ in done]


def write_output(out_root: Path, output: BuildOutput, *, photos: bool = False) -> list[Path]:
    """Write the build into `out_root` (the Jekyll source folder). Returns the folders now in place."""
    out_root = Path(out_root)
    tmp = out_root / TMP_NAME
    shutil.rmtree(tmp, ignore_errors=True)               # left over from a build that was killed
    tmp.mkdir(parents=True)
    try:
        staged = stage(output, tmp / "new", photos)
        trash = tmp / "old"
        trash.mkdir()
        written = _swap_in(staged, out_root, trash)
        if not photos:
            shutil.rmtree(out_root / SHEETS, ignore_errors=True)       # photos are not published: none may linger
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return written
