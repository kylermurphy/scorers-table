"""scripts/nightly_gate.py: the hourly wake-up builds only in the league's nightly hour, on its own clock."""
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import nightly_gate

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc


def league_file(tmp_path, **extra):
    """A real league.yml (the stub sport) in a temp folder; the gate reads sports/ from the repo."""
    lines = ['name: "Gate League"', "sport: stub", "timezone: America/Toronto"]
    lines += [f"{k}: {v}" for k, v in extra.items()]
    path = tmp_path / "league.yml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch", ""])
def test_only_scheduled_runs_wait_for_the_hour(event, tmp_path):
    run, _ = nightly_gate.decide(event, dt.datetime(2026, 11, 20, 12, 23, tzinfo=UTC), league_file(tmp_path))
    assert run is True


def test_a_scheduled_run_builds_in_the_nightly_hour_on_the_leagues_clock(tmp_path):
    path = league_file(tmp_path)                                    # default hour 3, America/Toronto
    # 08:23 UTC in November is 03:23 EST; 07:23 UTC is 02:23 and 09:23 UTC is 04:23.
    assert nightly_gate.decide("schedule", dt.datetime(2026, 11, 20, 8, 23, tzinfo=UTC), path)[0] is True
    assert nightly_gate.decide("schedule", dt.datetime(2026, 11, 20, 7, 23, tzinfo=UTC), path)[0] is False
    assert nightly_gate.decide("schedule", dt.datetime(2026, 11, 20, 9, 23, tzinfo=UTC), path)[0] is False


def test_daylight_saving_moves_the_utc_hour_not_the_local_one(tmp_path):
    path = league_file(tmp_path)
    # In July Toronto is UTC-4, so 03:23 local is 07:23 UTC.
    assert nightly_gate.decide("schedule", dt.datetime(2026, 7, 20, 7, 23, tzinfo=UTC), path)[0] is True
    assert nightly_gate.decide("schedule", dt.datetime(2026, 7, 20, 8, 23, tzinfo=UTC), path)[0] is False


def test_exactly_one_wake_up_a_day_builds(tmp_path):
    path = league_file(tmp_path, nightly_hour=22)
    day = dt.datetime(2026, 11, 20, 0, 23, tzinfo=UTC)
    hits = [h for h in range(24) if nightly_gate.decide("schedule", day + dt.timedelta(hours=h), path)[0]]
    assert len(hits) == 1


def test_a_league_file_with_problems_still_builds_so_the_build_reports_them(tmp_path):
    path = tmp_path / "league.yml"
    path.write_text("name: [oops\n", encoding="utf-8")
    run, why = nightly_gate.decide("schedule", dt.datetime(2026, 11, 20, 12, 23, tzinfo=UTC), path)
    assert run is True and "problems" in why


def test_the_script_prints_run_and_writes_github_output(tmp_path):
    out = tmp_path / "out"
    env = {"GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"}
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "nightly_gate.py"), "--event", "schedule",
         "--league", str(league_file(tmp_path)), "--now", "2026-11-20T07:23:00+00:00"],
        capture_output=True, text=True, env=env, cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "run=false"
    assert out.read_text() == "run=false\n"
