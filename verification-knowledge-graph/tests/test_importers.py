"""Golden tests for the importers against bundled example artifacts."""

from __future__ import annotations

from tests.conftest import EXAMPLES
from vkg.graph import Graph
from vkg.ids import node_id
from vkg.importers import import_rtl_intent_manifest, import_sva_intent
from vkg.models import EdgeType, NodeType


def test_rtl_import_creates_expected_nodes(demo_graph: Graph):
    modules = {n.name for n in demo_graph.nodes(NodeType.MODULE)}
    assert modules == {"fifo", "arbiter"}

    resets = {n.name for n in demo_graph.nodes(NodeType.RESET_DOMAIN)}
    assert resets == {"por_rst", "arb_rst"}

    ifaces = {n.name for n in demo_graph.nodes(NodeType.INTERFACE)}
    assert ifaces == {"wr", "rd", "req_grant"}


def test_rtl_signal_reset_domain_edge():
    g = Graph(":memory:")
    import_rtl_intent_manifest(g, EXAMPLES / "rtl_intent_manifest.json")
    count_sig = node_id(NodeType.SIGNAL, "fifo", "count")
    por = node_id(NodeType.RESET_DOMAIN, "por_rst")
    deps = [e.dst for e in g.out_edges(count_sig, EdgeType.DEPENDS_ON_RESET)]
    assert por in deps


def test_sva_import_links_assertion_to_requirement_and_reset():
    g = Graph(":memory:")
    import_sva_intent(g, EXAMPLES / "sva_intent.json")
    a = node_id(NodeType.ASSERTION, "P_no_overflow")
    req = node_id(NodeType.REQUIREMENT, "REQ-FIFO-001")
    por = node_id(NodeType.RESET_DOMAIN, "por_rst")
    assert req in [e.dst for e in g.out_edges(a, EdgeType.ASSERTS)]
    assert por in [e.dst for e in g.out_edges(a, EdgeType.DEPENDS_ON_RESET)]


def test_import_is_idempotent(demo_graph: Graph):
    before = demo_graph.stats()
    import_rtl_intent_manifest(demo_graph, EXAMPLES / "rtl_intent_manifest.json")
    import_sva_intent(demo_graph, EXAMPLES / "sva_intent.json")
    after = demo_graph.stats()
    assert before == after


def test_run_ledger_records_status_not_pass(demo_graph: Graph):
    failures = demo_graph.nodes(NodeType.FAILURE)
    statuses = {f.name: f.attrs["status"] for f in failures}
    # timeout stays a timeout; never a pass
    assert statuses["fifo_no_overflow_timeout"] == "TIMEOUT"
    assert statuses["fifo_no_underflow_cex"] == "FAIL"


def test_provenance_has_input_hash(demo_graph: Graph):
    for n in demo_graph.nodes(NodeType.MODULE):
        assert n.provenance.input_hash
        assert n.provenance.artifact == "rtl_intent_manifest"
