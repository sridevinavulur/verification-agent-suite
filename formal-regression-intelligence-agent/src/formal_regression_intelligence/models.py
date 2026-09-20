"""Typed data contracts for the Formal Regression Intelligence Agent.

Every payload crossing a module or CLI boundary is a Pydantic v2 model so it
*validates*, not merely annotates.

INTEROP: :class:`RunRecord` mirrors the run-record contract emitted by the
``formal-run-orchestrator`` project (see its ``schemas/run_record.schema.json``).
Field names are reused verbatim so a ledger produced by that orchestrator can be
ingested here without transformation. We accept a *superset* posture: unknown
extra fields on ingested records are ignored (``extra="ignore"``) rather than
rejected, because a downstream analytics tool must not brittle-fail on a newer
producer that adds fields. The analysis outputs defined below are this project's
own contracts and use ``extra="forbid"``.

Nothing in this module claims a *root cause*. Every cluster/alert is an
evidence-backed statistical observation and is labelled HEURISTIC.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "0.1.0"


# --------------------------------------------------------------------------- #
# Sanctioned vocabularies (must match the orchestrator's RunStatus exactly)
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    """Formal result vocabulary. See BUILD_STANDARD.md.

    Only ``PASS`` denotes a proven/passing outcome. TIMEOUT / ERROR /
    INCONCLUSIVE are *never* success and are handled explicitly everywhere.
    A TIMEOUT is never treated as a PASS anywhere in this codebase.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"

    @property
    def is_success(self) -> bool:
        return self is RunStatus.PASS

    @property
    def is_conclusive(self) -> bool:
        return self in (RunStatus.PASS, RunStatus.FAIL)


class Severity(str, Enum):
    """Triage severity for a finding. Ordered low -> high."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
}


def severity_rank(sev: Severity) -> int:
    return _SEVERITY_RANK[sev]


class FindingKind(str, Enum):
    """The category of a regression-intelligence finding."""

    FAILURE_CLUSTER = "failure_cluster"
    TIMEOUT_CLUSTER = "timeout_cluster"
    DUPLICATE_JOBS = "duplicate_jobs"
    RUNTIME_REGRESSION = "runtime_regression"
    MEMORY_REGRESSION = "memory_regression"
    CONFIG_SENSITIVITY = "config_sensitivity"
    REPRODUCIBILITY_WARNING = "reproducibility_warning"


# --------------------------------------------------------------------------- #
# Ingested run record (interop contract with formal-run-orchestrator)
# --------------------------------------------------------------------------- #
class RunRecord(BaseModel):
    """One formal-run provenance row, as produced by ``formal-run-orchestrator``.

    Only the fields this agent actually reads are declared; extra fields on the
    ingested JSON are ignored so newer producers do not break ingestion. Field
    names and semantics are copied from the orchestrator's ``RunRecord``.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = SCHEMA_VERSION
    run_id: str
    plan_id: str | None = None
    benchmark_id: str

    # Provenance: sources
    design_sha: str
    property_sha: str
    input_hash: str

    # Provenance: tool + config
    tool_name: str
    tool_version: str
    config_id: str
    catalog_version: str
    seed: int

    # Timing / resources
    start_time: datetime | None = None
    end_time: datetime | None = None
    cpu_time_s: float = Field(..., ge=0.0)
    wall_time_s: float = Field(..., ge=0.0)
    peak_memory_mb: float = Field(..., ge=0.0)
    return_code: int

    # Outcome
    status: RunStatus

    @field_validator("status")
    @classmethod
    def _pass_needs_rc0(cls, v: RunStatus, info) -> RunStatus:  # noqa: ANN001
        # A PASS with a non-zero return code is a producer bug; reject it rather
        # than silently trusting a "PASS" that the tool did not really conclude.
        if v is RunStatus.PASS and info.data.get("return_code", 0) != 0:
            raise ValueError("PASS status requires return_code == 0")
        return v

    @property
    def job_key(self) -> str:
        """Logical job identity: the (design, property, config) triple.

        Repeated executions of the *same* logical job (across seeds / commits)
        share this key. Flakiness and runtime/memory baselines are computed per
        ``job_key``.
        """
        return f"{self.benchmark_id}::{self.config_id}"

    @property
    def signature_fields(self) -> tuple[str, str, str, str]:
        """Content identity used for duplicate detection.

        Two jobs are *duplicates* when they run the identical design, property,
        and configuration -- i.e. identical inputs -- regardless of seed. We key
        on the provenance SHAs (content) rather than names.
        """
        return (self.design_sha, self.property_sha, self.config_id, self.catalog_version)


