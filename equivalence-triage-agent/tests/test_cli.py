from __future__ import annotations

import json

from typer.testing import CliRunner

from eq_triage.cli import app

runner = CliRunner()


def test_cli_parse(toy_alu):
    r = runner.invoke(app, ["parse", "--log", str(toy_alu / "equivalence.eqlog")])
    assert r.exit_code == 0, r.output
    assert "status: NOT_EQUIVALENT" in r.output
    assert "mismatches: 5" in r.output


def test_cli_demo_toy_alu():
    r = runner.invoke(app, ["demo", "toy_alu", "--no-narrate"])
    assert r.exit_code == 0, r.output
    assert "Equivalence Mismatch-Localization Report" in r.output
    assert "width" in r.output
    assert "polarity" in r.output


def test_cli_demo_toy_counter():
    r = runner.invoke(app, ["demo", "toy_counter", "--no-narrate"])
    assert r.exit_code == 0, r.output
    assert "state_encoding" in r.output
    assert "gating" in r.output


def test_cli_triage_json_out(tmp_path, toy_alu):
    out = tmp_path / "report.json"
    r = runner.invoke(
        app,
        [
            "triage",
            "--log", str(toy_alu / "equivalence.eqlog"),
            "--ref-manifest", str(toy_alu / "ref_manifest.json"),
            "--rev-manifest", str(toy_alu / "rev_manifest.json"),
            "--source-map", str(toy_alu / "source_map.json"),
            "--out-json", str(out),
        ],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(out.read_text())
    assert data["reported_status"] == "NOT_EQUIVALENT"
    assert data["groups"]
    # provenance recorded input hashes
    assert data["provenance"]["input_sha256"]


def test_cli_schema():
    r = runner.invoke(app, ["schema", "report"])
    assert r.exit_code == 0, r.output
    schema = json.loads(r.output)
    assert schema["title"] == "TriageReport"


def test_cli_narrate_disclaimer():
    r = runner.invoke(app, ["demo", "toy_alu", "--narrate"])
    assert r.exit_code == 0
    assert "advisory" in r.output.lower()
    assert "not a proof" in r.output.lower()
