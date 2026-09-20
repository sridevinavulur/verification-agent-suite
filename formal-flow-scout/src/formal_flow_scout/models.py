"""Typed Pydantic v2 data contracts for FormalFlow-Scout.

Two families of models live here:

1. **Input contracts** - a minimal mirror of the RTL Intent Manifest produced by
   ``rtl-intent-ingestor`` (only the fields FormalFlow-Scout actually consumes),
   plus the property signal set.
2. **Output contracts** - the COI/partition analysis report. Every model uses
   ``extra="forbid"`` so the JSON is a strict, validated contract.

Soundness discipline (mandatory, per BUILD_STANDARD.md):
* Backward combinational + sequential COI over the *structural* dependency graph
  is a **sound over-approximation** of the true cone of influence for the
  constrained Verilog subset we support (see ARCHITECTURE.md for the argument and
  its stated assumptions).
* Everything derived from *partitioning* - candidate partitions, interface cuts,
  cut signals - is **HEURISTIC**. A cut is only a valid formal reduction if the
  emitted environment assumptions are discharged. We emit those assumptions as
  explicit ``UNPROVEN`` obligations and never claim the slice is proven.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input contracts (subset of the RTL Intent Manifest + property set)
# --------------------------------------------------------------------------- #


class SourceLocation(_Strict):
    file: str
    line: int = Field(ge=1)
    col: int = Field(ge=1, default=1)
    end_line: int = Field(ge=1, default=1)
    end_col: int = Field(ge=1, default=1)


class NodeKind(str, Enum):
    """Kind of a graph node.

    ``PORT_IN``/``PORT_OUT`` are module boundary signals; ``NET`` is a
    combinational wire; ``REG`` is a state element (target of ``<=`` under a
    clock edge); ``CLOCK``/``RESET`` are control signals; ``CONST`` is a
    literal source; ``BLACKBOX`` is an output of an undefined child instance.
    """

    PORT_IN = "port_in"
    PORT_OUT = "port_out"
    NET = "net"
    REG = "reg"
    CLOCK = "clock"
    RESET = "reset"
    CONST = "const"
    BLACKBOX = "blackbox"


class EdgeKind(str, Enum):
    """Directed dependency edge kinds.

    Edges point **from a signal to the signals that drive it** (fan-in / reverse
    dataflow), so backward-COI is a forward walk over this graph.

    * ``COMB`` - combinational dependency (``assign`` RHS, comb-block RHS).
    * ``SEQ``  - sequential dependency: a register depends on its next-state
      expression across a clock edge.
    * ``CLOCK`` - a register depends on its clock signal.
    * ``RESET`` - a register depends on its reset signal.
    * ``HIER``  - a signal crosses a module-instance boundary.
    """

    COMB = "comb"
    SEQ = "seq"
    CLOCK = "clock"
    RESET = "reset"
    HIER = "hier"


class GraphNode(_Strict):
    node_id: int = Field(ge=0)
    name: str  # hierarchical name, e.g. "top.u_fifo.rd_ptr"
    kind: NodeKind
    module: str
    clock_domain: str | None = None
    reset_domain: str | None = None
    location: SourceLocation | None = None


class GraphEdge(_Strict):
    """Edge ``src -> dst`` meaning: signal ``src`` depends on signal ``dst``."""

    src: int = Field(ge=0)
    dst: int = Field(ge=0)
    kind: EdgeKind


class DependencyGraph(_Strict):
    """Deterministic, ID-stable dependency graph.

    Nodes are ordered by ``node_id``; ``node_id`` is assigned in first-seen
    order during graph construction, which is itself deterministic because the
    manifest / parser produce signals in stable source order.
    """

    schema_version: str = SCHEMA_VERSION
    top: str | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class PropertySignal(_Strict):
    """One signal referenced by a property (the COI seed set)."""

    name: str
    role: str = "asserted"  # asserted | assumed | cover | referenced


class PropertySpec(_Strict):
    """A property and the signal set that seeds the cone-of-influence walk."""

    name: str
    signals: list[PropertySignal] = Field(default_factory=list)
    description: str | None = None


class PropertySet(_Strict):
    schema_version: str = SCHEMA_VERSION
    properties: list[PropertySpec] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Output contracts (the analysis report)
# --------------------------------------------------------------------------- #


class Soundness(str, Enum):
    """Soundness label attached to every result element."""

    SOUND = "SOUND"  # over-approximation that provably preserves the property
    HEURISTIC = "HEURISTIC"  # ranking / grouping only; no preservation argument
    UNPROVEN = "UNPROVEN"  # requires a discharged obligation to be valid


class ExclusionReason(str, Enum):
    NOT_IN_COI = "not_in_coi"  # unreachable from any property seed
    OUTSIDE_PARTITION = "outside_partition"  # in COI but cut away by a partition


class ExcludedLogic(_Strict):
    node_id: int
    name: str
    kind: NodeKind
    reason: ExclusionReason
    detail: str


class CutSignal(_Strict):
    """A signal on a partition boundary that must be constrained at the cut."""

    node_id: int
    name: str
    kind: NodeKind
    direction: str  # "into_partition" (input driven from outside) or "out_of_partition"


class EnvironmentAssumption(_Strict):
    """An UNPROVEN obligation that must hold for a cut to be a valid reduction.

    Emitting this does NOT make the slice sound. It records precisely what a
    human/formal tool must discharge. ``soundness`` is always ``UNPROVEN``.
    """

    cut_signal: str
    node_id: int
    obligation: str
    soundness: Soundness = Soundness.UNPROVEN
    rationale: str


class SoundnessRisk(_Strict):
    """A flagged risk that could make a partition an *unsound* reduction."""

    severity: str  # "high" | "medium" | "low"
    kind: str
    detail: str
    node_ids: list[int] = Field(default_factory=list)


class CandidatePartition(_Strict):
    """A HEURISTIC proof-partition proposal.

    ``soundness`` is ``HEURISTIC`` unless every assumption in
    ``environment_assumptions`` is discharged - which this tool cannot do.
    """

    partition_id: str
    strategy: str  # "hierarchy" | "scc" | "interface_cut"
    soundness: Soundness = Soundness.HEURISTIC
    included_nodes: list[int] = Field(default_factory=list)
    cut_signals: list[CutSignal] = Field(default_factory=list)
    environment_assumptions: list[EnvironmentAssumption] = Field(default_factory=list)
    soundness_risks: list[SoundnessRisk] = Field(default_factory=list)
    rationale: str = ""
    estimated_state_bits: int = 0


class SCCInfo(_Strict):
    scc_id: int
    node_ids: list[int]
    is_cyclic: bool  # size > 1, or a self-loop


class DomainInfo(_Strict):
    clock_domains: dict[str, list[int]] = Field(default_factory=dict)
    reset_domains: dict[str, list[int]] = Field(default_factory=dict)
    multi_clock: bool = False


class CoiStats(_Strict):
    total_nodes: int
    total_edges: int
    coi_nodes: int
    coi_registers: int
    coi_combinational: int
    excluded_nodes: int
    scc_count: int
    cyclic_scc_count: int
    largest_scc_size: int
    clock_domain_count: int
    reset_domain_count: int
    seed_signals: int
    unresolved_seed_signals: int


class Provenance(_Strict):
    tool: str = "formal-flow-scout"
    tool_version: str
    schema_version: str = SCHEMA_VERSION
    git_sha: str = "UNKNOWN"
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)
    command: str = ""
    graph_core: str = "python"  # "python" | "cpp"


class CoiReport(_Strict):
    """Top-level machine-readable COI / partition analysis report."""

    schema_version: str = SCHEMA_VERSION
    provenance: Provenance
    property_name: str
    top: str | None = None
    seed_node_ids: list[int] = Field(default_factory=list)
    unresolved_seed_signals: list[str] = Field(default_factory=list)
    coi_node_ids: list[int] = Field(default_factory=list)
    excluded_logic: list[ExcludedLogic] = Field(default_factory=list)
    sccs: list[SCCInfo] = Field(default_factory=list)
    domains: DomainInfo = Field(default_factory=DomainInfo)
    candidate_partitions: list[CandidatePartition] = Field(default_factory=list)
    soundness_risks: list[SoundnessRisk] = Field(default_factory=list)
    stats: CoiStats
    notes: list[str] = Field(default_factory=list)