class RunLedger(BaseModel):
    """A collection of run records. Accepts a JSON array or a JSONL file."""

    model_config = ConfigDict(extra="forbid")

    records: list[RunRecord]

    @field_validator("records")
    @classmethod
    def _non_empty(cls, v: list[RunRecord]) -> list[RunRecord]:
        if not v:
            raise ValueError("run ledger must contain at least one record")
        return v


# --------------------------------------------------------------------------- #
# Statistics / evidence primitives
# --------------------------------------------------------------------------- #
class BaselineStats(BaseModel):
    """Robust summary statistics for one metric over a job's baseline history."""

    model_config = ConfigDict(extra="forbid")

    n: int = Field(..., ge=0)
    mean: float
    stdev: float = Field(..., ge=0.0)
    median: float
    mad: float = Field(..., ge=0.0, description="Median absolute deviation (robust scale).")
    minimum: float
    maximum: float


class RegressionEvidence(BaseModel):
    """Evidence for one runtime/memory regression alert against a baseline."""

    model_config = ConfigDict(extra="forbid")

    job_key: str
    metric: str = Field(..., description="'wall_time_s', 'cpu_time_s', or 'peak_memory_mb'.")
    latest_run_id: str
    latest_value: float
    baseline: BaselineStats
    z_score: float = Field(..., description="Classic z vs baseline mean/stdev (inf-guarded).")
    robust_z: float = Field(..., description="Robust z: 0.6745*(x-median)/MAD.")
    ratio_to_median: float = Field(..., description="latest / baseline median.")


class ReproEvidence(BaseModel):
    """Evidence for a reproducibility / flakiness warning on one logical job."""

    model_config = ConfigDict(extra="forbid")

    job_key: str
    n_runs: int = Field(..., ge=2)
    distinct_statuses: list[RunStatus]
    status_counts: dict[str, int]
    pass_count: int = Field(..., ge=0)
    fail_count: int = Field(..., ge=0)
    nonconclusive_count: int = Field(..., ge=0)
    flip_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of consecutive runs whose status changed."
    )
    coefficient_of_variation: float | None = Field(
        None, ge=0.0, description="stdev/mean of wall_time_s across runs, if computable."
    )


class ConfigSensitivityEvidence(BaseModel):
    """How one benchmark's outcome/runtime varies across configurations."""

    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    n_configs: int = Field(..., ge=2)
    distinct_terminal_statuses: list[RunStatus]
    best_config_id: str | None
    worst_config_id: str | None
    best_median_wall_s: float | None
    worst_median_wall_s: float | None
    wall_spread_ratio: float | None = Field(
        None, ge=1.0, description="worst_median / best_median wall time across configs."
    )
    solved_by_some_config: bool
    solved_by_all_configs: bool


# --------------------------------------------------------------------------- #
# Findings (the deterministic outputs)
# --------------------------------------------------------------------------- #
class Finding(BaseModel):
    """One evidence-backed regression-intelligence observation.

    A Finding is HEURISTIC: it reports a statistical/structural pattern, never a
    proven root cause. ``evidence`` holds the machine-readable substantiation and
    ``member_run_ids`` lists the exact records the finding was computed from, so
    every claim is reproducible and auditable.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    kind: FindingKind
    severity: Severity
    title: str
    summary: str = Field(..., description="Deterministic, template-generated description.")
    heuristic: bool = True
    member_run_ids: list[str] = Field(default_factory=list)
    benchmark_ids: list[str] = Field(default_factory=list)
    config_ids: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict, description="Machine-readable substantiation.")
    priority_score: float = Field(0.0, description="Deterministic ranking score (higher first).")


class InvestigationItem(BaseModel):
    """One entry in the prioritized investigation queue."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., ge=1)
    finding_id: str
    kind: FindingKind
    severity: Severity
    priority_score: float
    title: str
    recommended_next_step: str


class RegressionReport(BaseModel):
    """The complete analysis output for one ledger."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    n_records: int
    n_jobs: int = Field(..., description="Distinct (benchmark, config) logical jobs.")
    n_benchmarks: int
    status_totals: dict[str, int]
    findings: list[Finding]
    investigation_queue: list[InvestigationItem]

    def findings_by_kind(self, kind: FindingKind) -> list[Finding]:
        return [f for f in self.findings if f.kind is kind]
