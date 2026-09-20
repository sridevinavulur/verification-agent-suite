from __future__ import annotations

import json
from pathlib import Path

from coverage_closure_agent.report import render_markdown
from coverage_closure_agent.triage import TriageEngine

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_golden_json_report(toy_inputs):
    report = TriageEngine(seed=0).run(toy_inputs)
    produced = report.model_dump(mode="json")
    golden = json.loads((EXAMPLES / "toy_report.golden.json").read_text())
    assert produced == golden


def test_golden_markdown_report(toy_inputs):
    report = TriageEngine(seed=0).run(toy_inputs)
    produced = render_markdown(report)
    golden = (EXAMPLES / "toy_report.golden.md").read_text()
    assert produced == golden
