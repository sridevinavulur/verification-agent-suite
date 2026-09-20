"""Typed data contracts for the Formal Run Orchestrator.

All experiment/result payloads that cross a module or CLI boundary are Pydantic v2
models so they *validate* (not merely annotate). The result vocabulary is fixed by
``RunStatus`` and the classifier is the only sanctioned producer of it; a TIMEOUT,
ERROR, or INCONCLUSIVE result is never representable as a PASS.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "0.1.0"


# --------------------------------------------------------------------------- #
# Enumerations (the sanctioned vocabularies)
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    """Formal result vocabulary. See BUILD_STANDARD.md.

    Only ``PASS`` denotes a proven/passing outcome. TIMEOUT / ERROR /
    INCONCLUSIVE are *never* success and are handled explicitly everywhere.
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
        """PASS and FAIL are conclusive tool verdicts; the rest are not."""
        return self in (RunStatus.PASS, RunStatus.FAIL)


class EngineFamily(str, Enum):
    """Engine families in the approved catalog (open-source-flavored names)."""

    BMC = "bmc"
    KINDUCTION = "k_induction"
    PDR = "pdr"  # IC3/PDR-style
    INTERPOLATION = "interpolation"


class PreprocessingLevel(str, Enum):
    NONE = "none"
    LIGHT = "light"
    AGGRESSIVE = "aggressive"


class PartitionStrategy(str, Enum):
    MONOLITHIC = "monolithic"
    COI_SLICE = "coi_slice"
    HIERARCHY = "hierarchy"


class PropertyKind(str, Enum):
    ASSERT = "assert"
    COVER = "cover"
    ASSUME = "assume"


class ValidationStatus(str, Enum):
    """Whether the orchestrator's own record-keeping/config choice is internally valid.

    This is distinct from the *formal* result. A run may be VALID (well-formed,
    config in catalog, provenance complete) and still FAIL/TIMEOUT.
    """

    VALID = "valid"
    INVALID_CONFIG = "invalid_config"
    INCOMPLETE_PROVENANCE = "incomplete_provenance"


