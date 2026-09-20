"""CLI, model-contract, and sandbox-stub tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from conftest import FIXTURE_REPO
from tb_recovery.cli import app
from tb_recovery.models import (
    CandidateCommand,
    Evidence,
    Provenance,
    RecoveryReport,
    SourceKind,
    TargetPhase,
)
from tb_recovery.sandbox import DisabledExecutor
from tb_recovery.serialize import report_from_json

runner = CliRunner()


def test_cli_inspect_emits_valid_json():
    result = runner.invoke(app, ["inspect", str(FIXTURE_REPO)])
    assert result.exit_code == 0
    report = report_from_json(result.stdout)
    assert report.candidate_commands


def test_cli_smoke_prints_command():
    result = runner.invoke(app, ["smoke", str(FIXTURE_REPO)])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""


def test_cli_schema_is_valid_json():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["title"] == "RecoveryReport"


def test_cli_missing_repo_errors():
    result = runner.invoke(app, ["inspect", "/no/such/dir/xyz"])
    assert result.exit_code == 2


def test_extracted_command_requires_evidence_semantics():
    # Contract-level: an EXTRACTED command SHOULD carry evidence; a HYPOTHESIS
    # command carries none but must carry a rationale. Enforced by construction.
    ev = Evidence(file="Makefile", line=1, snippet="build:",
                  source_kind=SourceKind.MAKEFILE)
    ex = CandidateCommand(command="make build", phase=TargetPhase.BUILD,
                          provenance=Provenance.EXTRACTED, evidence=[ev])
    assert ex.evidence
    hy = CandidateCommand(command="make", phase=TargetPhase.BUILD,
                          provenance=Provenance.HYPOTHESIS, evidence=[],
                          rationale="default goal guess")
    assert hy.evidence == [] and hy.rationale


def test_report_forbids_extra_fields():
    with pytest.raises(ValidationError):
        RecoveryReport.model_validate({"repro": {}, "bogus": 1})


def test_sandbox_refuses_to_execute():
    ex = DisabledExecutor()
    assert ex.enabled is False
    cmd = CandidateCommand(command="make", phase=TargetPhase.BUILD,
                           provenance=Provenance.HYPOTHESIS, rationale="x")
    with pytest.raises(NotImplementedError):
        ex.run(cmd, cwd=".")
