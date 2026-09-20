"""Contract / validation tests for the typed models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from _ledger_helpers import make_record
from formal_regression_intelligence.models import RunLedger, RunRecord, RunStatus


def test_pass_requires_return_code_zero():
    with pytest.raises(ValidationError):
        make_record(run_id="r1", status="PASS", return_code=1)


def test_timeout_is_not_success_and_not_conclusive():
    r = make_record(run_id="r1", status="TIMEOUT", return_code=124)
    assert r.status is RunStatus.TIMEOUT
    assert not r.status.is_success
    assert not r.status.is_conclusive


def test_pass_and_fail_are_conclusive():
    assert RunStatus.PASS.is_conclusive
    assert RunStatus.FAIL.is_conclusive
    assert not RunStatus.INCONCLUSIVE.is_conclusive


def test_job_key_and_signature():
    r = make_record(run_id="r1", benchmark="b1", config_id="cfg-x")
    assert r.job_key == "b1::cfg-x"
    assert r.signature_fields == (r.design_sha, r.property_sha, "cfg-x", "cat-v1")


def test_extra_fields_ignored_for_interop():
    # A newer orchestrator adds a field we do not model; ingestion must not break.
    r = make_record(run_id="r1")
    payload = r.model_dump(mode="json")
    payload["some_future_field"] = {"nested": 1}
    parsed = RunRecord.model_validate(payload)
    assert parsed.run_id == "r1"


def test_empty_ledger_rejected():
    with pytest.raises(ValidationError):
        RunLedger(records=[])
