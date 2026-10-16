"""Build the throwaway Jekyll site the parity test renders, and read its pages back.

The site (in a temp folder): a minimal _config.yml; the repo's _includes/shell and _includes/parts copied in;
the case templates copied to _includes/cases/; the converted sample data (scripts/design_system/contract.py) as
_data/parity/<layout>--<sport>/*.json; one page per (layout, sport) with a <div data-case="..."> block for
every case that applies. Jekyll runs once for all of it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import copy

from scripts.design_system import contract

from . import cases as cases_mod

ROOT = Path(__file__).resolve().parents[2]

CONFIG = """\
url: ""
baseurl: ""
title: parity
markdown: kramdown
exclude: []
"""

LAYOUT = "<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>parity</title></head><body>{{ content }}</body></html>\n"

# one block: the case template's output with every line stripped, so indentation never reaches the markup
BLOCK = """\
<div data-case="{case}">
{{%- capture _c -%}}{{% include cases/{template}.html %}}{{%- endcapture -%}}
{{%- assign _cl = _c | split: "
" -%}}
{{%- for _x in _cl -%}}{{{{ _x | strip }}}}{{%- endfor -%}}
</div>
"""

PAGE_HEAD = """\
---
layout: case
---
{{% assign stats = site.data.parity["{key}"] %}}
{{% assign league = stats.league %}}
{{% assign active = stats.active %}}
{{% assign fixture = stats.case %}}
"""


def _extras() -> dict[str, tuple[dict, list[str]]]:
    """Pages for behaviour no specimen draws: {key: (data files, case templates)}. The test checks them in
    test_parity.py (a league logo, a plain stat table, an unknown block type, two byes, a card without a line score)."""
    base = contract.build("basketball", "scoreboard")
    logo = copy.deepcopy(base)
    logo["league"]["logo"] = "assets/league/logo.svg"
    plain = copy.deepcopy(base)
    gid = plain["case"]["game_id"]
    plain["games"][gid]["blocks"] = [
        {"type": "stat_table", "title": None, "side": None, "caption": "Skaters", "number_col": False,
         "columns": [{"key": "g", "label": "G", "title": "Goals", "key_col": False},
                     {"key": "pts", "label": "PTS", "title": "Points", "key_col": True}],
         "rows": [{"player": "dave-m", "cells": {"g": "2", "pts": "4"}}],
         "totals": {"label": "Total", "cells": {"g": "2", "pts": "4"}}, "note": None},
        {"type": "mystery", "text": "a block type the includes do not know"},
        {"type": "note", "text": "End of blocks."},
    ]
    plain["games"][gid]["line_score"] = None
    plain["games"][gid]["card"].pop("line_score", None)
    plain["schedule"]["days"][0]["byes"] = ["foxes", "herons"]
    return {
        "extras-logo": (logo, ["x-logo"]),
        "extras-plain": (plain, ["x-blocks", "x-ticker", "x-card"]),
    }


def skip_unless_ci(message: str) -> None:
    """Skip a test that needs Ruby and the gems, except in CI (the `CI` variable GitHub Actions sets): there a
    missing tool must fail the run, or the Jekyll tests would vanish from it without anyone noticing."""
    import pytest
    if os.environ.get("CI"):
        pytest.fail(f"{message} (CI must run this test)")
    pytest.skip(message)


def jekyll_command() -> list[str] | None:
    """The command that runs Jekyll, or None when Ruby, Bundler or the gems are missing."""
    bundle = shutil.which("bundle")
    if not bundle:
        return None
    probe = subprocess.run([bundle, "exec", "jekyll", "--version"], cwd=ROOT, capture_output=True, text=True,
                           env=os.environ)
    if probe.returncode != 0:
        return None
    return [bundle, "exec", "jekyll"]


def build_site(dest: Path, command: list[str]) -> dict[tuple[str, str], dict[str, str]]:
    """Write the site into dest/src, run Jekyll, return {(layout, sport): {case id: inner html}}."""
    src, out = dest / "src", dest / "out"
    (src / "_layouts").mkdir(parents=True)
    (src / "_includes" / "cases").mkdir(parents=True)
    (src / "_config.yml").write_text(CONFIG)
    (src / "_layouts" / "case.html").write_text(LAYOUT)
    for sub in ("shell", "parts"):
        shutil.copytree(ROOT / "_includes" / sub, src / "_includes" / sub)
    for f in cases_mod.CASES_DIR.glob("*.html"):
        shutil.copy(f, src / "_includes" / "cases" / f.name)
    contract.write(src / "_data" / "parity")

    for key, (data, templates) in _extras().items():
        folder = src / "_data" / "parity" / key
        folder.mkdir(parents=True)
        for name, value in data.items():
            (folder / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        body = PAGE_HEAD.format(key=key) + "".join(BLOCK.format(case=t, template=t) for t in templates)
        (src / f"{key}.html").write_text(body)

    run = cases_mod.all_cases()
    per_page: dict[tuple[str, str], list[str]] = {}
    for case, part in run:
        for combo in cases_mod.combos(part, case.sports):
            per_page.setdefault(combo, []).append(case.id)
    for (layout, sport), ids in per_page.items():
        key = f"{layout}--{sport}"
        body = PAGE_HEAD.format(key=key) + "".join(BLOCK.format(case=i, template=i) for i in ids)
        (src / f"{key}.html").write_text(body)

    env = dict(os.environ)
    proc = subprocess.run([*command, "build", "--source", str(src), "--destination", str(out), "--quiet"],
                          cwd=ROOT, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError("jekyll build failed:\n" + proc.stdout + proc.stderr)
    # Liquid problems are printed as warnings and leave a message in the page; fail on both
    if "Liquid" in proc.stderr or "Liquid" in proc.stdout:
        raise RuntimeError("Liquid problem:\n" + proc.stdout + proc.stderr)

    rendered: dict[tuple[str, str], dict[str, str]] = {}
    pages = {(layout, sport): f"{layout}--{sport}" for (layout, sport) in per_page}
    pages.update({("extras", key): key for key in _extras()})
    for combo, name in pages.items():
        html = (out / f"{name}.html").read_text(encoding="utf-8")
        blocks = {}
        for m in re.finditer(r'<div data-case="([^"]+)">(.*?)</div>\n(?=<div data-case=|</body>)', html, re.S):
            blocks[m.group(1)] = m.group(2)
        rendered[combo] = blocks
    return rendered
