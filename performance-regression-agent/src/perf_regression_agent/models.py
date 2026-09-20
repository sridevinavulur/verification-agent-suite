"""Typed data contracts (Pydantic v2) for the Performance Regression Agent.

The schema is *versioned*: every telemetry record and report carries
``schema_version`` so downstream tooling can detect incompatible payloads.
All models validate (not merely annotate) their inputs.
"""

from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "1.0.0"

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class MetricName(str, Enum):
    """Canonical performance metric identifiers.

    Kept as (str, Enum) for stable, human-readable JSON serialization.
    """

    SIM_RUNTIME_S = "sim_runtime_s"
    FORMAL_RUNTIME_S = "formal_runtime_s"
    PEAK_MEMORY_MB = "peak_memory_mb"
    THROUGHPUT_MOPS = "throughput_mops"
    LATENCY_NS = "latency_ns"
    BANDWIDTH_GBPS = "bandwidth_gbps"
    UTILIZATION_PCT = "utilization_pct"
    COVERAGE_RATE_PCT = "coverage_rate_pct"
    FPGA_FMAX_MHZ = "fpga_fmax_mhz"
    FPGA_LUT_UTIL_PCT = "fpga_lut_util_pct"


# Direction of "goodness": for some metrics higher is better, for others lower.
# A regression is always a change in the *bad* direction.
HIGHER_IS_BETTER: dict[MetricName, bool] = {
    MetricName.SIM_RUNTIME_S: False,
    MetricName.FORMAL_RUNTIME_S: False,
    MetricName.PEAK_MEMORY_MB: False,
    MetricName.THROUGHPUT_MOPS: True,
    MetricName.LATENCY_NS: False,
    MetricName.BANDWIDTH_GBPS: True,
    MetricName.UTILIZATION_PCT: True,
    MetricName.COVERAGE_RATE_PCT: True,
    MetricName.FPGA_FMAX_MHZ: True,
    MetricName.FPGA_LUT_UTIL_PCT: False,
}

METRIC_UNITS: dict[MetricName, str] = {
    MetricName.SIM_RUNTIME_S: "s",
    MetricName.FORMAL_RUNTIME_S: "s",
    MetricName.PEAK_MEMORY_MB: "MB",
    MetricName.THROUGHPUT_MOPS: "Mops",
    MetricName.LATENCY_NS: "ns",
    MetricName.BANDWIDTH_GBPS: "GB/s",
    MetricName.UTILIZATION_PCT: "%",
    MetricName.COVERAGE_RATE_PCT: "%",
    MetricName.FPGA_FMAX_MHZ: "MHz",
    MetricName.FPGA_LUT_UTIL_PCT: "%",
}


class Verdict(str, Enum):
    """Deterministic classification of a single metric comparison."""

    REGRESSION = "REGRESSION"
    IMPROVEMENT = "IMPROVEMENT"
    STABLE = "STABLE"
    INCONCLUSIVE = "INCONCLUSIVE"  # too few samples / high variance


# --------------------------------------------------------------------------- #
# Environment / provenance
# --------------------------------------------------------------------------- #


class Environment(BaseModel):
    """Hardware and tool-version context for a set of measurements."""

    model_config = ConfigDict(extra="forbid")

    platform: str = Field(..., description="e.g. 'x86_64-linux', 'fpga-u250'")
    cpu_model: str | None = None
    ram_gb: float | None = Field(default=None, ge=0)
    tool: str = Field(..., description="e.g. 'verilator', 'jaspergold', 'vivado'")
    tool_version: str = Field(..., description="e.g. '5.020'")
    os_release: str | None = None

    def fingerprint(self) -> str:
        """Stable key used to group comparable runs (same HW + tool version)."""
        return f"{self.platform}|{self.tool}@{self.tool_version}"


class MetricSample(BaseModel):
    """A single measured value for one metric within a run."""

    model_config = ConfigDict(extra="forbid")

    metric: MetricName
    value: float = Field(..., description="Measured value in the metric's canonical unit")

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("metric value must be finite")
        return v


