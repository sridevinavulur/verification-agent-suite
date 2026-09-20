"""CLI and reporting tests via Typer's CliRunner."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from formal_flow_scout.cli import app

runner = CliRunner()


def test_cli_analyze_rtl_emits_valid_report(examples_dir, tmp_path):
    out = tmp_path / "rep.json"
    dot = tmp_path / "rep.dot"
    result = runner.invoke(
        app,
        [
            "analyze",
            str(examples_dir / "fifo_property.json"),
            "--rtl",
            str(examples_dir / "fifo_ctrl.v"),
            "-o",
            str(out),
            "--dot",
            str(dot),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["property_name"] == "no_overflow"
    assert data["coi_node_ids"]
    assert data["stats"]["total_nodes"] > 0
    # DOT is non-empty and well-formed enough.
    dot_text = dot.read_text()
    assert dot_text.startswith("digraph coi {")
    assert dot_text.rstrip().endswith("}")
    assert "->" in dot_text


def test_cli_analyze_manifest(examples_dir, tmp_path):
    out = tmp_path / "rep.json"
    result = runner.invoke(
        app,
        [
            "analyze",
            str(examples_dir / "counter_property.json"),
            "--manifest",
            str(examples_dir / "counter_manifest.json"),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["provenance"]["graph_core"] == "python"
    assert data["provenance"]["input_sha256"]  # hashes recorded


def test_cli_build_graph(examples_dir):
    result = runner.invoke(
        app,
        ["build-graph", "--rtl", str(examples_dir / "counter.v")],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["top"] == "counter"
    assert data["nodes"]


def test_cli_schema_exports_json_schema():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["title"] == "CoiReport"
    assert "properties" in schema


def test_cli_demo_runs():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "FormalFlow-Scout COI report" in result.output


def test_cli_requires_input_source(examples_dir):
    result = runner.invoke(
        app, ["analyze", str(examples_dir / "counter_property.json")]
    )
    assert result.exit_code != 0
