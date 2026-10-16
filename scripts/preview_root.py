#!/usr/bin/env python3
"""The sport previews: which sports get a demo copy of the site, and the temporary root that builds one
(docs/stage-5-basketball-spec.md, section 7).

    python scripts/preview_root.py --list              # the sport ids `sport_previews` in league.yml asks for, one per line
    python scripts/preview_root.py <sport> <folder>    # write the temporary root for that sport's demo league

`scripts/build_preview.sh` runs both: `--list`, then for each id the second form, then
`build.py --root <folder> --out . --sport-preview <id>` and Jekyll with base path `<BASE_PATH>/<id>`.

The root holds a `league.yml` (the sport's made-up league from `sports/<id>/sample.py`, the sport's own default
look, `sample_data: true`, `preview: false`, `sport_previews: false`, `search_engines: false`; the real league's
`timezone` and `time_format` are the only things taken from the real `league.yml`), a `data/seasons.yml` with an
empty current season and the two sample seasons, the sample data from `scripts/make_sample.py` (the same fixed
seed as the golden test, so two runs write the same files), and `sports/`, a link to this repository's. Nothing
else of the real league reaches a preview: no name, colour, logo, rules or settings.

Exit codes: 0 done, 1 `league.yml` or the sport has problems (all printed), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import make_sample                                                      # noqa: E402
from scripts.core.config import LEAGUE_FILE, load_league                             # noqa: E402
from scripts.core.problems import format_human, has_errors, read_yaml               # noqa: E402
from scripts.core.sports import demo_sports, load_sport                              # noqa: E402

# data/seasons.yml of every preview: the same seasons as the template's own, so the sample data is the same
# (the golden test builds its sample from the template's data/seasons.yml; tests/test_preview_root.py compares).
SEASONS = """\
# Written by scripts/preview_root.py: the seasons of a sport preview.
- id: 2026-27
  label: "2026–27"
  current: true
  venue: "[Gym name]"
  venue_address: ""
- id: sample-2026-27
  label: "2026–27"
  sample: true
  stands_in_for: 2026-27
  as_of: 2026-11-20
  venue: "[Venue]"
- id: sample-2025-26
  label: "2025–26"
  sample: true
  overrides:
    standings:
      points: {win: 3, tie: 1, loss: 0, ot_win: 3, ot_loss: 1}
  venue: "[Venue]"
"""

EMPTY_FILES = {                      # the current season, left empty: a preview has no real games and no calendars
    "teams.yml": "[]\n",
    "players.yml": "[]\n",
    "schedule.csv": ",".join(make_sample.CSV_COLUMNS) + "\n",
}


def preview_ids(root: Path = ROOT) -> tuple[list[str], list]:
    """(the sport ids `sport_previews` asks for, problems). The ids are empty when league.yml has errors."""
    league, problems = load_league(root / LEAGUE_FILE, sports_root=root / "sports", root=root)
    return (list(league.sport_previews) if league else []), problems


def league_text(sport_id: str, root: Path = ROOT) -> str:
    """The generated league.yml for one sport's demo (a text; two calls give the same one)."""
    sports_root = root / "sports"
    sport, problems = load_sport(sport_id, sports_root, root=root, with_sample=True)
    if sport is None:
        raise ValueError("; ".join(f"{p.file}: {p.message}" for p in problems))
    real, _ = read_yaml(root / LEAGUE_FILE, LEAGUE_FILE)
    real = real if isinstance(real, dict) else {}
    lines = [
        "# Written by scripts/preview_root.py: the demo league of a sport preview. Nothing here is the real league's.",
        f"name: {json.dumps(sport.sample.LEAGUE_NAME, ensure_ascii=False)}",
        f"sport: {sport_id}",
        f"layout: {sport.spec['default_layout']}",
        f"timezone: {json.dumps(str(real.get('timezone', 'UTC')))}",
        f"time_format: {json.dumps(str(real.get('time_format', '12h')))}",
        "sample_data: true",
        "preview: false",
        "sport_previews: false",
        "search_engines: false",
        "",
    ]
    return "\n".join(lines)


def write_root(sport_id: str, dest: Path, root: Path = ROOT) -> Path:
    """Write the temporary root for `sport_id` into `dest` (a folder that is empty or does not exist yet)."""
    dest = Path(dest)
    if sport_id not in demo_sports(root / "sports"):
        raise ValueError(f"{sport_id!r} is not a sport with a preview. Sports with a preview: "
                         f"{', '.join(demo_sports(root / 'sports')) or '(none found)'}.")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"{dest} is not empty.")
    text = league_text(sport_id, root)
    (dest / "data" / "2026-27" / "games").mkdir(parents=True)
    (dest / "data" / "2026-27" / "drafts").mkdir()
    (dest / LEAGUE_FILE).write_text(text, encoding="utf-8", newline="")
    (dest / "data" / "seasons.yml").write_text(SEASONS, encoding="utf-8", newline="")
    for name, content in EMPTY_FILES.items():
        (dest / "data" / "2026-27" / name).write_text(content, encoding="utf-8", newline="")
    try:                                              # a link to the repository's sports/ (no copy to keep in step)
        os.symlink((root / "sports").resolve(), dest / "sports", target_is_directory=True)
    except OSError:                                   # a file system without links: copy, without caches
        shutil.copytree(root / "sports", dest / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    make_sample.write_all(dest, make_sample.generate_all(dest))
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preview_root.py", description="Sport previews: the list, and a temporary root.")
    parser.add_argument("sport", nargs="?", help="the sport id (a folder in sports/)")
    parser.add_argument("folder", nargs="?", type=Path, help="where to write the root (empty or not yet there)")
    parser.add_argument("--list", action="store_true", help="print the sport ids league.yml asks for, one per line")
    args = parser.parse_args(argv)
    if args.list == bool(args.sport):
        parser.error("give either --list, or a sport id and a folder")
    if args.list:
        ids, problems = preview_ids()
        if has_errors(problems):
            print(format_human(problems), file=sys.stderr)
            return 1
        if ids:
            print("\n".join(ids))
        return 0
    if args.folder is None:
        parser.error("give a folder to write the root into")
    try:
        write_root(args.sport, args.folder)
    except (ValueError, make_sample.SampleError) as exc:
        print(f"preview_root.py: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote the root for the {args.sport} preview to {args.folder}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