# --------------------------------------------------------------------------- #
# Configuration catalog
# --------------------------------------------------------------------------- #
class SolverConfig(BaseModel):
    """One approved, versioned configuration from the finite catalog.

    Every field maps to a knob the policy layer is *allowed* to choose. Nothing
    outside the catalog is executable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_id: str = Field(..., description="Stable ID, unique within a catalog version.")
    catalog_version: str = Field(..., description="Version of the catalog this config belongs to.")
    engine: EngineFamily
    bmc_depth: int = Field(..., ge=1, le=100000, description="Bounded-model-checking depth tier.")
    timeout_s: int = Field(..., ge=1, le=86400, description="Wall-clock timeout tier (seconds).")
    memory_cap_mb: int = Field(..., ge=64, le=1_048_576, description="Peak-memory cap tier (MB).")
    preprocessing: PreprocessingLevel
    partition_strategy: PartitionStrategy

    def command_line(self, design_path: str, property_id: str) -> str:
        """Deterministic, reproducible command string recorded in provenance.

        This is a *mock* command line describing what a real backend adapter would
        invoke. It is never executed as a shell command.
        """
        return (
            f"formal-backend --engine {self.engine.value} "
            f"--bmc-depth {self.bmc_depth} "
            f"--timeout {self.timeout_s} "
            f"--mem-cap-mb {self.memory_cap_mb} "
            f"--preprocess {self.preprocessing.value} "
            f"--partition {self.partition_strategy.value} "
            f"--property {property_id} {design_path}"
        )


# --------------------------------------------------------------------------- #
# Benchmark / design / property descriptors
# --------------------------------------------------------------------------- #
class PropertySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: str
    kind: PropertyKind = PropertyKind.ASSERT
    description: str = ""


class BenchmarkItem(BaseModel):
    """A public design + property pair to run, with difficulty features.

    The ``features`` are the *observable* signals a policy may condition on
    (RTL size, register count, COI size, property type, etc.). ``group`` is the
    correlated-design cluster used to build leakage-free train/test splits.
    """

    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    design_name: str
    design_sha: str = Field(..., description="Placeholder SHA of the RTL design source.")
    property: PropertySpec
    property_sha: str = Field(..., description="Placeholder SHA of the property/SVA source.")
    group: str = Field(..., description="Correlation group for leakage-free splitting.")
    # Difficulty features (deterministic, public, no proprietary data).
    rtl_lines: int = Field(..., ge=0)
    register_count: int = Field(..., ge=0)
    coi_size: int = Field(..., ge=0, description="Cone-of-influence node count estimate.")
    max_depth_hint: int = Field(..., ge=1, description="Depth at which the property resolves.")
    intrinsic_difficulty: float = Field(
        ..., ge=0.0, le=1.0, description="Public toy difficulty rating (mock ground-truth)."
    )
    # Mock ground truth for the deterministic simulator (public toy suite only).
    is_holds: bool = Field(..., description="Whether the property truly holds (toy ground truth).")


class BenchmarkSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    suite_id: str
    description: str = ""
    items: list[BenchmarkItem]

    @field_validator("items")
    @classmethod
    def _non_empty_unique(cls, v: list[BenchmarkItem]) -> list[BenchmarkItem]:
        if not v:
            raise ValueError("benchmark suite must contain at least one item")
        ids = [i.benchmark_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark_id values must be unique")
        return v


# --------------------------------------------------------------------------- #
# Experiment plan
# --------------------------------------------------------------------------- #
class PlannedRun(BaseModel):
    """A single (benchmark, config) unit of work with a rationale and seed."""

    model_config = ConfigDict(extra="forbid")

    plan_run_id: str
    benchmark_id: str
    config_id: str
    seed: int = Field(..., ge=0)
    rationale: str = Field(..., description="Why the planner/policy chose this config (heuristic).")
    policy_name: str


class ExperimentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    plan_id: str
    suite_id: str
    catalog_version: str
    policy_name: str
    created_at: datetime
    planned_runs: list[PlannedRun]


# --------------------------------------------------------------------------- #
# Run record (full provenance ledger row)
# --------------------------------------------------------------------------- #
class MachineMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    platform: str
    python_version: str
    cpu_count: int


class RunRecord(BaseModel):
    """Immutable-by-convention provenance record for one execution.

    Contains everything BUILD_STANDARD.md / spec 3.3 require: design & property
    SHAs, input hashes, tool name+version, command line, config ID, seed,
    machine/OS metadata, start/end, CPU/wall time, peak memory, return code,
    status, artifact paths/hashes, rationale, validation status.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    run_id: str
    plan_id: str
    benchmark_id: str

    # Provenance: sources
    design_sha: str
    property_sha: str
    input_hash: str = Field(..., description="Hash over (design_sha, property_sha, config).")

    # Provenance: tool + config
    tool_name: str
    tool_version: str
    config_id: str
    catalog_version: str
    command_line: str
    seed: int

    # Provenance: environment
    machine: MachineMetadata

    # Provenance: timing / resources
    start_time: datetime
    end_time: datetime
    cpu_time_s: float = Field(..., ge=0.0)
    wall_time_s: float = Field(..., ge=0.0)
    peak_memory_mb: float = Field(..., ge=0.0)
    return_code: int

    # Outcome
    status: RunStatus
    validation_status: ValidationStatus
    rationale: str

    # Artifacts
    artifact_path: str | None = None
    artifact_hash: str | None = None

    @field_validator("status")
    @classmethod
    def _no_pass_without_conclusion(cls, v: RunStatus, info) -> RunStatus:  # noqa: ANN001
        # Structural guard: PASS requires return_code 0. TIMEOUT/ERROR can never be PASS.
        data = info.data
        if v is RunStatus.PASS and data.get("return_code", 0) != 0:
            raise ValueError("PASS status requires return_code == 0")
        return v


# --------------------------------------------------------------------------- #
# Summaries / reports
# --------------------------------------------------------------------------- #
class StatusCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    PASS: int = 0
    FAIL: int = 0
    TIMEOUT: int = 0
    ERROR: int = 0
    INCONCLUSIVE: int = 0

    @property
    def total(self) -> int:
        return self.PASS + self.FAIL + self.TIMEOUT + self.ERROR + self.INCONCLUSIVE


class PolicyMetrics(BaseModel):
    """Offline-evaluable metrics for one policy over a benchmark split."""

    model_config = ConfigDict(extra="forbid")

    policy_name: str
    split: str = Field(..., description="'train', 'test', or 'all'.")
    n_designs: int
    n_attempts: int
    status_counts: StatusCounts
    solved_within_budget_pct: float = Field(..., ge=0.0, le=100.0)
    total_cpu_time_s: float = Field(..., ge=0.0)
    total_wall_time_s: float = Field(..., ge=0.0)
    peak_memory_mb: float = Field(..., ge=0.0)
    mean_reward: float
    per_design_reward_variance: float = Field(..., ge=0.0)
    reward_ci95: tuple[float, float] | None = None