class TelemetryRun(BaseModel):
    """One execution of a workload on a commit/config, with repeated samples.

    ``samples`` holds one-or-more repetitions per metric so variance and
    confidence can be computed. A run is scoped to a (commit, config,
    workload, environment) tuple.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    run_id: str
    commit: str = Field(..., description="Git SHA (placeholder allowed)")
    commit_order: int = Field(..., ge=0, description="Monotonic index; higher = newer")
    config: str = Field(..., description="Build/experiment configuration name")
    workload: str = Field(..., description="Workload / trace name")
    environment: Environment
    timestamp: str | None = None
    artifact_url: str | None = Field(
        default=None, description="Link to raw logs/waveforms/reports"
    )
    samples: list[MetricSample] = Field(..., min_length=1)

    @field_validator("schema_version")
    @classmethod
    def _check_schema(cls, v: str) -> str:
        major = v.split(".", 1)[0]
        want = SCHEMA_VERSION.split(".", 1)[0]
        if major != want:
            raise ValueError(
                f"incompatible schema_version {v!r}; agent supports major {want}.x"
            )
        return v

    def values_for(self, metric: MetricName) -> list[float]:
        return [s.value for s in self.samples if s.metric == metric]


class TelemetryDataset(BaseModel):
    """A collection of telemetry runs forming the analysis input."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    name: str
    runs: list[TelemetryRun] = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# Statistics & findings
# --------------------------------------------------------------------------- #


class MetricStats(BaseModel):
    """Summary statistics for repeated samples of a metric."""

    model_config = ConfigDict(extra="forbid")

    metric: MetricName
    n: int = Field(..., ge=1)
    mean: float
    stdev: float = Field(..., ge=0)
    median: float
    ci95_low: float
    ci95_high: float
    cv: float = Field(..., ge=0, description="Coefficient of variation (stdev/|mean|)")
    kept: list[float] = Field(default_factory=list, description="Non-outlier samples")
    outliers: list[float] = Field(
        default_factory=list, description="Samples rejected by robust outlier filter"
    )


class RegressionFinding(BaseModel):
    """Deterministic per-metric comparison of a candidate vs a baseline."""

    model_config = ConfigDict(extra="forbid")

    metric: MetricName
    unit: str
    config: str
    workload: str
    env_fingerprint: str
    baseline_commit: str
    candidate_commit: str
    baseline_stats: MetricStats
    candidate_stats: MetricStats
    delta_abs: float = Field(..., description="candidate.mean - baseline.mean")
    delta_pct: float = Field(..., description="signed % change of the mean")
    robust_z: float = Field(
        ..., description="Change measured in baseline robust sigmas (MAD-based)"
    )
    verdict: Verdict
    confidence: float = Field(..., ge=0, le=1)
    evidence: list[str] = Field(
        default_factory=list,
        description="Human-readable statements supporting the verdict",
    )
    artifact_urls: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _regression_needs_evidence(self) -> RegressionFinding:
        # Safety rule: no regression/improvement claim without supporting evidence.
        if self.verdict in (Verdict.REGRESSION, Verdict.IMPROVEMENT) and not self.evidence:
            raise ValueError(
                f"{self.verdict} finding must include supporting evidence"
            )
        return self


class DetectionConfig(BaseModel):
    """Tunable, versioned thresholds for the deterministic detector."""

    model_config = ConfigDict(extra="forbid")

    min_pct_change: float = Field(
        default=5.0, ge=0, description="Minimum |%| mean change to consider notable"
    )
    robust_z_threshold: float = Field(
        default=3.5, ge=0, description="Robust z (MAD) above which change is significant"
    )
    min_samples_for_confident: int = Field(default=3, ge=1)
    outlier_iqr_k: float = Field(default=1.5, ge=0)
    outlier_z_threshold: float = Field(default=3.5, ge=0)


class RegressionReport(BaseModel):
    """Top-level report contract (serialized to JSON and rendered to Markdown)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    dataset_name: str
    detection_config: DetectionConfig
    n_runs: int
    n_comparisons: int
    n_regressions: int
    findings: list[RegressionFinding]

    def regressions(self) -> list[RegressionFinding]:
        return [f for f in self.findings if f.verdict == Verdict.REGRESSION]
