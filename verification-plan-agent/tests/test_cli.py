"""End-to-end CLI tests via Typer's runner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vplan_agent.cli import app
from vplan_agent.serialize import plan_from_json

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vplan" in result.stdout


def test_cli_plan_to_stdout():
    result = runner.invoke(app, [
        "plan",
        "--spec", str(EX / "fifo_spec.json"),
        "--interface", str(EX / "fifo_interface.json"),
        "--manifest", str(EX / "fifo_manifest.json"),
    ])
    assert result.exit_code == 0
    plan = plan_from_json(result.stdout)
    assert plan.design_name == "sync_fifo"
    assert plan.plan_items


def test_cli_plan_writes_files(tmp_path: Path):
    out = tmp_path / "plan.json"
    md = tmp_path / "plan.md"
    result = runner.invoke(app, [
        "plan",
        "--spec", str(EX / "fifo_spec.json"),
        "--interface", str(EX / "fifo_interface.json"),
        "--manifest", str(EX / "fifo_manifest.json"),
        "--existing", str(EX / "fifo_existing_testplan.json"),
        "--out", str(out),
        "--markdown", str(md),
    ])
    assert result.exit_code == 0
    assert out.exists() and md.exists()
    plan = plan_from_json(out.read_text())
    # Provenance recorded input hashes for real runs.
    assert plan.provenance.input_sha256
    assert "sync_fifo" in md.read_text()


def test_cli_approve_roundtrip(tmp_path: Path):
    out = tmp_path / "plan.json"
    runner.invoke(app, [
        "plan",
        "--spec", str(EX / "fifo_spec.json"),
        "--interface", str(EX / "fifo_interface.json"),
        "--manifest", str(EX / "fifo_manifest.json"),
        "--out", str(out),
    ])
    approved = tmp_path / "approved.json"
    result = runner.invoke(app, [
        "approve", str(out),
        "--decisions", str(EX / "fifo_decisions.json"),
        "--out", str(approved),
    ])
    assert result.exit_code == 0
    plan = plan_from_json(approved.read_text())
    counts = plan.counts_by_approval()
    assert counts["approved"] == 2
    assert counts["rejected"] == 1


def test_cli_report(tmp_path: Path):
    out = tmp_path / "plan.json"
    runner.invoke(app, [
        "plan",
        "--spec", str(EX / "gpio_spec.json"),
        "--interface", str(EX / "gpio_interface.json"),
        "--manifest", str(EX / "gpio_manifest.json"),
        "--out", str(out),
    ])
    result = runner.invoke(app, ["report", str(out)])
    assert result.exit_code == 0
    assert "Traceability matrix" in result.stdout


def test_cli_schema_is_valid_json():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "VerificationPlan"


def test_cli_rejects_non_mock_llm():
    result = runner.invoke(app, [
        "plan",
        "--spec", str(EX / "fifo_spec.json"),
        "--interface", str(EX / "fifo_interface.json"),
        "--llm", "openai",
    ])
    assert result.exit_code != 0
