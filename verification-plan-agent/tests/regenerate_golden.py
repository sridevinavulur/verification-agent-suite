"""Regenerate the golden outputs in ``examples/expected/``.

Run after an intentional engine/report change::

    python tests/regenerate_golden.py

Uses a fixed provenance so the JSON goldens stay stable.
"""

from __future__ import annotations

from pathlib import Path

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
from vplan_agent.serialize import plan_to_json

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
EXP = EX / "expected"


def _prov() -> Provenance:
    return Provenance(command="<golden>", input_files=[], input_sha256={})


def _write(plan, name: str) -> None:
    (EXP / f"{name}_plan.json").write_text(plan_to_json(plan) + "\n", encoding="utf-8")
    (EXP / f"{name}_plan.md").write_text(render_markdown(plan), encoding="utf-8")


def main() -> None:
    EXP.mkdir(parents=True, exist_ok=True)

    fifo = build_plan(
        load_spec(EX / "fifo_spec.json"),
        load_interface(EX / "fifo_interface.json"),
        load_manifest_view(EX / "fifo_manifest.json"),
        load_existing_testplan(EX / "fifo_existing_testplan.json"),
        _prov(),
    )
    _write(fifo, "fifo")

    gpio = build_plan(
        load_spec(EX / "gpio_spec.json"),
        load_interface(EX / "gpio_interface.json"),
        load_manifest_view(EX / "gpio_manifest.json"),
        None,
        _prov(),
    )
    _write(gpio, "gpio")

    decisions = load_decisions(EX / "fifo_decisions.json")
    approved, _, _ = apply_decisions(fifo, decisions)
    (EXP / "fifo_plan.approved.json").write_text(
        plan_to_json(approved) + "\n", encoding="utf-8"
    )
    (EXP / "fifo_plan.approved.md").write_text(
        render_markdown(approved), encoding="utf-8"
    )
    print("Regenerated goldens in", EXP)


if __name__ == "__main__":
    main()
