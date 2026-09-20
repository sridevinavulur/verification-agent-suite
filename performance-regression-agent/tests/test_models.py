"""Tests for the versioned Pydantic contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from perf_regression_agent.models import (
    SCHEMA_VERSION,
    Environment,
    MetricName,
    MetricSample,
    MetricStats,
    RegressionFinding,
    TelemetryRun,
    Verdict,
)


def _env() -> Environment:
    return Environment(platform="x86_64-linux", tool="verilator", tool_version="5.020")


def test_env_fingerprint_groups_by_hw_and_tool():
    e1 = Environment(platform="x86_64-linux", tool="verilator", tool_version="5.020")
    e2 = Environment(platform="x86_64-linux", tool="verilator", tool_version="5.021")
    assert e1.fingerprint() != e2.fingerprint()
    assert e1.fingerprint() == "x86_64-linux|verilator@5.020"


def test_metric_sample_rejects_nan():
    with pytest.raises(ValidationError):
        MetricSample(metric=MetricName.LATENCY_NS, value=float("nan"))


def test_metric_sample_rejects_inf():
    with pytest.raises(ValidationError):
        MetricSample(metric=MetricName.LATENCY_NS, value=float("inf"))


def test_run_rejects_incompatible_major_schema():
    with pytest.raises(ValidationError):
        TelemetryRun(
            schema_version="9.0.0",
            run_id="r",
            commit="abc",
            commit_order=0,
            config="c",
            workload="w",
            environment=_env(),
            samples=[MetricSample(metric=MetricName.LATENCY_NS, value=1.0)],
        )


def test_run_requires_at_least_one_sample():
    with pytest.raises(ValidationError):
        TelemetryRun(
            run_id="r",
            commit="abc",
            commit_order=0,
            config="c",
            workload="w",
            environment=_env(),
            samples=[],
        )


def test_run_values_for_filters_by_metric():
    run = TelemetryRun(
        run_id="r",
        commit="abc",
        commit_order=0,
        config="c",
        workload="w",
        environment=_env(),
        samples=[
            MetricSample(metric=MetricName.LATENCY_NS, value=1.0),
            MetricSample(metric=MetricName.LATENCY_NS, value=2.0),
            MetricSample(metric=MetricName.PEAK_MEMORY_MB, value=100.0),
        ],
    )
    assert run.values_for(MetricName.LATENCY_NS) == [1.0, 2.0]
    assert run.values_for(MetricName.PEAK_MEMORY_MB) == [100.0]


def _stats(metric: MetricName) -> MetricStats:
    return MetricStats(
        metric=metric, n=3, mean=1.0, stdev=0.1, median=1.0,
        ci95_low=0.9, ci95_high=1.1, cv=0.1,
    )


def test_regression_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        RegressionFinding(
            metric=MetricName.SIM_RUNTIME_S,
            unit="s",
            config="c",
            workload="w",
            env_fingerprint="fp",
            baseline_commit="a",
            candidate_commit="b",
            baseline_stats=_stats(MetricName.SIM_RUNTIME_S),
            candidate_stats=_stats(MetricName.SIM_RUNTIME_S),
            delta_abs=1.0,
            delta_pct=35.0,
            robust_z=10.0,
            verdict=Verdict.REGRESSION,
            confidence=0.9,
            evidence=[],
        )


def test_regression_with_evidence_is_accepted():
    f = RegressionFinding(
        metric=MetricName.SIM_RUNTIME_S,
        unit="s",
        config="c",
        workload="w",
        env_fingerprint="fp",
        baseline_commit="a",
        candidate_commit="b",
        baseline_stats=_stats(MetricName.SIM_RUNTIME_S),
        candidate_stats=_stats(MetricName.SIM_RUNTIME_S),
        delta_abs=1.0,
        delta_pct=35.0,
        robust_z=10.0,
        verdict=Verdict.REGRESSION,
        confidence=0.9,
        evidence=["runtime up 35%"],
    )
    assert f.verdict == Verdict.REGRESSION


def test_schema_version_constant_is_semver():
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
