"""End-to-end CLI tests using Typer's runner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from conftest import EXAMPLES_DIR
from rtl_intent.cli import app
from rtl_intent.serialize import manifest_from_json

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "rtl-intent" in result.stdout


def test_adapters_lists_builtin() -> None:
    result = runner.invoke(app, ["adapters"])
    assert result.exit_code == 0
    assert "builtin" in result.stdout


def test_ingest_stdout_is_valid_manifest() -> None:
    result = runner.invoke(app, ["ingest", str(EXAMPLES_DIR / "counter.sv")])
    assert result.exit_code == 0
    manifest = manifest_from_json(result.stdout)
    assert manifest.top == "counter"
    assert manifest.get_module("counter") is not None


def test_ingest_writes_json_and_markdown(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    md = tmp_path / "m.md"
    result = runner.invoke(
        app,
        [
            "ingest",
            str(EXAMPLES_DIR / "valid_ready.sv"),
            "-o",
            str(out),
            "-m",
            str(md),
            "--top",
            "vr_top",
        ],
    )
    assert result.exit_code == 0
    manifest = manifest_from_json(out.read_text())
    assert manifest.top == "vr_top"
    assert len(manifest.hierarchy) == 2
    text = md.read_text()
    assert "# RTL Intent Manifest" in text
    assert "vr_producer" in text


def test_summary_markdown() -> None:
    result = runner.invoke(app, ["summary", str(EXAMPLES_DIR / "fifo_queue.sv")])
    assert result.exit_code == 0
    assert "Clock & reset candidates (heuristic)" in result.stdout
    assert "Parser limitations" in result.stdout


def test_schema_is_valid_json() -> None:
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "Manifest"


def test_missing_file_errors() -> None:
    result = runner.invoke(app, ["ingest", "does_not_exist.sv"])
    assert result.exit_code == 2
