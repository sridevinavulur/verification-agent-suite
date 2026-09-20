"""Importers that turn verification artifacts into typed graph nodes/edges.

Each importer reads a JSON file (one of the five artifact shapes documented
below) and upserts nodes/edges into a :class:`~vkg.graph.Graph`. Importers are
deterministic and idempotent -- re-running the same import produces the same
graph.

Compatible JSON shapes
----------------------
These shapes are intentionally simple and align with the sibling tools where
reasonable (``schema_version`` header, snake_case keys, source locations). The
exact shapes accepted are documented on each importer and demonstrated in
``examples/``. Only the fields the graph needs are consumed; unknown extra
fields are ignored so the importer stays tolerant of richer sibling outputs.

Provenance: every node/edge records the artifact name, source path, a locator,
and the sha256 of the source file for reproducibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph import Graph
from .ids import edge_id, hash_file_bytes, node_id
from .models import Edge, EdgeType, Node, NodeType, SourceProvenance


def _load(path: str | Path) -> tuple[dict[str, Any], str, str]:
    """Load a JSON file, returning (data, path_str, sha256)."""
    p = Path(path)
    raw = p.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{p}: expected a JSON object at top level")
    return data, str(p), hash_file_bytes(raw)


def _prov(artifact: str, src: str, digest: str, locator: str | None = None) -> SourceProvenance:
    return SourceProvenance(
        artifact=artifact, source_file=src, locator=locator, input_hash=digest
    )


def _n(g: Graph, node: Node) -> str:
    g.add_node(node)
    return node.id


def _e(
    g: Graph,
    etype: EdgeType,
    src: str,
    dst: str,
    prov: SourceProvenance,
    attrs: dict[str, str] | None = None,
) -> None:
    g.add_edge(
        Edge(
            id=edge_id(etype, src, dst),
            type=etype,
            src=src,
            dst=dst,
            attrs=attrs or {},
            provenance=prov,
        )
    )


# --------------------------------------------------------------------------- #
# 1. RTL Intent Manifest
# --------------------------------------------------------------------------- #
def import_rtl_intent_manifest(g: Graph, path: str | Path) -> int:
    """Import an RTL Intent Manifest.

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "modules": [
            {
              "name": "fifo",
              "interfaces": [{"name": "wr", "signals": ["wr_en", "full"]}],
              "signals": [{"name": "wr_en"}, {"name": "rd_en"}],
              "reset_domains": [{"name": "por_rst"}],
              "signal_reset_domain": {"wr_en": "por_rst"}
            }
          ]
        }

    Creates module/interface/signal/reset_domain nodes and structural edges.
    Returns the number of nodes touched.
    """
    data, src, digest = _load(path)
    prov = _prov("rtl_intent_manifest", src, digest)
    touched = 0
    for m in data.get("modules", []):
        mname = m["name"]
        mid = _n(
            g,
            Node(
                id=node_id(NodeType.MODULE, mname),
                type=NodeType.MODULE,
                name=mname,
                provenance=_prov("rtl_intent_manifest", src, digest, f"module {mname}"),
            ),
        )
        touched += 1

        # reset domains
        for rd in m.get("reset_domains", []):
            rname = rd["name"] if isinstance(rd, dict) else str(rd)
            rid = _n(
                g,
                Node(
                    id=node_id(NodeType.RESET_DOMAIN, rname),
                    type=NodeType.RESET_DOMAIN,
                    name=rname,
                    provenance=_prov(
                        "rtl_intent_manifest", src, digest, f"reset_domain {rname}"
                    ),
                ),
            )
            _e(g, EdgeType.RESET_OF, rid, mid, prov)
            touched += 1

        # interfaces
        iface_of_signal: dict[str, str] = {}
        for iface in m.get("interfaces", []):
            iname = iface["name"]
            # interface natural key is module-qualified so two modules can
            # both expose "wr" without colliding.
            iid = _n(
                g,
                Node(
                    id=node_id(NodeType.INTERFACE, mname, iname),
                    type=NodeType.INTERFACE,
                    name=iname,
                    attrs={"module": mname},
                    provenance=_prov(
                        "rtl_intent_manifest", src, digest, f"interface {mname}.{iname}"
                    ),
                ),
            )
            _e(g, EdgeType.EXPOSES, mid, iid, prov)
            touched += 1
            for sname in iface.get("signals", []):
                iface_of_signal[sname] = iid

        # signals
        sig_reset = m.get("signal_reset_domain", {})
        for sig in m.get("signals", []):
            sname = sig["name"] if isinstance(sig, dict) else str(sig)
            sid = _n(
                g,
                Node(
                    id=node_id(NodeType.SIGNAL, mname, sname),
                    type=NodeType.SIGNAL,
                    name=sname,
                    attrs={"module": mname},
                    provenance=_prov(
                        "rtl_intent_manifest", src, digest, f"signal {mname}.{sname}"
                    ),
                ),
            )
            _e(g, EdgeType.IN_MODULE, sid, mid, prov)
            touched += 1
            if sname in iface_of_signal:
                _e(g, EdgeType.ON_INTERFACE, sid, iface_of_signal[sname], prov)
            rd_name = sig_reset.get(sname)
            if rd_name:
                _e(
                    g,
                    EdgeType.DEPENDS_ON_RESET,
                    sid,
                    node_id(NodeType.RESET_DOMAIN, rd_name),
                    prov,
                )
    g.commit()
    return touched


# --------------------------------------------------------------------------- #
# 2. SVA Intent output
# --------------------------------------------------------------------------- #
def import_sva_intent(g: Graph, path: str | Path) -> int:
    """Import SVA Intent Engine output (candidate properties).

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "properties": [
            {
              "id": "P_wr_when_not_full",
              "name": "wr_when_not_full",
              "module": "fifo",
              "requirement_ids": ["REQ-FIFO-002"],
              "reset_domains": ["por_rst"],
              "interfaces": ["wr"]
            }
          ]
        }

    Creates assertion nodes and ASSERTS / IN_MODULE / DEPENDS_ON_RESET /
    ON_INTERFACE edges. Requirement nodes are created if absent (a property may
    reference a requirement not yet imported from the test plan).
    """
    data, src, digest = _load(path)
    prov = _prov("sva_intent", src, digest)
    touched = 0
    for p in data.get("properties", []):
        pkey = p.get("id") or p["name"]
        aid = _n(
            g,
            Node(
                id=node_id(NodeType.ASSERTION, pkey),
                type=NodeType.ASSERTION,
                name=p.get("name", pkey),
                attrs={"module": p.get("module", "")},
                provenance=_prov("sva_intent", src, digest, f"property {pkey}"),
            ),
        )
        touched += 1
        if p.get("module"):
            _e(
                g,
                EdgeType.IN_MODULE,
                aid,
                node_id(NodeType.MODULE, p["module"]),
                prov,
            )
        for rid in p.get("requirement_ids", []):
            req_id = node_id(NodeType.REQUIREMENT, rid)
            # ensure requirement node exists (stub name = its natural key)
            if g.get_node(req_id) is None:
                _n(
                    g,
                    Node(
                        id=req_id,
                        type=NodeType.REQUIREMENT,
                        name=rid,
                        provenance=_prov(
                            "sva_intent", src, digest, f"requirement ref {rid}"
                        ),
                    ),
                )
            _e(g, EdgeType.ASSERTS, aid, req_id, prov)
        for rd in p.get("reset_domains", []):
            _e(
                g,
                EdgeType.DEPENDS_ON_RESET,
                aid,
                node_id(NodeType.RESET_DOMAIN, rd),
                prov,
            )
        for iname in p.get("interfaces", []):
            mod = p.get("module", "")
            _e(
                g,
                EdgeType.ON_INTERFACE,
                aid,
                node_id(NodeType.INTERFACE, mod, iname),
                prov,
            )
    g.commit()
    return touched


# --------------------------------------------------------------------------- #
# 3. Test plan
# --------------------------------------------------------------------------- #
def import_test_plan(g: Graph, path: str | Path) -> int:
    """Import a test plan / requirement-to-test matrix.

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "requirements": [
            {"id": "REQ-FIFO-001", "text": "FIFO shall not overflow"}
          ],
          "tests": [
            {
              "id": "T_fifo_overflow",
              "name": "fifo_overflow_directed",
              "requirement_ids": ["REQ-FIFO-001"],
              "coverage_bins": ["cov_fifo_full"]
            }
          ]
        }

    Creates requirement/test nodes and TESTS / COVERS edges.
    """
    data, src, digest = _load(path)
    prov = _prov("test_plan", src, digest)
    touched = 0
    for r in data.get("requirements", []):
        rkey = r["id"]
        _n(
            g,
            Node(
                id=node_id(NodeType.REQUIREMENT, rkey),
                type=NodeType.REQUIREMENT,
                name=rkey,
                attrs={"text": r.get("text", "")},
                provenance=_prov("test_plan", src, digest, f"requirement {rkey}"),
            ),
        )
        touched += 1
    for t in data.get("tests", []):
        tkey = t.get("id") or t["name"]
        tid = _n(
            g,
            Node(
                id=node_id(NodeType.TEST, tkey),
                type=NodeType.TEST,
                name=t.get("name", tkey),
                provenance=_prov("test_plan", src, digest, f"test {tkey}"),
            ),
        )
        touched += 1
        for rid in t.get("requirement_ids", []):
            req_id = node_id(NodeType.REQUIREMENT, rid)
            if g.get_node(req_id) is None:
                _n(
                    g,
                    Node(
                        id=req_id,
                        type=NodeType.REQUIREMENT,
                        name=rid,
                        provenance=_prov(
                            "test_plan", src, digest, f"requirement ref {rid}"
                        ),
                    ),
                )
            _e(g, EdgeType.TESTS, tid, req_id, prov)
        for cbin in t.get("coverage_bins", []):
            _e(g, EdgeType.COVERS, tid, node_id(NodeType.COVERAGE_BIN, cbin), prov)
    g.commit()
    return touched


# --------------------------------------------------------------------------- #
# 4. Coverage summary
# --------------------------------------------------------------------------- #
def import_coverage_summary(g: Graph, path: str | Path) -> int:
    """Import a coverage summary.

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "bins": [
            {
              "id": "cov_fifo_full",
              "name": "fifo_full_hit",
              "module": "fifo",
              "interface": "wr",
              "hits": 0,
              "goal": 1
            }
          ]
        }

    Creates coverage_bin nodes (with a ``hole`` attr when hits < goal) and
    COVERAGE_OF edges to the module/interface they measure.
    """
    data, src, digest = _load(path)
    prov = _prov("coverage_summary", src, digest)
    touched = 0
    for b in data.get("bins", []):
        bkey = b.get("id") or b["name"]
        hits = int(b.get("hits", 0))
        goal = int(b.get("goal", 1))
        is_hole = hits < goal
        cid = _n(
            g,
            Node(
                id=node_id(NodeType.COVERAGE_BIN, bkey),
                type=NodeType.COVERAGE_BIN,
                name=b.get("name", bkey),
                attrs={
                    "hits": str(hits),
                    "goal": str(goal),
                    "hole": "true" if is_hole else "false",
                    "module": b.get("module", ""),
                },
                provenance=_prov("coverage_summary", src, digest, f"bin {bkey}"),
            ),
        )
        touched += 1
        if b.get("module"):
            _e(
                g,
                EdgeType.COVERAGE_OF,
                cid,
                node_id(NodeType.MODULE, b["module"]),
                prov,
            )
        if b.get("interface"):
            _e(
                g,
                EdgeType.COVERAGE_OF,
                cid,
                node_id(NodeType.INTERFACE, b.get("module", ""), b["interface"]),
                prov,
            )
    g.commit()
    return touched


# --------------------------------------------------------------------------- #
# 5. Run ledger
# --------------------------------------------------------------------------- #
def import_run_ledger(g: Graph, path: str | Path) -> int:
    """Import a run ledger (regressions, failures, waivers, bugs).

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "runs": [
            {
              "id": "reg_2026_09_20",
              "name": "nightly",
              "failures": [
                {
                  "id": "F_wr_when_not_full",
                  "status": "FAIL",
                  "target_assertion": "P_wr_when_not_full",
                  "target_test": null,
                  "interfaces": ["wr"],
                  "waiver": null,
                  "bug": "BUG-123"
                }
              ]
            }
          ]
        }

    Follows the shared result vocabulary: only ``FAIL`` failures are recorded
    as failures. TIMEOUT/ERROR/UNKNOWN are recorded on the failure node's
    ``status`` attr and never treated as a pass. Creates regression/failure/
    waiver/bug nodes and PRODUCED / FAILURE_OF / AFFECTS_INTERFACE / WAIVES /
    FILED_AS edges.
    """
    data, src, digest = _load(path)
    prov = _prov("run_ledger", src, digest)
    touched = 0
    for run in data.get("runs", []):
        rkey = run.get("id") or run["name"]
        rid = _n(
            g,
            Node(
                id=node_id(NodeType.REGRESSION, rkey),
                type=NodeType.REGRESSION,
                name=run.get("name", rkey),
                provenance=_prov("run_ledger", src, digest, f"run {rkey}"),
            ),
        )
        touched += 1
        for f in run.get("failures", []):
            fkey = f.get("id") or f["name"]
            status = f.get("status", "FAIL").upper()
            fid = _n(
                g,
                Node(
                    id=node_id(NodeType.FAILURE, fkey),
                    type=NodeType.FAILURE,
                    name=f.get("name", fkey),
                    attrs={"status": status},
                    provenance=_prov("run_ledger", src, digest, f"failure {fkey}"),
                ),
            )
            touched += 1
            _e(g, EdgeType.PRODUCED, rid, fid, prov)
            if f.get("target_assertion"):
                _e(
                    g,
                    EdgeType.FAILURE_OF,
                    fid,
                    node_id(NodeType.ASSERTION, f["target_assertion"]),
                    prov,
                )
            if f.get("target_test"):
                _e(
                    g,
                    EdgeType.FAILURE_OF,
                    fid,
                    node_id(NodeType.TEST, f["target_test"]),
                    prov,
                )
            for iname in f.get("interfaces", []):
                # interfaces on a failure may be module-qualified "mod.iface"
                if "." in iname:
                    mod, ifn = iname.split(".", 1)
                else:
                    mod, ifn = f.get("module", ""), iname
                _e(
                    g,
                    EdgeType.AFFECTS_INTERFACE,
                    fid,
                    node_id(NodeType.INTERFACE, mod, ifn),
                    prov,
                )
            if f.get("waiver"):
                wkey = f["waiver"]
                wid = _n(
                    g,
                    Node(
                        id=node_id(NodeType.WAIVER, wkey),
                        type=NodeType.WAIVER,
                        name=wkey,
                        provenance=_prov("run_ledger", src, digest, f"waiver {wkey}"),
                    ),
                )
                touched += 1
                _e(g, EdgeType.WAIVES, wid, fid, prov)
            if f.get("bug"):
                bkey = f["bug"]
                bid = _n(
                    g,
                    Node(
                        id=node_id(NodeType.BUG, bkey),
                        type=NodeType.BUG,
                        name=bkey,
                        provenance=_prov("run_ledger", src, digest, f"bug {bkey}"),
                    ),
                )
                touched += 1
                _e(g, EdgeType.FILED_AS, fid, bid, prov)
    g.commit()
    return touched


# --------------------------------------------------------------------------- #
# 6. EVIDENCE.md claims + benchmark links
# --------------------------------------------------------------------------- #
def import_evidence(g: Graph, path: str | Path) -> int:
    """Import EVIDENCE.md claims and their benchmark links.

    Expected shape (subset consumed)::

        {
          "schema_version": "0.1.0",
          "claims": [
            {
              "id": "C1",
              "text": "Importers run on sample data",
              "benchmarks": ["examples/"]
            }
          ]
        }

    Creates evidence_claim nodes and SUPPORTED_BY edges to benchmark nodes.
    A claim with no benchmarks has no outgoing SUPPORTED_BY edge (that is what
    the "claims lacking a linked benchmark" query detects).
    """
    data, src, digest = _load(path)
    prov = _prov("evidence", src, digest)
    touched = 0
    for c in data.get("claims", []):
        ckey = c.get("id") or c["text"][:40]
        cid = _n(
            g,
            Node(
                id=node_id(NodeType.EVIDENCE_CLAIM, ckey),
                type=NodeType.EVIDENCE_CLAIM,
                name=ckey,
                attrs={"text": c.get("text", "")},
                provenance=_prov("evidence", src, digest, f"claim {ckey}"),
            ),
        )
        touched += 1
        for bench in c.get("benchmarks", []):
            bid = _n(
                g,
                Node(
                    id=node_id(NodeType.BENCHMARK, bench),
                    type=NodeType.BENCHMARK,
                    name=bench,
                    provenance=_prov("evidence", src, digest, f"benchmark {bench}"),
                ),
            )
            touched += 1
            _e(g, EdgeType.SUPPORTED_BY, cid, bid, prov)
    g.commit()
    return touched


# Registry so the CLI can dispatch by name.
IMPORTERS = {
    "rtl": import_rtl_intent_manifest,
    "sva": import_sva_intent,
    "testplan": import_test_plan,
    "coverage": import_coverage_summary,
    "runledger": import_run_ledger,
    "evidence": import_evidence,
}
