from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cdc_rdc_triage.manifest_models import Manifest
from cdc_rdc_triage.report_models import (
    Crossing,
    CrossingKind,
    Domain,
    Severity,
    SyncEvidence,
    TriageReport,
)
from cdc_rdc_triage.serialize import load_manifest


def test_manifest_ignores_extra_fields(examples_dir: Path) -> None:
    # The canonical manifest has many fields we don't model; loading must not fail.
    m = load_manifest(examples_dir / "cdc_sync.manifest.json")
    assert m.top == "cdc_sync"
    assert len(m.modules) == 1


def test_manifest_validates_types() -> None:
    with pytest.raises(ValidationError):
        Manifest.model_validate({"modules": [{"name": 123}]})  # name must be str


def test_risk_score_bounds() -> None:
    with pytest.raises(ValidationError):
        Crossing(
            kind=CrossingKind.cdc,
            module="m",
            src_signal="a",
            dst_signal="b",
            src_domain=Domain(clock="c1"),
            dst_domain=Domain(clock="c2"),
            sync_evidence=SyncEvidence.none_found,
            severity=Severity.high,
            risk_score=200,  # out of range
        )


def test_report_defaults_are_safe() -> None:
    r = TriageReport(tool_version="0.1.0")
    assert "NOT a CDC/RDC signoff" in r.disclaimer
    assert any("clean" in n.lower() for n in r.non_claims)
    # extra fields are forbidden on the output contract
    with pytest.raises(ValidationError):
        TriageReport.model_validate({"tool_version": "x", "bogus": 1})
