"""Golden-output tests.

The engine + report are deterministic, so regenerating from the bundled example
inputs must byte-match the committed golden reports in ``examples/expected/``.

Regenerate goldens (after an intentional change) with::

    python tests/regenerate_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vplan_agent.approval import apply_decisions, load_decisions
from vplan_agent.engine import build_plan
from vplan_agent.ingest import (
    load_existing_testplan,
    load_interface,
    load_manifest_view,
    load_spec,
)
from vplan_agent.models import Provenance
from vplan_agent.report import render_markdown
from vplan_agent.serialize import plan_from_json, plan_to_json

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
EXP = EX / "expected"


def _fixed_provenance() -> Provenance:
    # Fixed provenance so goldens are stable (real runs record hashes/command).
    return Provenance(command="<golden>", input_files=[], input_sha256={})


def _build_fifo():
    return build_plan(
        load_spec(EX / "fifo_spec.json"),
        load_interface(EX / "fifo_interface.json"),
        load_manifest_view(EX / "fifo_manifest.json"),
        load_existing_testplan(EX / "fifo_existing_testplan.json"),
        _fixed_provenance(),
    )


def _build_gpio():
    return build_plan(
        load_spec(EX / "gpio_spec.json"),
        load_interface(EX / "gpio_interface.json"),
        load_manifest_view(EX / "gpio_manifest.json"),
        None,
        _fixed_provenance(),
    )


def _normalize(plan_json_text: str) -> dict:
    d = json.loads(plan_json_text)
    d["provenance"] = "<ignored>"
    return d


@pytest.mark.parametrize("builder,name", [(_build_fifo, "fifo"), (_build_gpio, "gpio")])
def test_golden_markdown(builder, name):
    plan = builder()
    got = render_markdown(plan)
    expected = (EXP / f"{name}_plan.md").read_text(encoding="utf-8")
    assert got == expected


@pytest.mark.parametrize("builder,name", [(_build_fifo, "fifo"), (_build_gpio, "gpio")])
def test_golden_json(builder, name):
    plan = builder()
    got = _normalize(plan_to_json(plan))
    expected = _normalize((EXP / f"{name}_plan.json").read_text(encoding="utf-8"))
    assert got == expected


def test_golden_approved_markdown():
    plan = plan_from_json((EXP / "fifo_plan.json").read_text(encoding="utf-8"))
    decisions = load_decisions(EX / "fifo_decisions.json")
    updated, _, _ = apply_decisions(plan, decisions)
    got = render_markdown(updated)
    expected = (EXP / "fifo_plan.approved.md").read_text(encoding="utf-8")
    assert got == expected
