from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from coverage_closure_agent.cli import app

runner = CliRunner()

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_cli_demo_runs():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0, result.output
    assert "Coverage Closure Triage Report" in result.output
    assert "Enforced Prohibited Actions" in result.output


def test_cli_triage_json(tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["triage", str(EXAMPLES / "toy_benchmark.json"), "--out", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["scope_provenance"]["total_holes"] == 9
    assert len(data["classifications"]) == 9


def test_cli_metrics(tmp_path):
    result = runner.invoke(
        app,
        ["metrics", str(EXAMPLES / "toy_benchmark.json"), str(EXAMPLES / "toy_labels.json")],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["category_precision"] == 1.0
    assert data["valid_proposal_rate"] == 1.0


def test_cli_schema(tmp_path):
    result = runner.invoke(app, ["schema", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "triage_inputs.schema.json").exists()
    assert (tmp_path / "triage_report.schema.json").exists()
