"""Stable JSON serialization for recovery reports.

Uses Pydantic v2 ``model_dump(mode="json")`` with sorted keys so output is
byte-stable across runs and platforms - required for golden tests.

``repo_root`` and every path the tool emits (``inspected_files``,
``file_hashes`` keys, evidence ``file`` pointers, and the ``command`` string)
are already portable *by construction* in ``recover()`` - the repo root is
recorded relative to itself (``.``) and no absolute path is persisted. The
remaining checkout-specific fields are ``git_sha`` and ``file_hashes`` (content
hashes shift with line-endings/edits), which ``report_to_json_stable``
normalizes for portable golden comparisons.
"""

from __future__ import annotations

import json

from .models import RecoveryReport


def report_to_json(report: RecoveryReport, *, indent: int = 2) -> str:
    return json.dumps(
        report.model_dump(mode="json"),
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def report_to_json_stable(report: RecoveryReport, *, indent: int = 2) -> str:
    """Serialize with checkout-specific fields normalized (for golden tests).

    ``repo_root`` is already portable (``.``) so it is left untouched.
    ``git_sha``/``file_hashes`` vary by checkout, so they are replaced with
    stable placeholders rather than dropped - this keeps the output a *valid*
    ``RecoveryReport`` that still round-trips through the model. ``command`` is
    left as produced (already stripped of any absolute path by ``recover()``).
    """
    data = report.model_dump(mode="json")
    repro = data.get("repro", {})
    repro["git_sha"] = None
    repro["file_hashes"] = {}
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def report_from_json(text: str) -> RecoveryReport:
    return RecoveryReport.model_validate_json(text)
