"""Typed data contracts for the Reset Intent Agent.

All models are Pydantic v2 and validate (not merely annotate). JSON emitted by
the tool round-trips through these models. Enums subclass ``str`` for stable
JSON serialization.

Key vocabulary rules encoded here:

* ``ResetPolarity.UNKNOWN`` is a first-class value. Polarity is *never* inferred
  silently -- when evidence is contradictory or absent the value stays
  ``unknown`` and an :class:`Ambiguity` is recorded.
* Every :class:`ResetDomainEdge` and domain membership is marked
  ``heuristic=True`` -- structural detection is not verified intent.
* Candidate SVA is always ``status = "candidate"`` (never "verified").
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class ResetPolarity(str, Enum):
    """Reset polarity. ``UNKNOWN`` is used whenever evidence is ambiguous."""

    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class ResetSync(str, Enum):
    """Synchronous vs asynchronous reset usage (structural)."""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SvaStatus(str, Enum):
    """SVA lifecycle. This tool only ever emits ``CANDIDATE``."""

    CANDIDATE = "candidate"


class PropertyKind(str, Enum):
    ASSERT = "assert"
    ASSUME = "assume"
    COVER = "cover"


# --------------------------------------------------------------------------- #
# Evidence / provenance
# --------------------------------------------------------------------------- #
class SourceLocation(_Base):
    """1-based location of an extracted item.

    When the input is a manifest without column data, ``col``/``end_*`` may be
    absent and only ``file``/``line`` are populated.
    """

    file: str
    line: int = Field(ge=1)
    col: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    end_col: int | None = Field(default=None, ge=1)


class Provenance(_Base):
    tool: str = "reset-intent-agent"
    tool_version: str
    schema_version: str = "0.1.0"
    git_sha: str = "UNKNOWN"
    command: str = ""
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Reset topology
# --------------------------------------------------------------------------- #
class PolarityEvidence(_Base):
    """A single piece of evidence for a polarity decision.

    ``votes_polarity`` is what this evidence, on its own, would suggest. The
    aggregate decision is made in :mod:`analyzer` and recorded on
    :class:`ResetCandidate`. Keeping per-evidence votes visible means a reviewer
    can see *why* a polarity was chosen and where the votes conflict.
    """

    kind: str  # e.g. "name_suffix", "edge", "guard_expr", "manifest_type"
    detail: str
    votes_polarity: ResetPolarity = ResetPolarity.UNKNOWN
    location: SourceLocation | None = None


class ResetCandidate(_Base):
    """A structurally detected reset signal.

    STRUCTURAL: presence in reset position of an always block or a
    manifest reset entry. Not a proof that the signal is a reset.
    """

    signal: str
    polarity: ResetPolarity = ResetPolarity.UNKNOWN
    sync: ResetSync = ResetSync.UNKNOWN
    # heuristic confidence in [0,1] that this signal is a reset at all
    confidence: float = Field(ge=0.0, le=1.0)
    polarity_evidence: list[PolarityEvidence] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    location: SourceLocation | None = None
    # registers/nets this reset drives to a reset value (structural fanout)
    fanout_registers: list[str] = Field(default_factory=list)
    is_port: bool = False


class ResetTarget(_Base):
    """A register reset by a reset candidate, with its reset value if extracted.

    The field is named ``register_name`` (not ``register``) to avoid shadowing a
    Pydantic ``BaseModel`` internal.
    """

    register_name: str
    reset_signal: str
    reset_value: str | None = None
    sync: ResetSync = ResetSync.UNKNOWN
    location: SourceLocation | None = None


# --------------------------------------------------------------------------- #
# Reset domains (HEURISTIC)
# --------------------------------------------------------------------------- #
class ResetDomain(_Base):
    """A group of registers reset by the same reset signal.

    HEURISTIC: grouping by shared reset signal name. This is structural and is
    NOT a verified reset-domain definition.
    """

    domain_id: str
    reset_signal: str
    polarity: ResetPolarity = ResetPolarity.UNKNOWN
    sync: ResetSync = ResetSync.UNKNOWN
    members: list[str] = Field(default_factory=list)
    heuristic: bool = True


class ResetDomainCrossing(_Base):
    """A possible reset-domain crossing.

    HEURISTIC: a register in domain A feeds (via combinational logic or a
    read in a procedure) a register in domain B. Flagged for review, not proven
    to be a real RDC hazard.
    """

    from_domain: str
    to_domain: str
    from_register: str
    to_register: str
    severity: Severity = Severity.MEDIUM
    rationale: list[str] = Field(default_factory=list)
    heuristic: bool = True
    location: SourceLocation | None = None


class ResetGraphNode(_Base):
    node_id: str
    kind: str  # "reset" | "register" | "domain"
    label: str


class ResetGraphEdge(_Base):
    src: str
    dst: str
    kind: str  # "resets" | "member_of" | "rdc"
    heuristic: bool = False


class ResetGraph(_Base):
    nodes: list[ResetGraphNode] = Field(default_factory=list)
    edges: list[ResetGraphEdge] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Risks / recommendations / candidate SVA
# --------------------------------------------------------------------------- #
class Ambiguity(_Base):
    """A place where the tool refused to infer silently."""

    ambiguity_id: str
    signal: str | None = None
    detail: str
    severity: Severity = Severity.MEDIUM
    location: SourceLocation | None = None


class Risk(_Base):
    risk_id: str
    category: str  # e.g. "polarity", "mixed_sync", "no_reset", "rdc", "quiescence"
    detail: str
    severity: Severity = Severity.MEDIUM
    heuristic: bool = True
    location: SourceLocation | None = None


class TestRecommendation(_Base):
    rec_id: str
    kind: str  # "cover" | "directed_test" | "assertion"
    detail: str
    target_signal: str | None = None


class CandidateSVA(_Base):
    """A candidate reset-behavior property.

    Emitted in sva-intent-engine style: ``status`` is always ``candidate``. This
    tool does *not* validate semantics, run formal, or claim correctness.
    """

    property_id: str
    name: str
    kind: PropertyKind = PropertyKind.ASSERT
    sva_text: str
    status: SvaStatus = SvaStatus.CANDIDATE
    clock: str | None = None
    reset_signal: str | None = None
    reset_polarity: ResetPolarity = ResetPolarity.UNKNOWN
    rationale: str = ""
    referenced_signals: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Top-level manifest
# --------------------------------------------------------------------------- #
class ResetIntentManifest(_Base):
    """Top-level reset intent manifest."""

    schema_version: str = "0.1.0"
    design_top: str | None = None
    provenance: Provenance
    reset_candidates: list[ResetCandidate] = Field(default_factory=list)
    reset_targets: list[ResetTarget] = Field(default_factory=list)
    reset_domains: list[ResetDomain] = Field(default_factory=list)
    domain_crossings: list[ResetDomainCrossing] = Field(default_factory=list)
    reset_graph: ResetGraph = Field(default_factory=ResetGraph)
    candidate_sva: list[CandidateSVA] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    recommendations: list[TestRecommendation] = Field(default_factory=list)
