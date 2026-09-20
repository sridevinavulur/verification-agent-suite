"""CLI smoke tests via Typer's CliRunner."""

import json

from typer.testing import CliRunner

from cx_triage.cli import app

runner = CliRunner()


def test_demo_runs():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Counterexample Triage Report" in result.stdout
    assert "design_bug" in result.stdout


def test_parse_summary(examples_dir):
    result = runner.invoke(
        app, ["parse", "--trace", str(examples_dir / "toy_counter" / "counter_fail.vcd")]
    )
    assert result.exit_code == 0
    assert "tb.count" in result.stdout


def test_triage_writes_json(tmp_path, examples_dir):
    out = tmp_path / "r.json"
    d = examples_dir / "toy_counter"
    result = runner.invoke(
        app,
        [
            "triage",
            "--trace", str(d / "counter_fail.vcd"),
            "--failure", str(d / "failure.json"),
            "--manifest", str(d / "manifest.json"),
            "--out-json", str(out),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["first_divergence_cycle"] == 6


def test_schema_export():
    result = runner.invoke(app, ["schema", "report"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "TriageReport"
