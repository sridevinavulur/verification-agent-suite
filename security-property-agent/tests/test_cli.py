from __future__ import annotations

import json

from typer.testing import CliRunner

from security_property_agent.cli import app

runner = CliRunner()


def test_cli_run_writes_report(tmp_path, requirements_path, manifest_path):
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "run",
            str(requirements_path),
            "-m",
            str(manifest_path),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["run_id"]
    assert data["artifacts"]
    assert data["non_claims"]


def test_cli_run_stdout_json(requirements_path, manifest_path):
    result = runner.invoke(
        app, ["run", str(requirements_path), "-m", str(manifest_path)]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["manifest_top"] == "secure_soc"


def test_cli_missing_manifest_errors(tmp_path, requirements_path):
    result = runner.invoke(
        app, ["run", str(requirements_path), "-m", str(tmp_path / "nope.json")]
    )
    assert result.exit_code == 2


def test_cli_decompose(requirements_path):
    result = runner.invoke(app, ["decompose", str(requirements_path)])
    assert result.exit_code == 0, result.output
    assert "SEC-AC-001" in result.output


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()
