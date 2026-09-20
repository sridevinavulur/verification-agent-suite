"""Shared test fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assertion_review.review import review_file

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"
GOLDEN = EXAMPLES / "golden"

# (sva relative path, manifest relative path or None)
CORPUS: list[tuple[str, str | None]] = [
    ("good/handshake_good.sv", "manifests/handshake.manifest.json"),
    ("good/fifo_good.sv", "manifests/fifo.manifest.json"),
    ("bad/handshake_bad.sv", "manifests/handshake.manifest.json"),
    ("bad/fifo_bad.sv", "manifests/fifo.manifest.json"),
]


def golden_name(sva_rel: str) -> str:
    return sva_rel.replace("/", "__").replace(".sv", ".golden.json")


def summarize(sva_rel: str, manifest_rel: str | None) -> dict:
    """Deterministic, human-reviewable summary used as the golden fixture."""
    manifest_path = str(EXAMPLES / manifest_rel) if manifest_rel else None
    report = review_file(str(EXAMPLES / sva_rel), manifest_path=manifest_path)
    score = report.score()
    return {
        "source": sva_rel,
        "manifest": manifest_rel,
        "property_count": report.property_count,
        "counts": report.counts(),
        "score": score.score,
        "grade": score.grade,
        "findings": [
            {
                "line": f.location.line,
                "check_id": f.check_id.value,
                "severity": f.severity.value,
                "property": f.property_name,
                "heuristic": f.heuristic,
            }
            for f in report.findings
        ],
    }


@pytest.fixture(params=CORPUS, ids=[c[0] for c in CORPUS])
def corpus_case(request: pytest.FixtureRequest) -> tuple[str, str | None]:
    return request.param


def load_golden(sva_rel: str) -> dict:
    return json.loads((GOLDEN / golden_name(sva_rel)).read_text())
