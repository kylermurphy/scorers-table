#!/usr/bin/env python3
"""Should this workflow run build the site? (.github/workflows/build.yml, job `gate`)

GitHub cron cannot read league.yml, so the workflow wakes every hour and asks this script. For a scheduled run
it says yes only in the league's `nightly_hour` (league.yml, default 3) on the league's `timezone` clock; every
other trigger (a push, a pull request, "Run workflow") always says yes. If league.yml cannot be read it says yes,
so the build itself reports the problem.

    python scripts/nightly_gate.py --event schedule [--now 2026-11-20T08:23:00+00:00]

Prints `run=true` or `run=false` (also appended to $GITHUB_OUTPUT when that is set) and a line saying why.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.core.config import load_league  # noqa: E402


def decide(event: str, now: dt.datetime, league_file: Path | None = None) -> tuple[bool, str]:
    """(run, why). `now` must be timezone-aware."""
    if event != "schedule":
        return True, f"a {event or 'manual'} run always builds"
    league, problems = load_league(league_file)
    if league is None:
        return True, "league.yml has problems; building so the build reports them"
    local = now.astimezone(ZoneInfo(league.timezone))
    if local.hour == league.nightly_hour:
        return True, f"it is {local:%H:%M} in {league.timezone}: the nightly hour ({league.nightly_hour}:00)"
    return False, (f"it is {local:%H:%M} in {league.timezone}; the nightly build runs in the "
                   f"{league.nightly_hour}:00 hour (nightly_hour in league.yml)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--now", help="an ISO date and time with an offset, for tests (default: now)")
    parser.add_argument("--league", type=Path, help="the league.yml to read (default: the repository's)")
    args = parser.parse_args(argv)
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    run, why = decide(args.event, now, args.league)
    print(f"run={'true' if run else 'false'}")
    print(why, file=sys.stderr)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
