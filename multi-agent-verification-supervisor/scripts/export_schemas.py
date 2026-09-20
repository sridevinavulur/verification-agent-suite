"""Regenerate JSON Schemas for the public Pydantic contracts.

Usage:  python scripts/export_schemas.py
"""

from __future__ import annotations

import json
from pathlib import Path

from mav_supervisor import models as m

EXPORT = {
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


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "schemas"
    out.mkdir(exist_ok=True)
    for name, model in EXPORT.items():
        (out / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", name)


if __name__ == "__main__":
    main()
