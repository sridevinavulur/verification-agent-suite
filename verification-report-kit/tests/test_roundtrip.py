"""Round-trip and CLI-path tests."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from verification_report_kit import load_json, write_json
from verification_report_kit.cli import app
from verification_report_kit.examples_data import coverage_report

runner = CliRunner()


def test_json_roundtrip(tmp_path: Path) -> None:
    original = coverage_report()
    p = write_json(original, tmp_path / "r.json")
    loaded = load_json(p)
    assert loaded.model_dump() == original.model_dump()


def test_cli_render(tmp_path: Path) -> None:
    original = coverage_report()
    jp = write_json(original, tmp_path / "r.json")
    out = tmp_path / "r.html"
    result = runner.invoke(app, ["render", "--in", str(jp), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    html = out.read_text()
    assert "Coverage Closure Report" in html


def test_cli_validate(tmp_path: Path) -> None:
    jp = write_json(coverage_report(), tmp_path / "r.json")
    result = runner.invoke(app, ["validate", "--in", str(jp)])
    assert result.exit_code == 0
    assert "OK:" in result.output


def test_cli_demo(tmp_path: Path) -> None:
    out = tmp_path / "demo.html"
    result = runner.invoke(app, ["demo", "--kind", "findings", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "Counterexample" in out.read_text()
