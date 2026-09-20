from __future__ import annotations

import json
from pathlib import Path

from mav_supervisor import models as m

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

EXPECTED = [
    "VerificationTask", "RtlManifest", "CandidateProperty", "PartitionReport",
    "ExperimentPlan", "RunRecord", "ApprovalDecision", "AuditEvent", "EvidencePacket",
]


def test_all_schema_files_present_and_current() -> None:
    models = {
        "VerificationTask": m.VerificationTask,
        "RtlManifest": m.RtlManifest,
        "CandidateProperty": m.CandidateProperty,
        "PartitionReport": m.PartitionReport,
        "ExperimentPlan": m.ExperimentPlan,
        "RunRecord": m.RunRecord,
        "ApprovalDecision": m.ApprovalDecision,
        "AuditEvent": m.AuditEvent,
        "EvidencePacket": m.EvidencePacket,
    }
    assert sorted(models) == sorted(EXPECTED)
    for name, model in models.items():
        path = SCHEMA_DIR / f"{name}.schema.json"
        assert path.exists(), f"missing schema file for {name}"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == model.model_json_schema(), (
            f"{name}.schema.json is stale; run scripts/export_schemas.py"
        )


def test_extra_fields_are_forbidden() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        m.VerificationTask(
            task_id="t", repo_revision="r", requirement_text="x",
            not_a_field=True,  # type: ignore[call-arg]
        )
