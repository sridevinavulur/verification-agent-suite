"""Tests for the optional C++ core bridge.

These skip cleanly when the C++ binary has not been built, so the suite is green
with no compiler (per BUILD_STANDARD.md).
"""

from __future__ import annotations

import pytest

from formal_flow_scout import parse_verilog
from formal_flow_scout.cpp_bridge import (
    CppCoreUnavailable,
    coi_via_cpp,
    find_cpp_binary,
)
from formal_flow_scout.graph_builder import build_from_parse
from formal_flow_scout.graph_core import PackedGraph

_HAS_CPP = find_cpp_binary() is not None


def test_bridge_raises_when_unavailable(monkeypatch):
    # Force "not found" and confirm the typed error is raised (Python fallback).
    monkeypatch.setattr(
        "formal_flow_scout.cpp_bridge.find_cpp_binary", lambda: None
    )
    from formal_flow_scout.models import DependencyGraph

    pg = PackedGraph(DependencyGraph(nodes=[], edges=[]))
    with pytest.raises(CppCoreUnavailable):
        coi_via_cpp(pg, [], combinational_only=False)


@pytest.mark.skipif(not _HAS_CPP, reason="C++ core not built")
def test_cpp_agrees_with_python(examples_dir):
    parse = parse_verilog((examples_dir / "fifo_ctrl.v").read_text(), "fifo_ctrl.v")
    graph = build_from_parse(parse)
    pg = PackedGraph(graph)
    seeds = [pg.id_of("fifo_ctrl.full")]
    seeds = [s for s in seeds if s is not None]
    cpp = coi_via_cpp(pg, seeds, combinational_only=False)
    py = sorted(
        pg.backward_coi(seeds, combinational_only=False, include_control=True)
    )
    assert cpp == py
