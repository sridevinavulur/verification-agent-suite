"""Tests for the deterministic detector behavior on the benchmark."""

from __future__ import annotations

from perf_regression_agent.benchmark import build_dataset
from perf_regression_agent.detector import analyze
from perf_regression_agent.models import (
    Environment,
    MetricName,
    MetricSample,
    TelemetryDataset,
    TelemetryRun,
    Verdict,
)


def _reg_keys(report):
    return {
        (f.metric, f.config, f.workload)
        for f in report.findings
        if f.verdict == Verdict.REGRESSION
    }


def test_detects_exactly_the_injected_regressions(report):
    keys = _reg_keys(report)
    assert (MetricName.SIM_RUNTIME_S, "opt3", "cache_stress") in keys
    assert (MetricName.PEAK_MEMORY_MB, "opt3", "cache_stress") in keys
    assert report.n_regressions == 2


def test_no_false_alarm_on_noise_group(report):
    # The debug/smoke group is pure noise; nothing there may be a regression.
    for f in report.findings:
        if f.config == "debug" and f.workload == "smoke":
            assert f.verdict == Verdict.STABLE


def test_fpga_outlier_does_not_cause_false_regression(report):
    # Group D has a wild fmax outlier on the last commit; must stay STABLE.
    fmax = [
        f for f in report.findings
        if f.metric == MetricName.FPGA_FMAX_MHZ and f.workload == "top_build"
    ]
    assert len(fmax) == 1
    assert fmax[0].verdict == Verdict.STABLE
    # And the outlier must have been rejected from at least one side.
    assert (
        fmax[0].candidate_stats.outliers
        or fmax[0].baseline_stats.outliers
        or 150.0 not in fmax[0].candidate_stats.kept
    )


def test_detects_genuine_improvement(report):
    improvements = {
        (f.metric, f.workload)
        for f in report.findings
        if f.verdict == Verdict.IMPROVEMENT
    }
    assert (MetricName.THROUGHPUT_MOPS, "random_rw") in improvements


def test_regression_has_direction_and_evidence(report):
    for f in report.findings:
        if f.verdict == Verdict.REGRESSION:
            assert f.evidence, "regression must carry evidence"
            assert f.delta_pct > 0  # sim/mem are lower-is-better -> increase = worse
            assert abs(f.robust_z) >= report.detection_config.robust_z_threshold
            assert f.artifact_urls  # artifact links propagated


def test_analysis_is_deterministic():
    r1 = analyze(build_dataset())
    r2 = analyze(build_dataset())
    assert r1.model_dump() == r2.model_dump()


def test_incomparable_runs_not_compared_across_platforms():
    # Two runs on different platforms must NOT be paired.
    env_a = Environment(platform="x86_64-linux", tool="verilator", tool_version="5.0")
    env_b = Environment(platform="fpga-u250", tool="vivado", tool_version="2023.2")
    ds = TelemetryDataset(
        name="mixed",
        runs=[
            TelemetryRun(
                run_id="1", commit="old", commit_order=0, config="c", workload="w",
                environment=env_a,
                samples=[MetricSample(metric=MetricName.SIM_RUNTIME_S, value=100.0)],
            ),
            TelemetryRun(
                run_id="2", commit="new", commit_order=1, config="c", workload="w",
                environment=env_b,
                samples=[MetricSample(metric=MetricName.SIM_RUNTIME_S, value=200.0)],
            ),
        ],
    )
    report = analyze(ds)
    # Different fingerprints -> two groups of size 1 -> no comparison at all.
    assert report.n_comparisons == 0


def test_low_samples_large_change_is_inconclusive_not_regression():
    env = Environment(platform="x86_64-linux", tool="verilator", tool_version="5.0")
    ds = TelemetryDataset(
        name="sparse",
        runs=[
            TelemetryRun(
                run_id="1", commit="old", commit_order=0, config="c", workload="w",
                environment=env,
                samples=[MetricSample(metric=MetricName.SIM_RUNTIME_S, value=100.0)],
            ),
            TelemetryRun(
                run_id="2", commit="new", commit_order=1, config="c", workload="w",
                environment=env,
                samples=[MetricSample(metric=MetricName.SIM_RUNTIME_S, value=140.0)],
            ),
        ],
    )
    report = analyze(ds)
    f = report.findings[0]
    # Single sample each side: cannot confirm -> INCONCLUSIVE, never a false PASS.
    assert f.verdict == Verdict.INCONCLUSIVE
