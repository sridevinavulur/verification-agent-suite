"""Typed Pydantic v2 data contracts for the Verification Knowledge Graph.

The graph is a set of typed **nodes** and typed directed **edges**. Every node
carries a *stable ID* (deterministically derived from its natural key) and a
*source provenance* record pointing back to the artifact it was imported from.

These models are the strict, validated interface between:

    importers (RTL manifest / SVA output / test plan / coverage / run ledger)
        -> Graph (in-memory + SQLite persistence)
            -> queries and exporters (JSON / Graphviz DOT)

Nothing here performs LLM interpretation. Every field is populated by
deterministic import logic. The graph *records relationships*; it does not
decide correctness, proof status, or signoff.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Bumped when the graph schema changes in a backward-incompatible way.
GRAPH_SCHEMA_VERSION = "0.1.0"


class _Strict(BaseModel):
    """Base model: forbid unknown keys so the contract stays tight."""

    model_config = ConfigDict(extra="forbid")


class NodeType(StrEnum):
    """Typed node kinds tracked by the graph (spec 6.12)."""

    REQUIREMENT = "requirement"
    MODULE = "module"
    INTERFACE = "interface"
    SIGNAL = "signal"
    RESET_DOMAIN = "reset_domain"
    ASSERTION = "assertion"
    TEST = "test"
    COVERAGE_BIN = "coverage_bin"
    REGRESSION = "regression"
    FAILURE = "failure"
    WAIVER = "waiver"
    BUG = "bug"
    EVIDENCE_CLAIM = "evidence_claim"
    BENCHMARK = "benchmark"


class EdgeType(StrEnum):
    """Typed directed edge kinds.

    Direction convention: the edge points from ``src`` to ``dst`` in the
    natural reading of the verb. For example ``ASSERTS`` goes from an
    assertion to the requirement it asserts; ``COVERS`` goes from a test to
    the coverage bin it covers.
    """

    # requirement <-> assertion / test / interface
    ASSERTS = "asserts"  # assertion -> requirement
    TESTS = "tests"  # test -> requirement
    # coverage
    COVERS = "covers"  # test -> coverage_bin
    COVERAGE_OF = "coverage_of"  # coverage_bin -> module/interface
    # structure
    IN_MODULE = "in_module"  # signal/assertion -> module
    EXPOSES = "exposes"  # module -> interface
    ON_INTERFACE = "on_interface"  # signal -> interface
    # reset domains
    DEPENDS_ON_RESET = "depends_on_reset"  # assertion/signal -> reset_domain
    RESET_OF = "reset_of"  # reset_domain -> module
    # runs / failures / triage
    PRODUCED = "produced"  # regression -> failure
    FAILURE_OF = "failure_of"  # failure -> assertion/test
    AFFECTS_INTERFACE = "affects_interface"  # failure -> interface
    WAIVES = "waives"  # waiver -> failure
    FILED_AS = "filed_as"  # failure -> bug
    # evidence
    SUPPORTED_BY = "supported_by"  # evidence_claim -> benchmark


class SourceProvenance(_Strict):
    """Where a node/edge came from.

    ``artifact`` is the importer name (e.g. ``rtl_intent_manifest``).
    ``source_file`` is the path of the imported JSON. ``locator`` is a
    best-effort human-readable pointer (line number, key path, bin name)
    into that source. ``input_hash`` is the sha256 of the source file so a
    run can be reproduced and audited.
    """

    artifact: str
    source_file: str | None = None
    locator: str | None = None
    input_hash: str | None = None


class Node(_Strict):
    """A typed graph node with a stable ID and provenance."""

    id: str
    type: NodeType
    name: str
    attrs: dict[str, str] = Field(default_factory=dict)
    provenance: SourceProvenance


class Edge(_Strict):
    """A typed directed edge between two node IDs.

    The edge ID is deterministic: ``sha1(type|src|dst)`` (see ``ids.edge_id``)
    so re-importing the same artifact is idempotent.
    """

    id: str
    type: EdgeType
    src: str
    dst: str
    attrs: dict[str, str] = Field(default_factory=dict)
    provenance: SourceProvenance


class GraphExport(_Strict):
    """The full JSON export contract for the graph."""

    schema_version: str = GRAPH_SCHEMA_VERSION
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


class QueryResultRow(_Strict):
    """One row of a query result (stable, JSON-serializable)."""

    fields: dict[str, str] = Field(default_factory=dict)


class QueryResult(_Strict):
    """Structured result of a graph query."""

    query: str
    description: str
    columns: list[str]
    rows: list[QueryResultRow] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.rows)
