"""Shared pytest setup: puts the repo root on sys.path so `from scripts.core... import ...` works from
anywhere, and gives the tests the fixture sports and a place to put a throwaway repo."""
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
