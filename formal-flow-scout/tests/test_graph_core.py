"""Unit tests for the packed graph core: CSR, COI traversal, Tarjan SCC."""

from __future__ import annotations

import pytest

from formal_flow_scout.graph_core import PackedGraph
from formal_flow_scout.models import (
    DependencyGraph,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
)


def _mk(nodes: int, edges: list[tuple[int, int, EdgeKind]]) -> DependencyGraph:
    return DependencyGraph(
        nodes=[
            GraphNode(node_id=i, name=f"n{i}", kind=NodeKind.NET, module="m")
            for i in range(nodes)
        ],
        edges=[GraphEdge(src=s, dst=d, kind=k) for (s, d, k) in edges],
    )


def test_csr_neighbours_sorted_and_deterministic():
    # Edges given out of order; CSR must sort by (dst, kind).
    g = _mk(3, [(0, 2, EdgeKind.COMB), (0, 1, EdgeKind.COMB)])
    pg = PackedGraph(g)
    assert [d for d, _ in pg.neighbours(0)] == [1, 2]


def test_rejects_non_dense_ids():
    g = DependencyGraph(
        nodes=[GraphNode(node_id=5, name="x", kind=NodeKind.NET, module="m")],
        edges=[],
    )
    with pytest.raises(ValueError):
        PackedGraph(g)


def test_backward_coi_combinational_stops_at_seq():
    # 0 -SEQ-> 1 -COMB-> 2 ; comb-only COI from 0 excludes 1,2 (behind a reg edge)
    g = _mk(3, [(0, 1, EdgeKind.SEQ), (1, 2, EdgeKind.COMB)])
    pg = PackedGraph(g)
    comb = pg.backward_coi([0], combinational_only=True, include_control=False)
    assert comb == {0}
    seq = pg.backward_coi([0], combinational_only=False, include_control=False)
    assert seq == {0, 1, 2}


def test_backward_coi_over_approximation_chain():
    # linear comb chain 0<-1<-2<-3 ; COI from 0 is everything upstream.
    g = _mk(4, [(0, 1, EdgeKind.COMB), (1, 2, EdgeKind.COMB), (2, 3, EdgeKind.COMB)])
    pg = PackedGraph(g)
    assert pg.backward_coi([0], combinational_only=True, include_control=False) == {
        0,
        1,
        2,
        3,
    }
    # Seeds that are leaves have a COI of just themselves.
    assert pg.backward_coi([3], combinational_only=True, include_control=False) == {3}


def test_tarjan_simple_cycle():
    # 0->1->2->0 is one cyclic SCC.
    g = _mk(
        3,
        [(0, 1, EdgeKind.COMB), (1, 2, EdgeKind.COMB), (2, 0, EdgeKind.COMB)],
    )
    pg = PackedGraph(g)
    sccs = pg.tarjan_scc()
    cyclic = [c for c in sccs if len(c) > 1]
    assert len(cyclic) == 1
    assert set(cyclic[0]) == {0, 1, 2}


def test_tarjan_dag_all_singletons():
    g = _mk(3, [(0, 1, EdgeKind.COMB), (1, 2, EdgeKind.COMB)])
    pg = PackedGraph(g)
    sccs = pg.tarjan_scc()
    assert all(len(c) == 1 for c in sccs)
    assert len(sccs) == 3


def test_tarjan_subset_restriction():
    g = _mk(
        4,
        [(0, 1, EdgeKind.COMB), (1, 0, EdgeKind.COMB), (2, 3, EdgeKind.COMB)],
    )
    pg = PackedGraph(g)
    sccs = pg.tarjan_scc(subset={0, 1})
    assert sorted(len(c) for c in sccs) == [2]


def test_self_loop_detection():
    g = _mk(2, [(0, 0, EdgeKind.COMB)])
    pg = PackedGraph(g)
    assert pg.has_self_loop(0)
    assert not pg.has_self_loop(1)


def test_control_edges_excluded_from_comb_coi_unless_requested():
    g = _mk(2, [(0, 1, EdgeKind.CLOCK)])
    pg = PackedGraph(g)
    assert pg.backward_coi([0], combinational_only=True, include_control=False) == {0}
    assert pg.backward_coi([0], combinational_only=True, include_control=True) == {0, 1}
