from __future__ import annotations

import json
from pathlib import Path

import pytest

from eq_triage.report import render_markdown
from tests.regenerate_golden import build

GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.mark.parametrize("name", ["toy_alu", "toy_counter"])
def test_golden_json(name):
    report = build(name)
    got = json.loads(report.model_dump_json())
    expected = json.loads((GOLDEN / f"{name}_report.json").read_text())
    assert got == expected


@pytest.mark.parametrize("name", ["toy_alu", "toy_counter"])
def test_golden_markdown(name):
    report = build(name)
    got = render_markdown(report)
    expected = (GOLDEN / f"{name}_report.md").read_text()
    assert got == expected
