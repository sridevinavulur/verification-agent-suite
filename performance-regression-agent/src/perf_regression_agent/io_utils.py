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


# Derived float metrics (cv, delta_pct, robust_z, CI bounds, ...) can differ in
# their lowest-order digits across Python versions/platforms due to float
# summation order. Rounding to 6 decimals is far coarser than that ~1e-11 drift
# yet far finer than the input precision, so serialized reports are byte-stable
# across environments (and the golden test stays meaningful on every Python).
_JSON_FLOAT_DIGITS = 6


def _round_floats(obj: object) -> object:
    """Recursively round every float in a JSON-able structure for determinism."""
    if isinstance(obj, bool):  # bool is a subclass of int — leave untouched
        return obj
    if isinstance(obj, float):
        return round(obj, _JSON_FLOAT_DIGITS)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v) for v in obj]
    return obj


def report_to_json(report: RegressionReport) -> str:
    """Deterministic, indented JSON serialization of a report."""
    return json.dumps(
        _round_floats(report.model_dump(mode="json")),
        indent=2,
        sort_keys=False,
    )


def write_report_json(report: RegressionReport, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report_to_json(report) + "\n", encoding="utf-8")
    return p
