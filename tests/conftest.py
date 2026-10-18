"""Shared pytest setup: puts the repo root on sys.path so `from scripts.core... import ...` works from
anywhere, and gives the tests the fixture sports and a place to put a throwaway repo."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_SPORTS = ROOT / "tests" / "fixtures" / "sports"


@pytest.fixture
def sports_root() -> Path:
    """The fake sports in tests/fixtures/sports/ (tiny, other, bare, broken, typo)."""
    return FIXTURE_SPORTS


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty folder standing in for the repository root (for the logo-exists check)."""
    return tmp_path


def set_landing_page(text: str, value: bool | None = False) -> str:
    """The text of league.yml with its `landing_page:` line set to `value` (True, False) or, with None, left out.

    The shipped league.yml says `landing_page: true` (the template's own site is the landing page), and a key written
    twice is an error, so a test that copies league.yml and wants something else never appends a second line: it runs
    the text through this. Most copies want the league's own site (the default here, False): they have no landing.yml
    and no demo sports to show."""
    if value is None:
        return re.sub(r"(?m)^landing_page:.*\n", "", text)
    new = f"landing_page: {'true' if value else 'false'}"
    return re.sub(r"(?m)^landing_page:.*$", new, text) if re.search(r"(?m)^landing_page:", text) else text + f"\n{new}\n"
