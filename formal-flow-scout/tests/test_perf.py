"""Small generated-RTL performance/scaling test.

Not a benchmark of absolute speed (that lives in benchmarks/); this asserts the
graph core handles a non-trivial generated graph correctly and in bounded time.
"""

from __future__ import annotations

import time

from formal_flow_scout.graph_core import PackedGraph
from formal_flow_scout.models import (
    DependencyGraph,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
)


def _generate_pipeline(stages: int, width: int) -> DependencyGraph:
    """Generate a synthetic pipeline: `stages` register banks of `width` bits.

    Stage s register i depends (SEQ) on stage s-1 register i (a shift-register
    style chain), plus a COMB fan-in from a shared control net.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    ctrl_id = 0
    nodes.append(GraphNode(node_id=0, name="ctrl", kind=NodeKind.NET, module="gen"))
    nid = 1
    prev_bank: list[int] = []
    for s in range(stages):
        bank: list[int] = []
        for i in range(width):
            nodes.append(
                GraphNode(
                    node_id=nid, name=f"r{s}_{i}", kind=NodeKind.REG, module="gen"
                )
            )
            if prev_bank:
                edges.append(GraphEdge(src=nid, dst=prev_bank[i], kind=EdgeKind.SEQ))
            edges.append(GraphEdge(src=nid, dst=ctrl_id, kind=EdgeKind.COMB))
            bank.append(nid)
            nid += 1
        prev_bank = bank
    return DependencyGraph(nodes=nodes, edges=edges)


def test_generated_pipeline_coi_scales():
    stages, width = 200, 64  # ~12.8k regs, ~25k edges
    g = _generate_pipeline(stages, width)
    pg = PackedGraph(g)
    assert pg.n == stages * width + 1

    # COI of the last-stage register 0 = all upstream stage-0..N regs at index 0
    # plus ctrl. That is exactly `stages` regs + ctrl.
    last_stage_first = 1 + (stages - 1) * width
    t0 = time.perf_counter()
    coi = pg.backward_coi(
        [last_stage_first], combinational_only=False, include_control=False
    )
    dt = time.perf_counter() - t0
    assert len(coi) == stages + 1  # stages regs in the chain + ctrl
    assert dt < 5.0  # generous bound; typically milliseconds


def test_generated_pipeline_scc_is_acyclic():
    g = _generate_pipeline(50, 16)
    pg = PackedGraph(g)
    sccs = pg.tarjan_scc()
    # A feed-forward pipeline has no cycles.
    assert all(len(c) == 1 for c in sccs)
