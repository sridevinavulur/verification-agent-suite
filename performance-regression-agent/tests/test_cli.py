"""End-to-end CLI tests via Typer's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from perf_regression_agent.cli import app

runner = CliRunner()

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "examples" / "telemetry" / "benchmark.json"


def test_version():
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0
    assert res.stdout.strip()


def test_demo_runs_and_reports_regressions():
    res = runner.invoke(app, ["demo"])
    assert res.exit_code == 0
    assert "regressions=2" in res.stdout
    assert "sim_runtime_s" in res.stdout


def test_analyze_writes_reports(tmp_path: Path):
    jp = tmp_path / "r.json"
    mp = tmp_path / "r.md"
    res = runner.invoke(
        app, ["analyze", str(BENCHMARK), "--json", str(jp), "--md", str(mp)]
    )
    assert res.exit_code == 0
    data = json.loads(jp.read_text())
    assert data["n_regressions"] == 2
    assert "# Performance Regression Report" in mp.read_text()


def test_analyze_fail_on_regression_exit_code(tmp_path: Path):
    res = runner.invoke(app, ["analyze", str(BENCHMARK), "--fail-on-regression"])
    assert res.exit_code == 1


def test_gen_benchmark_roundtrip(tmp_path: Path):
    out = tmp_path / "bench.json"
    res = runner.invoke(app, ["gen-benchmark", str(out)])
    assert res.exit_code == 0
    data = json.loads(out.read_text())
    assert len(data["runs"]) == 20


def test_export_schemas(tmp_path: Path):
    res = runner.invoke(app, ["export-schemas", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "telemetry_dataset.schema.json").exists()
    assert (tmp_path / "regression_report.schema.json").exists()
