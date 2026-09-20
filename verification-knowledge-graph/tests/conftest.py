"""Shared fixtures: build a graph from the bundled examples."""

from __future__ import annotations

from pathlib import Path

import pytest

from vkg.graph import Graph
from vkg.importers import (
    import_coverage_summary,
    import_evidence,
    import_rtl_intent_manifest,
    import_run_ledger,
    import_sva_intent,
    import_test_plan,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture()
def demo_graph() -> Graph:
    """An in-memory graph populated from every example artifact."""
    g = Graph(":memory:")
    import_rtl_intent_manifest(g, EXAMPLES / "rtl_intent_manifest.json")
    import_sva_intent(g, EXAMPLES / "sva_intent.json")
    import_test_plan(g, EXAMPLES / "test_plan.json")
    import_coverage_summary(g, EXAMPLES / "coverage_summary.json")
    import_run_ledger(g, EXAMPLES / "run_ledger.json")
    import_evidence(g, EXAMPLES / "evidence_claims.json")
    return g
