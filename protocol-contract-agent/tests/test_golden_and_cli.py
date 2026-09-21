"""Golden-output regression + CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from protocol_contract_agent.cli import app
from protocol_contract_agent.generator import generate_contract
from protocol_contract_agent.report import render_sva_file
from tests.conftest import ALL_NAMES, EXAMPLES, _pair

runner = CliRunner()


@pytest.mark.parametrize("name", ALL_NAMES)
def test_golden_sva_matches(name):
    req, man = _pair(name)
    c = generate_contract(req, man)
    produced = render_sva_file(c)
    golden = (EXAMPLES / "golden_contracts" / f"{name}.sva").read_text().rstrip("\n")
    assert produced.rstrip("\n") == golden, (
        f"golden mismatch for {name}; regenerate with the CLI if intended"
    )


def test_cli_protocols():
    res = runner.invoke(app, ["protocols"])
    assert res.exit_code == 0
    assert "valid_ready" in res.output
    assert "credit_return" in res.output


def test_cli_demo_runs():
    res = runner.invoke(app, ["demo"])
    assert res.exit_code == 0
    assert "TOTAL candidate properties" in res.output
    assert "NON-CLAIMS" in res.output


def test_cli_generate_markdown(tmp_path: Path):
    res = runner.invoke(app, [
        "generate",
        str(EXAMPLES / "specs" / "fifo.json"),
        str(EXAMPLES / "rtl_manifests" / "fifo.json"),
        "-f", "markdown",
    ])
    assert res.exit_code == 0
    assert "# Interface Contract" in res.output
    assert "Review checklist" in res.output


def test_cli_generate_json_out(tmp_path: Path):
    out = tmp_path / "c.json"
    res = runner.invoke(app, [
        "generate",
        str(EXAMPLES / "specs" / "valid_ready.json"),
        str(EXAMPLES / "rtl_manifests" / "valid_ready.json"),
        "-f", "json", "--out", str(out),
    ])
    assert res.exit_code == 0
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert data["protocol"] == "valid_ready"
    assert data["provenance"]["input_sha256"]  # hashed inputs recorded


def test_cli_mutate():
    res = runner.invoke(app, [
        "mutate",
        str(EXAMPLES / "specs" / "req_grant.json"),
        str(EXAMPLES / "rtl_manifests" / "req_grant.json"),
    ])
    assert res.exit_code == 0
    assert "TOTAL mutants" in res.output


def test_cli_export_schemas(tmp_path: Path):
    res = runner.invoke(app, ["export-schemas", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "protocol_contract.schema.json").exists()
    assert (tmp_path / "contract_request.schema.json").exists()
