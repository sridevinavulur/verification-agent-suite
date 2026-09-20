"""Export JSON Schema for the public Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import RegressionReport, TelemetryDataset

_EXPORTS = {
    "telemetry_dataset.schema.json": TelemetryDataset,
    "regression_report.schema.json": RegressionReport,
}


def export_all(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in _EXPORTS.items():
        schema = model.model_json_schema()
        path = out / filename
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
