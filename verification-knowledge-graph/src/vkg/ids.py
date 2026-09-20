"""Stable, deterministic ID generation for graph nodes and edges.

Node IDs are derived from the node *type* plus a *natural key* (the identifying
tuple for that node kind, e.g. module name, or module+signal). This makes
imports idempotent and lets independent importers reference the same entity
without coordination: the SVA importer and the RTL importer both compute the
same ID for module ``fifo``.

IDs are human-readable prefixes plus a short hash suffix, so DOT output and
query rows stay legible while remaining collision-resistant.
"""

from __future__ import annotations

import hashlib

from .models import EdgeType, NodeType

# Short prefixes keep DOT/JSON readable.
_TYPE_PREFIX: dict[NodeType, str] = {
    NodeType.REQUIREMENT: "req",
    NodeType.MODULE: "mod",
    NodeType.INTERFACE: "if",
    NodeType.SIGNAL: "sig",
    NodeType.RESET_DOMAIN: "rst",
    NodeType.ASSERTION: "asrt",
    NodeType.TEST: "test",
    NodeType.COVERAGE_BIN: "cov",
    NodeType.REGRESSION: "reg",
    NodeType.FAILURE: "fail",
    NodeType.WAIVER: "wvr",
    NodeType.BUG: "bug",
    NodeType.EVIDENCE_CLAIM: "clm",
    NodeType.BENCHMARK: "bench",
}


def _norm(part: str) -> str:
    """Normalize a natural-key part: lowercase, collapse whitespace."""
    return "_".join(part.strip().lower().split())


def node_id(node_type: NodeType, *key_parts: str) -> str:
    """Compute a stable node ID from a type and natural-key parts.

    The same ``(type, key_parts)`` always yields the same ID. Empty or
    ``None`` key parts are rejected because an ID without a natural key is
    not stable.
    """
    parts = [p for p in key_parts if p is not None and str(p).strip() != ""]
    if not parts:
        raise ValueError(f"node_id for {node_type} requires a non-empty natural key")
    normalized = "|".join(_norm(str(p)) for p in parts)
    digest = hashlib.sha1(f"{node_type.value}|{normalized}".encode()).hexdigest()[:8]
    prefix = _TYPE_PREFIX[node_type]
    return f"{prefix}:{normalized}:{digest}"


def edge_id(edge_type: EdgeType, src: str, dst: str) -> str:
    """Compute a stable edge ID from its type and endpoints."""
    digest = hashlib.sha1(f"{edge_type.value}|{src}|{dst}".encode()).hexdigest()[:10]
    return f"e:{edge_type.value}:{digest}"


def hash_file_bytes(data: bytes) -> str:
    """sha256 of raw file bytes, for provenance/reproducibility."""
    return hashlib.sha256(data).hexdigest()
