"""The part cases the parity test runs, and the ones it skips (with the reason).

A case is one specimen part (scripts/design_system/specimens_*.py) rendered for every layout and sport the
design-system page shows it in, light and dark, and the same markup built from the Jekyll includes. The
template of a case (cases/<id>.html) holds the specimen's own scaffolding (padding wrappers, demo labels)
with the includes where the specimen has the part.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from scripts.design_system import sample
from scripts.design_system.model import SPORTS, Part

CASES_DIR = Path(__file__).parent / "cases"

# Parts that only a real sport needs: they stay Python-only in stage 4 (docs/stage-4-spec.md section 9), each
# arrives with its sport in stage 5 together with its include and parity case.
SKIPPED = {
    "event-log": "hockey's scoring summary and penalties: a stage 5 part with the hockey sport (spec section 9)",
    "game-tables": "hockey's and slo-pitch's game tables (goalies and skaters, facts, batting): stage 5 parts with "
                   "each sport; basketball's tables, notes and top-performer tile ('game-tables-box') and "
                   "curling's game in numbers ('game-tables-numbers') are covered by the fragment cases below",
}


@dataclass
class Case:
    id: str                      # unique id; also the name of the template in cases/
    part: str                    # the specimen Part id
    sports: tuple | None = None  # restrict the sports (None: as the part says)
    drop: tuple = ()             # ((tag, class), ...) children of the specimen's wrapper to leave out
    note: str = ""


# Fragment cases: compare a piece of a specimen that is a generic part, though the specimen as a whole is not.
FRAGMENTS = [
    Case("game-tables-box", "game-tables", sports=("basketball",),
         note="basketball's whole game-tables specimen: the top-performer tile, the box-score tables and the footnote "
              "(the top_performer, stat_table and note blocks)"),
    Case("game-tables-numbers", "game-tables", sports=("curling",),
         note="curling's game-tables specimen: the game in numbers (the numbers block)"),
]


def load_parts() -> list[Part]:
    parts: list[Part] = []
    for name in ("specimens_shell", "specimens_scores", "specimens_data"):
        parts.extend(importlib.import_module(f"scripts.design_system.{name}").PARTS)
    return parts


def sports_for(part: Part, layout_meta: dict) -> list[str]:
    if part.sports == "layout":
        return list(layout_meta["sports"])
    if part.sports == "all":
        return list(SPORTS)
    return list(part.sports)


def combos(part: Part, only_sports: tuple | None = None) -> list[tuple[str, str]]:
    """(layout, sport) pairs the design-system page shows `part` for."""
    out = []
    for lay in sample.LAYOUTS:
        if part.layouts and lay["id"] not in part.layouts:
            continue
        for sport in sports_for(part, lay):
            if only_sports is None or sport in only_sports:
                out.append((lay["id"], sport))
    return out


def all_cases() -> list[tuple[Case, Part]]:
    """Every case to run: one per covered part, then the fragment cases."""
    parts = {p.id: p for p in load_parts()}
    out = []
    for pid, part in parts.items():
        if pid in SKIPPED:
            continue
        out.append((Case(pid, pid), part))
    for frag in FRAGMENTS:
        out.append((frag, parts[frag.part]))
    return out
