"""End-to-end CLI tests using Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from vkg.cli import app

runner = CliRunner()


def test_build_demo_query_and_export(tmp_path):
    db = str(tmp_path / "kg.db")

    r = runner.invoke(app, ["build-demo", "--db", db])
    assert r.exit_code == 0, r.output
    assert "Built demo graph" in r.output

    r = runner.invoke(
        app, ["query", "requirements-without-assertions", "--db", db]
    )
    assert r.exit_code == 0, r.output
    assert "REQ-FIFO-003" in r.output
    assert "REQ-ARB-002" in r.output

    r = runner.invoke(
        app, ["query", "properties-depending-on-reset", "por_rst", "--db", db]
    )
    assert r.exit_code == 0, r.output
    assert "fifo_no_overflow" in r.output

    dot_out = tmp_path / "kg.dot"
    r = runner.invoke(app, ["export", "dot", "--db", db, "--out", str(dot_out)])
    assert r.exit_code == 0, r.output
    assert dot_out.read_text().startswith("digraph")

    r = runner.invoke(app, ["export", "json", "--db", db])
    assert r.exit_code == 0, r.output
    assert '"schema_version"' in r.output


def test_query_missing_parametric_arg(tmp_path):
    db = str(tmp_path / "kg.db")
    runner.invoke(app, ["build-demo", "--db", db])
    r = runner.invoke(app, ["query", "failures-affecting-interface", "--db", db])
    assert r.exit_code == 2


def test_import_single_artifact(tmp_path):
    from tests.conftest import EXAMPLES

    db = str(tmp_path / "one.db")
    r = runner.invoke(
        app, ["import", "rtl", str(EXAMPLES / "rtl_intent_manifest.json"), "--db", db]
    )
    assert r.exit_code == 0, r.output
    assert "nodes touched" in r.output
