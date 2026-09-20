"""Golden-output tests and end-to-end CLI/package tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from register_csr_agent.cli import app
from register_csr_agent.pipeline import run_from_files
from register_csr_agent.renderer import (
    render_coverage_matrix,
    render_discrepancy_report,
    render_sva_file,
)

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "examples" / "register_maps"
RTL = ROOT / "examples" / "rtl_symbols"
GOLDEN = ROOT / "examples" / "golden"

runner = CliRunner()


def test_golden_timer_sva():
    pkg = run_from_files(MAPS / "timer_block.yaml", RTL / "timer_block.json")
    got = render_sva_file(pkg)
    expected = (GOLDEN / "timer_block.candidate.sva").read_text()
    assert got == expected


def test_golden_timer_discrepancies():
    pkg = run_from_files(MAPS / "timer_block.yaml", RTL / "timer_block.json")
    got = render_discrepancy_report(pkg)
    expected = (GOLDEN / "timer_block.discrepancies.md").read_text()
    assert got == expected


def test_golden_timer_coverage():
    pkg = run_from_files(MAPS / "timer_block.yaml", RTL / "timer_block.json")
    got = render_coverage_matrix(pkg)
    expected = (GOLDEN / "timer_block.coverage.md").read_text()
    assert got == expected


def test_golden_buggy_discrepancies():
    pkg = run_from_files(MAPS / "buggy_block.json")
    got = render_discrepancy_report(pkg)
    expected = (GOLDEN / "buggy_block.discrepancies.md").read_text()
    assert got == expected


def test_cli_check_exits_nonzero_on_error():
    result = runner.invoke(app, ["check", str(MAPS / "buggy_block.json")])
    assert result.exit_code == 1
    assert "ERRORS: 7" in result.stdout


def test_cli_check_clean_exits_zero():
    result = runner.invoke(app, ["check", str(MAPS / "timer_block.yaml")])
    assert result.exit_code == 0


def test_cli_normalize_json_roundtrip():
    result = runner.invoke(app, ["normalize", str(MAPS / "gpio_block.csv")])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert {r["name"] for r in data["registers"]} == {"DATA", "DIR", "INT_STAT"}


def test_cli_package_writes_artifacts(tmp_path):
    out = tmp_path / "pkg"
    result = runner.invoke(
        app,
        [
            "package",
            str(MAPS / "timer_block.yaml"),
            str(RTL / "timer_block.json"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    for fname in (
        "package.json",
        "manifest.json",
        "candidate.sva",
        "discrepancies.md",
        "coverage.md",
        "grounding.md",
        "review_checklist.md",
    ):
        assert (out / fname).exists(), fname
    pkg = json.loads((out / "package.json").read_text())
    assert pkg["provenance"]["input_sha256"]  # provenance recorded
    assert pkg["candidate_sva"][0]["status"] == "candidate"


def test_cli_demo_runs():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "[clean]" in result.stdout and "[buggy]" in result.stdout
