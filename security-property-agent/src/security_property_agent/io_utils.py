"""Input/output helpers: load requirement sets, dump reports as JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import RequirementSet, SecurityReviewReport


def load_requirement_set(path: str | Path) -> RequirementSet:
    """Load a requirement set from YAML or JSON, validated by Pydantic."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data: Any
    if p.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    return RequirementSet.model_validate(data)


def dump_report(report: SecurityReviewReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=False)


def write_report(report: SecurityReviewReport, path: str | Path) -> None:
    Path(path).write_text(dump_report(report) + "\n", encoding="utf-8")
