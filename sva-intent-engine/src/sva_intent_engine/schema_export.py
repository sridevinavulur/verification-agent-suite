"""Export JSON Schema for the public Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CandidateProperty,
    DecompositionResult,
    GroundingResult,
    Provenance,
    Requirement,
    ReviewReport,
    RTLManifest,
    TemporalIntent,
    ValidationReport,
)

EXPORTS = {
    "requirement": Requirement,
    "decomposition_result": DecompositionResult,
    "rtl_manifest": RTLManifest,
    "grounding_result": GroundingResult,
    "temporal_intent": TemporalIntent,
    "candidate_property": CandidateProperty,
    "validation_report": ValidationReport,
    "review_report": ReviewReport,
    "provenance": Provenance,
}


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in EXPORTS.items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
        written.append(path)
    return written
