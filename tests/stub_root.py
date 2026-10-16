"""The stub is the core's test sport. The repository ships another sport (basketball), so a test that wants the
stub's league and sample seasons turns a copy of the repository into a stub one with `use_the_stub`."""
import re
import shutil
from pathlib import Path

from scripts import make_sample

STUB_LEAGUE_NAME = "Example Valley Stub League"


def use_the_stub(root: Path) -> None:
    """In a copy of the repository: league.yml says `sport: stub` with the stub's league name, and data/sample-*/
    are the stub's sample seasons (written by make_sample.py, so they are what the golden files describe)."""
    league = root / "league.yml"
    text = league.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^sport: .*$", "sport: stub", text)
    text = re.sub(r"(?m)^name: .*$", f'name: "{STUB_LEAGUE_NAME}"', text)
    league.write_text(text, encoding="utf-8")
    for sample in (root / "data").glob("sample-*"):
        shutil.rmtree(sample)
    make_sample.write_all(root, make_sample.generate_all(root))
