"""Typed data contracts for the Multi-Agent Verification Supervisor.

All contracts are Pydantic v2 models that *validate*, not merely annotate. The
supervisor is a workflow/policy coordinator: it never independently declares an
assertion valid, a proof complete, or signoff achieved. That authority boundary
is encoded here in the enums and in the fields the supervisor is allowed to set.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base model: reject unknown fields, validate on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Workflow states and result vocabulary
# ---------------------------------------------------------------------------


class WorkflowState(StrEnum):
    """States of the supervisor state machine.

    The order here also documents the nominal happy-path progression, but the
    only authoritative source of allowed transitions is ``ALLOWED_TRANSITIONS``
    in ``state_machine.py``.
    """

    CREATED = "CREATED"
    RTL_INGESTION = "RTL_INGESTION"
    SVA_PROPOSAL = "SVA_PROPOSAL"
    PROPERTY_REVIEW = "PROPERTY_REVIEW"
    PARTITION_ANALYSIS = "PARTITION_ANALYSIS"
    PLAN_EXPERIMENT = "PLAN_EXPERIMENT"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    EXECUTION = "EXECUTION"
    EVIDENCE_ASSEMBLY = "EVIDENCE_ASSEMBLY"
    DONE = "DONE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


TERMINAL_STATES: frozenset[WorkflowState] = frozenset(
    {WorkflowState.DONE, WorkflowState.REJECTED, WorkflowState.FAILED}
)


class FormalResult(StrEnum):
    """Formal result vocabulary. Never map TIMEOUT/ERROR/UNKNOWN to PASS."""

    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"
    # Front-end syntax acceptance only; does NOT establish semantics.
    COMPILED = "COMPILED"


# A PASS from the backend is authoritative for that exact run; the supervisor
# still never elevates it to "signoff". These are the only results the
# orchestrator worker is permitted to emit.
EXECUTION_RESULTS: frozenset[FormalResult] = frozenset(
    {FormalResult.PASS, FormalResult.FAIL, FormalResult.TIMEOUT,
     FormalResult.ERROR, FormalResult.UNKNOWN}
)


class ReviewState(StrEnum):
    """Review state of a candidate property."""

    UNREVIEWED = "UNREVIEWED"
    REVIEWED_OK = "REVIEWED_OK"
    REVIEWED_REJECTED = "REVIEWED_REJECTED"


# ---------------------------------------------------------------------------
# Task input
# ---------------------------------------------------------------------------


class VerificationTask(StrictModel):
    """The verification task handed to the supervisor."""

    task_id: str = Field(min_length=1)
    repo_revision: str = Field(min_length=1, description="Git SHA/tag placeholder of the RTL repo.")
    requirement_text: str = Field(min_length=1, description="Natural-language requirement.")
    rtl_files: list[str] = Field(default_factory=list)
    # If any of these are affected, human approval is mandatory before EXECUTION.
    affects_assumptions: bool = False
    affects_abstraction: bool = False
    affects_budget: bool = False
    affects_proof_scope: bool = False

    def requires_human_approval(self) -> bool:
        return any(
            (
                self.affects_assumptions,
                self.affects_abstraction,
                self.affects_budget,
                self.affects_proof_scope,
            )
        )


# ---------------------------------------------------------------------------
# Agent messages: RTL Intent Ingestor
# ---------------------------------------------------------------------------


class RtlIngestRequest(StrictModel):
    task_id: str
    repo_revision: str
    rtl_files: list[str] = Field(default_factory=list)


class SignalInfo(StrictModel):
    name: str = Field(min_length=1)
    direction: Literal["input", "output", "inout", "internal"]
    width: int = Field(ge=1, default=1)
    source_loc: str = Field(description="file:line evidence for the symbol.")


class RtlManifest(StrictModel):
    """Deterministic extraction result from the RTL Intent Ingestor."""

    task_id: str
    repo_revision: str
    design_top: str = Field(min_length=1)
    signals: list[SignalInfo] = Field(default_factory=list)
    clock_candidates: list[str] = Field(default_factory=list)
    reset_candidates: list[str] = Field(default_factory=list)
    reset_polarity: dict[str, Literal["active_high", "active_low", "unknown"]] = Field(
        default_factory=dict
    )
    unresolved_constructs: list[str] = Field(default_factory=list)
    manifest_hash: str = Field(min_length=1)

    def symbol_names(self) -> set[str]:
        return {s.name for s in self.signals}


# ---------------------------------------------------------------------------
# Agent messages: SVA Intent Agent
# ---------------------------------------------------------------------------


class SvaProposalRequest(StrictModel):
    task_id: str
    requirement_text: str
    manifest_hash: str


class SymbolMapping(StrictModel):
    """Grounding of a requirement term to an RTL symbol."""

    term: str = Field(min_length=1)
    # None means the term could not be grounded -> ungrounded property.
    symbol: str | None = None
    source_loc: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class CandidateProperty(StrictModel):
    """A candidate SVA property. It is a *candidate* until reviewed AND validated.

    The SVA Intent Agent proposes; deterministic validators + human review gate
    it. No field here means "proven" or "signoff".
    """

    property_id: str = Field(min_length=1)
    task_id: str
    requirement_text: str
    sva_text: str = Field(min_length=1)
    property_kind: Literal["assert", "assume", "cover"] = "assert"
    clock_signal: str | None = None
    reset_signal: str | None = None
    reset_polarity: Literal["active_high", "active_low", "unknown"] | None = None
    groundings: list[SymbolMapping] = Field(default_factory=list)
    # Set by the SVA agent's own front-end; supervisor re-checks deterministically.
    syntax_ok: bool = False
    review_state: ReviewState = ReviewState.UNREVIEWED

    def ungrounded_terms(self) -> list[str]:
        return [g.term for g in self.groundings if g.symbol is None]


# ---------------------------------------------------------------------------
# Agent messages: Formal Partition Agent
# ---------------------------------------------------------------------------


class PartitionRequest(StrictModel):
    task_id: str
    property_id: str
    manifest_hash: str


class PartitionReport(StrictModel):
    """COI / partition analysis. Every partition is labeled heuristic."""

    task_id: str
    property_id: str
    coi_signals: list[str] = Field(default_factory=list)
    excluded_signals: list[str] = Field(default_factory=list)
    partitions: list[str] = Field(default_factory=list)
    cut_signals: list[str] = Field(default_factory=list)
    # Unproven obligations required at cuts. Non-empty => affects assumptions.
    cut_assumptions: list[str] = Field(default_factory=list)
    soundness_risk_flags: list[str] = Field(default_factory=list)
    heuristic: bool = True


# ---------------------------------------------------------------------------
# Experiment plan + Formal Run Orchestrator
# ---------------------------------------------------------------------------


class ExperimentConfig(StrictModel):
    """A single config from the finite, versioned approved catalog."""

    config_id: str = Field(min_length=1)
    engine: str = Field(min_length=1)
    bmc_depth: int = Field(ge=1)
    timeout_s: int = Field(ge=1)
    preprocessing: Literal["none", "basic", "aggressive"] = "basic"


class ExperimentPlan(StrictModel):
    task_id: str
    property_id: str
    config: ExperimentConfig
    # True when the plan touches assumptions/abstraction/budget/proof scope.
    needs_human_approval: bool = False


class ExecutionRequest(StrictModel):
    task_id: str
    property_id: str
    config: ExperimentConfig
    # The worker MUST refuse to run if this is False.
    approved: bool = False


class RunRecord(StrictModel):
    """Provenance record for one formal run (mirrors the orchestrator ledger)."""

    task_id: str
    property_id: str
    config_id: str
    repo_revision: str
    manifest_hash: str
    tool_name: str = "mock-formal"
    tool_version: str = "0.0.0-mock"
    command: str = ""
    seed: int = 0
    start_time: datetime = Field(default_factory=_utcnow)
    end_time: datetime = Field(default_factory=_utcnow)
    cpu_time_s: float = 0.0
    wall_time_s: float = 0.0
    peak_mem_mb: float = 0.0
    return_code: int = 0
    result: FormalResult = FormalResult.UNKNOWN
    artifact_paths: list[str] = Field(default_factory=list)
    rationale: str = ""

    @field_validator("result")
    @classmethod
    def _result_must_be_executable(cls, v: FormalResult) -> FormalResult:
        if v not in EXECUTION_RESULTS:
            raise ValueError(
                f"RunRecord.result {v!r} is not an execution result; "
                "the orchestrator may not emit COMPILED as a run outcome."
            )
        return v


# ---------------------------------------------------------------------------
# Human approval
# ---------------------------------------------------------------------------


class ApprovalDecision(StrictModel):
    task_id: str
    approver: str = Field(min_length=1)
    approved: bool
    reason: str = ""
    decided_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditEvent(StrictModel):
    """One append-only JSONL audit record."""

    seq: int = Field(ge=0)
    task_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    from_state: WorkflowState
    to_state: WorkflowState
    event: str = Field(min_length=1)
    detail: str = ""
    actor: Literal["supervisor", "rtl_ingestor", "sva_agent", "partition_agent",
                   "orchestrator", "human"] = "supervisor"


# ---------------------------------------------------------------------------
# Evidence packet (final output)
# ---------------------------------------------------------------------------


class EvidencePacket(StrictModel):
    """Complete evidence packet returned at the end of a workflow.

    Note the explicit non-claims: the packet reports the backend's classified
    result and never asserts proof completeness or signoff.
    """

    task_id: str
    final_state: WorkflowState
    requirement_text: str
    repo_revision: str
    rtl_manifest: RtlManifest | None = None
    candidate_property: CandidateProperty | None = None
    validation_findings: list[str] = Field(default_factory=list)
    partition_report: PartitionReport | None = None
    experiment_plan: ExperimentPlan | None = None
    approval: ApprovalDecision | None = None
    run_record: RunRecord | None = None
    result_classification: FormalResult | None = None
    limitations: list[str] = Field(default_factory=list)
    next_recommended_action: str = ""
    audit_log_path: str = ""
    non_claims: list[str] = Field(
        default_factory=lambda: [
            "The supervisor did NOT declare the assertion valid.",
            "The supervisor did NOT declare the proof complete.",
            "The supervisor did NOT declare verification signoff achieved.",
            "A PASS result is authoritative only for the exact recorded design, "
            "assumptions, property, tool version, and configuration.",
        ]
    )
