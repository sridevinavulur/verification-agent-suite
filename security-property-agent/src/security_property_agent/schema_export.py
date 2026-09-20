"""Export JSON Schema for the primary Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import RequirementSet, SecurityReviewReport

_EXPORTS = {
    "requirement_set.schema.json": RequirementSet,
    "security_review_report.schema.json": SecurityReviewReport,
}


def export_all(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in _EXPORTS.items():
        path = out / filename
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written


if __name__ == "__main__":  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "schemas"
    for p in export_all(target):
        print(f"wrote {p}")
