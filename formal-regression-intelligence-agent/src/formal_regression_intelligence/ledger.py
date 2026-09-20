"""Run-ledger ingestion.

Accepts either a JSON array of run records or a JSONL file (one record per line).
Both formats are produced by / compatible with ``formal-run-orchestrator`` ledger
exports. Malformed records are surfaced explicitly rather than silently dropped
(safety: never hide a run).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import RunLedger, RunRecord


def _iter_json_objects(text: str) -> list[dict]:
    """Parse a document that is either a JSON array or newline-delimited JSON."""
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("top-level JSON must be an array of run records")
        return data
    # JSONL: one object per non-empty line.
    objs: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            objs.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON on line {lineno}: {e}") from e
    return objs


def load_ledger(path: str | Path) -> RunLedger:
    """Load and validate a run ledger from a .json or .jsonl file.

    Raises ``ValueError`` with the offending index if any record fails to
    validate, so a bad producer is reported, not swallowed.
    """
    p = Path(path)
    text = p.read_text()
    raw = _iter_json_objects(text)

    records: list[RunRecord] = []
    for idx, obj in enumerate(raw):
        try:
            records.append(RunRecord.model_validate(obj))
        except ValidationError as e:
            rid = obj.get("run_id", f"<index {idx}>") if isinstance(obj, dict) else f"<index {idx}>"
            raise ValueError(f"run record {rid} failed validation:\n{e}") from e
    return RunLedger(records=records)
