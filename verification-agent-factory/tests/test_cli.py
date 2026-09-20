"""End-to-end CLI tests using Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from verification_agent_factory.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def test_validate_manifest_valid():
    r = runner.invoke(app, ["validate-manifest", str(EXAMPLES / "spec_to_sva_manifest.json")])
    assert r.exit_code == 0
    assert "VALID" in r.stdout


def test_validate_manifest_invalid_exits_nonzero():
    r = runner.invoke(
        app, ["validate-manifest", str(EXAMPLES / "invalid_manifest_overclaim.json")]
    )
    assert r.exit_code == 1
    assert "INVALID" in r.stdout


def test_generate_schema_stdout():
    r = runner.invoke(app, ["generate-schema"])
    assert r.exit_code == 0
    assert "VerificationAgentManifest" in r.stdout


def test_generate_docs():
    r = runner.invoke(app, ["generate-docs", str(EXAMPLES / "spec_to_sva_manifest.json")])
    assert r.exit_code == 0
    assert "This agent must not claim" in r.stdout


def test_run_mock_demo_deterministic():
    a = runner.invoke(app, ["run-mock-demo", "--seed", "1"])
    b = runner.invoke(app, ["run-mock-demo", "--seed", "1"])
    assert a.exit_code == 0
    assert a.stdout == b.stdout
    assert "MOCK-LLM" in a.stdout


def test_init_agent_then_audit(tmp_path: Path):
    dest = tmp_path / "generated"
    r = runner.invoke(
        app,
        ["init-agent", str(EXAMPLES / "spec_to_sva_manifest.json"), "--dest", str(dest)],
    )
    assert r.exit_code == 0, r.stdout
    assert (dest / "pyproject.toml").exists()
    assert (dest / "src" / "spec_to_sva_agent" / "agent.py").exists()

    # Audit the freshly generated tree: it must be clean.
    a = runner.invoke(app, ["audit-public-release", str(dest)])
    assert a.exit_code == 0, a.stdout
    assert "No blocking findings" in a.stdout


def test_audit_finds_planted_secret(tmp_path: Path):
    (tmp_path / "bad.py").write_text('api_key = "abcdef123456"\n')  # audit: allow (fixture written at runtime)
    r = runner.invoke(app, ["audit-public-release", str(tmp_path)])
    assert r.exit_code == 1
    assert "BLOCKING" in r.stdout
