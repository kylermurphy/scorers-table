#!/usr/bin/env python3
"""The build: load -> check -> compute -> write (docs/stage-4-spec.md section 4).

    python scripts/build.py                          # check everything and write _data/computed/, the stub pages, calendar/
    python scripts/build.py --check                  # check only; write nothing
    python scripts/build.py --sample --today 2026-11-20

Nothing is written unless every check passes. Problems print as `<file>: <path>: <message>` (errors first, then
warnings, then "Still to decide"). Exit codes: 0 built (warnings and placeholders are listed), 1 data problems
(all listed, nothing written), 2 usage or internal error (a sport function that raised, a bug; the message
names the file, `--debug` adds the traceback).

Options:
  --sample           show the sample season whatever league.yml says (the /preview/ copy)
  --today DATE       use this date as today (YYYY-MM-DD), for tests and for repeatable builds
  --check            stages 1-4 only: report problems, write nothing
  --json             print problems as JSON lines on stdout (nothing else is printed there)
  --annotations      also print GitHub `::error file=...::` lines on stdout (always on under GitHub Actions)
  --site-url URL     the site's address, for the calendar subscribe links and event URLs
  --root DIR         the repository root: league.yml, sports/ and data/ are read from here (default: this repo)
  --data DIR         the data folder (default: <root>/data)
  --out DIR          where _data/, _games/ ... calendar/ are written (default: <root>)
  --debug            show the traceback of an internal error
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.compute import BuildOutput, compute                                # noqa: E402
from scripts.core.config import load_league                                          # noqa: E402
from scripts.core.fmt import parse_date                                              # noqa: E402
from scripts.core.loader import load_data                                            # noqa: E402
from scripts.core.model import League, Problem                                       # noqa: E402
from scripts.core.problems import (                                                  # noqa: E402
    EXIT_INTERNAL, EXIT_OK, InternalError, has_errors, report,
)
from scripts.core.writer import write_output                                         # noqa: E402


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="build.py", description="Check the data and build the site's data files.")
    parser.add_argument("--sample", action="store_true", help="show the sample season (the /preview/ copy)")
    parser.add_argument("--today", metavar="YYYY-MM-DD", help="use this date as today")
    parser.add_argument("--check", action="store_true", help="check only; write nothing")
    parser.add_argument("--json", action="store_true", help="print problems as JSON lines on stdout")
    parser.add_argument("--annotations", action="store_true", help="also print GitHub ::error annotations")
    parser.add_argument("--site-url", default="", metavar="URL", help="the site's address (calendar links)")
    parser.add_argument("--root", type=Path, default=ROOT, metavar="DIR", help="the repository root")
    parser.add_argument("--data", type=Path, metavar="DIR", help="the data folder (default: <root>/data)")
    parser.add_argument("--out", type=Path, metavar="DIR", help="where to write (default: <root>)")
    parser.add_argument("--debug", action="store_true", help="show the traceback of an internal error")
    args = parser.parse_args(argv)
    if args.today is not None and parse_date(args.today) is None:
        parser.error(f"--today must be a date like 2026-11-20, not {args.today!r}")
    if os.environ.get("GITHUB_ACTIONS") == "true":          # a volunteer sees the problems on the pull request
        args.annotations = True
    return args


def _say(args: argparse.Namespace, message: str) -> None:
    """A line for the person running the build: on stderr when stdout carries JSON or annotations."""
    print(message, file=sys.stderr if (args.json or args.annotations) else sys.stdout)


def _report(args: argparse.Namespace, problems: list[Problem], league: League | None) -> int:
    return report(problems, league.placeholders if league else (), json_lines=args.json, annotations=args.annotations)


def build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    data_dir = Path(args.data).resolve() if args.data else root / "data"
    out_root = Path(args.out).resolve() if args.out else root
    league, problems = load_league(root / "league.yml", sports_root=root / "sports", root=root)
    if league is None:
        return _report(args, problems, None)
    preview = args.sample and not league.sample_data
    if args.sample:
        league = replace(league, sample_data=True)
    today = parse_date(args.today) if args.today else None
    data = load_data(root, league, league.sport_def, today=today, data_dir=data_dir)
    problems = problems + data.problems
    output = BuildOutput()
    if not has_errors(problems):
        output, found = compute(league, data, data_dir=data_dir, site_url=args.site_url, preview=preview)
        problems = problems + found
    code = _report(args, problems, league)
    if code != EXIT_OK:
        return code
    if args.check:
        _say(args, "The data is valid. Nothing was written (--check).")
        return EXIT_OK
    write_output(out_root, output, photos=league.photos)
    _say(args, f"Built {len(output.seasons)} season(s); the site shows {output.active}. "
               f"Wrote {len(output.data)} data files, {sum(len(p) for p in output.pages.values())} pages and "
               f"{len(output.calendars)} calendar files to {out_root}.")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return build(args)
    except InternalError as exc:
        if args.debug:
            raise
        print(f"Internal error: {exc}\n(a bug in the sport's files, not in your data; run with --debug for details)",
              file=sys.stderr)
        return EXIT_INTERNAL
    except Exception as exc:                      # a bug here, or a disk problem: never a raw traceback
        if args.debug:
            raise
        print(f"Internal error: {type(exc).__name__}: {exc}\n(run with --debug for the traceback)", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
