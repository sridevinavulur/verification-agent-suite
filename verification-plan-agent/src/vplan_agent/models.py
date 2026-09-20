"""Typed data contracts (Pydantic v2) for the Verification Plan Agent.

The models fall into three groups:

1. **Inputs** - the structured spec, interface glossary and existing testplan
   items the agent consumes (:class:`SpecDocument`, :class:`InterfaceGlossary`,
   :class:`ExistingTestplan`). The RTL Intent Manifest is consumed via the
   canonical external schema and only a small, defensively-typed view of it is
   modeled here (:class:`ManifestView`).

2. **Plan content** - what the agent produces: features, plan items, scenarios,
   assertion candidates, coverage targets, ambiguities and the traceability
   matrix.

3. **Approval workflow** - every generated item carries an
   :class:`ApprovalState`. Nothing is ``APPROVED`` unless a human decision file
   says so; the agent only ever *proposes*.

All models validate at construction time (``extra="forbid"`` where practical)
so malformed inputs fail loudly rather than silently.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class Category(StrEnum):
    """Verification concern categories (spec 6.2)."""

    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    RESET = "reset"
    ERROR_HANDLING = "error_handling"
    SECURITY = "security"
    LOW_POWER = "low_power"
    CDC_RDC = "cdc_rdc"
    INTEGRATION = "integration"


class Technique(StrEnum):
    """Proposed verification techniques (spec 6.2)."""

    DIRECTED_SIM = "directed_sim"
    CONSTRAINED_RANDOM = "constrained_random"
    SVA = "sva"
    FORMAL = "formal"
    COVER = "cover"
    EMULATION = "emulation"
    POST_SILICON = "post_silicon"


class Priority(StrEnum):
    P0 = "P0"  # must verify, highest risk
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"  # nice to have


class ApprovalState(StrEnum):
    """Human-approval workflow states.

    The agent never emits ``APPROVED``; only a human decision (applied via the
    ``approve`` command / a decisions file) promotes an item.
    """

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class AmbiguityKind(StrEnum):
    MISSING_REQUIREMENT = "missing_requirement"
    UNVERIFIABLE_REQUIREMENT = "unverifiable_requirement"
    ASSUMPTION = "assumption"
    UNDEFINED_INTERFACE_SIGNAL = "undefined_interface_signal"
    UNMAPPED_MANIFEST_RESET = "unmapped_manifest_reset"
    UNMAPPED_MANIFEST_CLOCK = "unmapped_manifest_clock"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
class Requirement(_Strict):
    """A single structured requirement extracted from the spec."""

    id: str = Field(..., description="Stable requirement id, e.g. REQ-FIFO-01.")
    text: str
    tags: list[str] = Field(default_factory=list)


class SpecDocument(_Strict):
    """A structured architecture specification (public/toy only)."""

    design_name: str
    version: str = "0.0.0"
    requirements: list[Requirement] = Field(default_factory=list)


class InterfaceSignal(_Strict):
    name: str
    direction: str = Field(..., description="input | output | inout")
    width: int = 1
    description: str = ""
    role: str = Field(
        "",
        description="Optional semantic role hint, e.g. clock/reset/handshake/data.",
    )


class InterfaceGlossary(_Strict):
    """Interface description / signal glossary."""

    design_name: str
    signals: list[InterfaceSignal] = Field(default_factory=list)


class ExistingTestplanItem(_Strict):
    """A pre-existing, already-agreed testplan item (optional input)."""

    id: str
    description: str
    covers_requirements: list[str] = Field(default_factory=list)
    approved: bool = True


class ExistingTestplan(_Strict):
    items: list[ExistingTestplanItem] = Field(default_factory=list)


# --- A small, defensive view of the external RTL Intent Manifest --- #
class ManifestPortView(_Strict):
    model_config = ConfigDict(extra="ignore")
    name: str
    direction: str = "input"


class ManifestModuleView(_Strict):
    model_config = ConfigDict(extra="ignore")
    name: str
    ports: list[ManifestPortView] = Field(default_factory=list)
    reset_candidate_signals: list[str] = Field(default_factory=list)
    clock_candidate_signals: list[str] = Field(default_factory=list)
    register_count: int = 0
    has_memory: bool = False


class ManifestView(_Strict):
    """Normalized, minimal projection of an RTL Intent Manifest.

    Built by :func:`vplan_agent.ingest.load_manifest_view` from the canonical
    ``manifest.schema.json`` structure. Kept separate so the plan engine never
    depends on the full external schema.
    """

    top: str | None = None
    modules: list[ManifestModuleView] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Plan content (all agent-produced items carry an ApprovalState)
# --------------------------------------------------------------------------- #
class Feature(_Strict):
    """A verifiable feature decomposed from one or more requirements."""

    id: str
    name: str
    category: Category
    description: str
    source_requirements: list[str] = Field(default_factory=list)
    approval: ApprovalState = ApprovalState.PROPOSED


class TestScenario(_Strict):
    id: str
    feature_id: str
    technique: Technique
    description: str
    approval: ApprovalState = ApprovalState.PROPOSED


class AssertionCandidate(_Strict):
    """A proposed assertion (SVA-ish sketch).

    NON-CLAIM: this is a *sketch* proposed by deterministic templates + a mock
    LLM. It is not guaranteed to compile, be complete, or be correct.
    """

    id: str
    feature_id: str
    sva_sketch: str
    rationale: str
    approval: ApprovalState = ApprovalState.PROPOSED


class CoverageTarget(_Strict):
    id: str
    feature_id: str
    metric: str = Field(..., description="e.g. cover_group, functional_bin, toggle.")
    description: str
    approval: ApprovalState = ApprovalState.PROPOSED


class PlanItem(_Strict):
    """A risk-ranked verification-plan item tying a feature to techniques."""

    id: str
    feature_id: str
    category: Category
    priority: Priority
    risk_score: int = Field(..., ge=0, le=100)
    risk_rationale: list[str] = Field(default_factory=list)
    techniques: list[Technique] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    assertion_ids: list[str] = Field(default_factory=list)
    coverage_ids: list[str] = Field(default_factory=list)
    approval: ApprovalState = ApprovalState.PROPOSED


class Ambiguity(_Strict):
    id: str
    kind: AmbiguityKind
    detail: str
    ref: str = Field("", description="Related requirement/signal/module id.")


class TraceRow(_Strict):
    """One requirement -> tests -> coverage traceability row."""

    requirement_id: str
    feature_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    assertion_ids: list[str] = Field(default_factory=list)
    coverage_ids: list[str] = Field(default_factory=list)
    existing_testplan_ids: list[str] = Field(default_factory=list)
    covered: bool = False


class ApprovalDecision(_Strict):
    """A human decision applied to a generated item id."""

    item_id: str
    decision: ApprovalState
    approver: str = ""
    note: str = ""


class Provenance(_Strict):
    tool: str = "verification-plan-agent"
    tool_version: str = SCHEMA_VERSION
    schema_version: str = SCHEMA_VERSION
    git_sha: str = "UNKNOWN"
    command: str = ""
    llm_adapter: str = "mock"
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)


class VerificationPlan(_Strict):
    """The complete verification-plan draft (the agent's top-level output)."""

    schema_version: str = SCHEMA_VERSION
    design_name: str
    provenance: Provenance
    features: list[Feature] = Field(default_factory=list)
    plan_items: list[PlanItem] = Field(default_factory=list)
    scenarios: list[TestScenario] = Field(default_factory=list)
    assertions: list[AssertionCandidate] = Field(default_factory=list)
    coverage_targets: list[CoverageTarget] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    traceability: list[TraceRow] = Field(default_factory=list)

    def counts_by_approval(self) -> dict[str, int]:
        """Summarize proposed vs approved vs rejected across all item groups."""
        counts = {s.value: 0 for s in ApprovalState}
        groups = (
            self.features,
            self.plan_items,
            self.scenarios,
            self.assertions,
            self.coverage_targets,
        )
        for group in groups:
            for item in group:
                counts[item.approval.value] += 1
        return counts
