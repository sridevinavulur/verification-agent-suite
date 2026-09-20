"""Golden tests for the five working queries against the demo graph."""

from __future__ import annotations

from vkg.graph import Graph
from vkg.queries import (
    coverage_holes_without_test,
    evidence_claims_without_benchmark,
    failures_affecting_interface,
    properties_depending_on_reset,
    requirements_without_assertions,
)


def _names(result, col):
    return sorted(r.fields[col] for r in result.rows)


def test_requirements_without_assertions(demo_graph: Graph):
    r = requirements_without_assertions(demo_graph)
    # REQ-FIFO-003 and REQ-ARB-002 have no asserting property.
    assert _names(r, "requirement") == ["REQ-ARB-002", "REQ-FIFO-003"]


def test_coverage_holes_without_test(demo_graph: Graph):
    r = coverage_holes_without_test(demo_graph)
    # holes: fifo_empty (has test), fifo_reset (no test), arb_fair (no test)
    assert _names(r, "coverage_bin") == ["arb_fairness", "fifo_reset_hit"]


def test_properties_depending_on_reset(demo_graph: Graph):
    r = properties_depending_on_reset(demo_graph, "por_rst")
    assert _names(r, "assertion") == ["fifo_no_overflow", "fifo_no_underflow"]

    r2 = properties_depending_on_reset(demo_graph, "arb_rst")
    assert _names(r2, "assertion") == ["arbiter_grant_onehot"]

    # case-insensitive match
    r3 = properties_depending_on_reset(demo_graph, "POR_RST")
    assert r3.count == 2


def test_properties_depending_on_unknown_reset(demo_graph: Graph):
    r = properties_depending_on_reset(demo_graph, "does_not_exist")
    assert r.count == 0


def test_failures_affecting_interface(demo_graph: Graph):
    r = failures_affecting_interface(demo_graph, "fifo.rd")
    assert _names(r, "failure") == ["fifo_no_underflow_cex"]

    # unqualified name also matches
    r2 = failures_affecting_interface(demo_graph, "req_grant")
    assert _names(r2, "failure") == ["arbiter_grant_onehot_cex"]

    # a TIMEOUT failure still shows up (with its status), and status is honest
    r3 = failures_affecting_interface(demo_graph, "wr")
    statuses = {row.fields["failure"]: row.fields["status"] for row in r3.rows}
    assert statuses == {"fifo_no_overflow_timeout": "TIMEOUT"}


def test_evidence_claims_without_benchmark(demo_graph: Graph):
    r = evidence_claims_without_benchmark(demo_graph)
    # C-SCALE has no benchmarks.
    assert _names(r, "claim") == ["C-SCALE"]
