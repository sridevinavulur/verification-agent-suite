"""Loading and serialization helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import RegressionReport, TelemetryDataset


def load_dataset(path: str | Path) -> TelemetryDataset:
    """Load and validate a telemetry dataset from a JSON file."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return TelemetryDataset.model_validate(data)


def report_to_json(report: RegressionReport) -> str:
    """Deterministic, indented JSON serialization of a report."""
    return json.dumps(
        report.model_dump(mode="json"),
        indent=2,
        sort_keys=False,
    )


def write_report_json(report: RegressionReport, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report_to_json(report) + "\n", encoding="utf-8")
    return p
