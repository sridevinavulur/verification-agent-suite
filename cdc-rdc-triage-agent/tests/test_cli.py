from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cdc_rdc_triage.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "cdc-rdc-triage" in result.stdout


def test_triage_stdout(examples_dir: Path) -> None:
    manifest = examples_dir / "cdc_sync.manifest.json"
    result = runner.invoke(app, ["triage", str(manifest)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["summary"]["total_crossings"] == 2
    assert data["disclaimer"]


def test_triage_writes_files(examples_dir: Path, tmp_path: Path) -> None:
    manifest = examples_dir / "rdc_example.manifest.json"
    out = tmp_path / "r.json"
    md = tmp_path / "r.md"
    result = runner.invoke(
        app, ["triage", str(manifest), "-o", str(out), "-m", str(md)]
    )
    assert result.exit_code == 0
    assert out.is_file() and md.is_file()
    assert "HEURISTIC" in md.read_text()


def test_report_markdown(examples_dir: Path) -> None:
    manifest = examples_dir / "single_clock.manifest.json"
    result = runner.invoke(app, ["report", str(manifest)])
    assert result.exit_code == 0
    assert "No candidate CDC/RDC crossings" in result.stdout
    assert "NOT a clean result" in result.stdout or "not a clean" in result.stdout.lower()


def test_missing_manifest_errors() -> None:
    result = runner.invoke(app, ["triage", "does_not_exist.json"])
    assert result.exit_code == 2


def test_schema_command() -> None:
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "TriageReport"


def test_triage_with_glossary(examples_dir: Path, tmp_path: Path) -> None:
    glossary = tmp_path / "g.json"
    glossary.write_text(json.dumps({"cells": []}))
    manifest = examples_dir / "cdc_sync.manifest.json"
    result = runner.invoke(app, ["triage", str(manifest), "-g", str(glossary)])
    assert result.exit_code == 0
