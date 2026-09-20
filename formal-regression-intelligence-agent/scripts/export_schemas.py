"""Export the Pydantic JSON Schemas to schemas/.

Usage:  python scripts/export_schemas.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from formal_regression_intelligence.models import RegressionReport, RunRecord  # noqa: E402

SCHEMAS = ROOT / "schemas"

_EXPORTS = {
    "run_record.schema.json": RunRecord,
    "regression_report.schema.json": RegressionReport,
}


def main() -> None:
    SCHEMAS.mkdir(exist_ok=True)
    for filename, model in _EXPORTS.items():
        path = SCHEMAS / filename
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
