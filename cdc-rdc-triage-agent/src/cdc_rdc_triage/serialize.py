"""Byte-stable JSON serialization for triage reports (for golden tests)."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest_models import Manifest
from .report_models import TriageReport


def report_to_json(report: TriageReport, *, indent: int = 2) -> str:
    data = report.model_dump(mode="json")
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
