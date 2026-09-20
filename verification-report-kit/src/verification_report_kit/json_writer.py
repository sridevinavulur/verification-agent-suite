"""Deterministic JSON report writer.

Adapted from the JSON report writer in
``spec-to-cov-agent/veri_forge/utils/report.py`` (read-only reference), but
made generic and deterministic: no implicit timestamps, stable key ordering,
and a trailing newline so the file is diff-/golden-friendly.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import ReportModel


def to_json(report: ReportModel, *, indent: int = 2) -> str:
    """Serialize a report to a deterministic JSON string.

    ``mode="json"`` ensures enums/paths become plain strings. Keys are emitted
    in the field-declaration order of the model (stable across runs).
    """
    data = report.model_dump(mode="json", exclude_none=False)
    return json.dumps(data, indent=indent, sort_keys=False) + "\n"


def write_json(report: ReportModel, path: str | Path, *, indent: int = 2) -> Path:
    """Write a report to ``path`` as JSON. Returns the written path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(report, indent=indent), encoding="utf-8")
    return out


def load_json(path: str | Path) -> ReportModel:
    """Load and validate a report from a JSON file."""
    return ReportModel.model_validate_json(Path(path).read_text(encoding="utf-8"))
