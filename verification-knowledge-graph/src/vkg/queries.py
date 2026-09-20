"""Working queries over the Verification Knowledge Graph (spec 6.12).

Each query is a deterministic graph traversal returning a structured
:class:`~vkg.models.QueryResult` (stable column order, sorted rows). These are
plain Python over the SQLite-backed adjacency -- no LLM, no heuristics. The
graph records relationships; these queries surface gaps in that recorded state.
"""

from __future__ import annotations

from .graph import Graph
from .models import EdgeType, NodeType, QueryResult, QueryResultRow


def _sorted_rows(rows: list[dict[str, str]], key: str) -> list[QueryResultRow]:
    return [QueryResultRow(fields=r) for r in sorted(rows, key=lambda r: r[key])]


def requirements_without_assertions(g: Graph) -> QueryResult:
    """Which requirements lack assertions?

    A requirement is uncovered if no assertion node has an ``ASSERTS`` edge
    pointing to it.
    """
    rows: list[dict[str, str]] = []
    for req in g.nodes(NodeType.REQUIREMENT):
        asserters = g.in_edges(req.id, EdgeType.ASSERTS)
        if not asserters:
            rows.append({"requirement_id": req.id, "requirement": req.name})
    return QueryResult(
        query="requirements_without_assertions",
        description="Requirements with no linked assertion (ASSERTS edge)",
        columns=["requirement_id", "requirement"],
        rows=_sorted_rows(rows, "requirement"),
    )


def coverage_holes_without_test(g: Graph) -> QueryResult:
    """Which coverage holes have no linked test?

    A coverage hole is a bin with ``hole == "true"`` (hits < goal). It is
    "unlinked" if no test node has a ``COVERS`` edge pointing to it.
    """
    rows: list[dict[str, str]] = []
    for cbin in g.nodes(NodeType.COVERAGE_BIN):
        if cbin.attrs.get("hole") != "true":
            continue
        coverers = g.in_edges(cbin.id, EdgeType.COVERS)
        if not coverers:
            rows.append(
                {
                    "coverage_bin_id": cbin.id,
                    "coverage_bin": cbin.name,
                    "hits": cbin.attrs.get("hits", "?"),
                    "goal": cbin.attrs.get("goal", "?"),
                }
            )
    return QueryResult(
        query="coverage_holes_without_test",
        description="Coverage holes (hits<goal) with no linked test (COVERS edge)",
        columns=["coverage_bin_id", "coverage_bin", "hits", "goal"],
        rows=_sorted_rows(rows, "coverage_bin"),
    )


def properties_depending_on_reset(g: Graph, reset_name: str) -> QueryResult:
    """Which properties depend on a given reset domain?

    Finds assertion nodes with a ``DEPENDS_ON_RESET`` edge to the named reset
    domain. Reset domain is matched by node name (case-insensitive).
    """
    target = None
    for rd in g.nodes(NodeType.RESET_DOMAIN):
        if rd.name.lower() == reset_name.lower():
            target = rd
            break
    rows: list[dict[str, str]] = []
    if target is not None:
        for e in g.in_edges(target.id, EdgeType.DEPENDS_ON_RESET):
            node = g.get_node(e.src)
            if node is not None and node.type == NodeType.ASSERTION:
                rows.append({"assertion_id": node.id, "assertion": node.name})
    return QueryResult(
        query="properties_depending_on_reset",
        description=f"Assertions depending on reset domain '{reset_name}'",
        columns=["assertion_id", "assertion"],
        rows=_sorted_rows(rows, "assertion"),
    )


def failures_affecting_interface(g: Graph, interface_name: str) -> QueryResult:
    """Which failures affect a given interface?

    Only FAIL-status failure nodes with an ``AFFECTS_INTERFACE`` edge to a
    matching interface are returned. Interface is matched by name
    (case-insensitive); a ``module.iface`` argument matches the qualified
    interface exactly.
    """
    want_mod = None
    want_if = interface_name
    if "." in interface_name:
        want_mod, want_if = interface_name.split(".", 1)

    target_ids: set[str] = set()
    for iface in g.nodes(NodeType.INTERFACE):
        if iface.name.lower() != want_if.lower():
            continue
        if want_mod is not None and iface.attrs.get("module", "").lower() != want_mod.lower():
            continue
        target_ids.add(iface.id)

    rows: list[dict[str, str]] = []
    for iid in target_ids:
        for e in g.in_edges(iid, EdgeType.AFFECTS_INTERFACE):
            fnode = g.get_node(e.src)
            if fnode is None or fnode.type != NodeType.FAILURE:
                continue
            rows.append(
                {
                    "failure_id": fnode.id,
                    "failure": fnode.name,
                    "status": fnode.attrs.get("status", "?"),
                }
            )
    # de-duplicate (a failure may hit the same iface via multiple targets)
    seen: dict[str, dict[str, str]] = {r["failure_id"]: r for r in rows}
    return QueryResult(
        query="failures_affecting_interface",
        description=f"Failures affecting interface '{interface_name}'",
        columns=["failure_id", "failure", "status"],
        rows=_sorted_rows(list(seen.values()), "failure"),
    )


def evidence_claims_without_benchmark(g: Graph) -> QueryResult:
    """Which EVIDENCE.md claims lack a linked benchmark?

    An evidence claim is unsupported if it has no ``SUPPORTED_BY`` edge to a
    benchmark node.
    """
    rows: list[dict[str, str]] = []
    for claim in g.nodes(NodeType.EVIDENCE_CLAIM):
        links = g.out_edges(claim.id, EdgeType.SUPPORTED_BY)
        if not links:
            rows.append(
                {
                    "claim_id": claim.id,
                    "claim": claim.name,
                    "text": claim.attrs.get("text", ""),
                }
            )
    return QueryResult(
        query="evidence_claims_without_benchmark",
        description="EVIDENCE.md claims with no linked benchmark (SUPPORTED_BY edge)",
        columns=["claim_id", "claim", "text"],
        rows=_sorted_rows(rows, "claim"),
    )


# Registry for the CLI. Parametric queries take a positional arg.
QUERIES = {
    "requirements-without-assertions": requirements_without_assertions,
    "coverage-holes-without-test": coverage_holes_without_test,
    "properties-depending-on-reset": properties_depending_on_reset,
    "failures-affecting-interface": failures_affecting_interface,
    "evidence-claims-without-benchmark": evidence_claims_without_benchmark,
}

PARAMETRIC_QUERIES = {
    "properties-depending-on-reset",
    "failures-affecting-interface",
}
