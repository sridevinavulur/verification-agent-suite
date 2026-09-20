"""Deterministic public benchmark generator.

Produces a mock-telemetry dataset spanning several commits, two configs, two
workloads and two platforms. Exactly one *real* regression is injected (a
simulation-runtime blow-up on one config/workload at a specific commit) plus a
genuine improvement. Everything else is stable-with-noise. A separate noise-only
group exists to prove the detector does NOT false-alarm.

The generator uses a seeded PRNG so output is byte-for-byte reproducible; no
real telemetry, tools, or network access is involved.
"""

from __future__ import annotations

import random

from .models import (
    Environment,
    MetricName,
    MetricSample,
    TelemetryDataset,
    TelemetryRun,
)

SEED = 20260920

# Baseline metric values per (config, workload). Kept deliberately simple.
_BASE = {
    MetricName.SIM_RUNTIME_S: 120.0,
    MetricName.PEAK_MEMORY_MB: 2048.0,
    MetricName.THROUGHPUT_MOPS: 850.0,
    MetricName.LATENCY_NS: 42.0,
    MetricName.COVERAGE_RATE_PCT: 78.0,
    MetricName.FORMAL_RUNTIME_S: 300.0,
    MetricName.BANDWIDTH_GBPS: 25.0,
    MetricName.UTILIZATION_PCT: 65.0,
    MetricName.FPGA_FMAX_MHZ: 300.0,
    MetricName.FPGA_LUT_UTIL_PCT: 55.0,
}

# Per-metric relative measurement noise (1-sigma fraction of the value).
_NOISE = {
    MetricName.SIM_RUNTIME_S: 0.02,
    MetricName.PEAK_MEMORY_MB: 0.01,
    MetricName.THROUGHPUT_MOPS: 0.02,
    MetricName.LATENCY_NS: 0.03,
    MetricName.COVERAGE_RATE_PCT: 0.005,
    MetricName.FORMAL_RUNTIME_S: 0.04,
    MetricName.BANDWIDTH_GBPS: 0.02,
    MetricName.UTILIZATION_PCT: 0.02,
    MetricName.FPGA_FMAX_MHZ: 0.01,
    MetricName.FPGA_LUT_UTIL_PCT: 0.01,
}

_COMMITS = [
    "a1b2c3d",
    "b2c3d4e",
    "c3d4e5f",  # <- regression injected here for sim@cache_stress/x86
    "d4e5f6a",
    "e5f6a7b",
]

_REPS = 5  # repetitions per metric


def _env_x86() -> Environment:
    return Environment(
        platform="x86_64-linux",
        cpu_model="generic-16c",
        ram_gb=64.0,
        tool="verilator",
        tool_version="5.020",
        os_release="ubuntu-22.04",
    )


def _env_fpga() -> Environment:
    return Environment(
        platform="fpga-u250",
        cpu_model="generic-16c",
        ram_gb=64.0,
        tool="vivado",
        tool_version="2023.2",
        os_release="ubuntu-22.04",
    )


def _samples(
    rng: random.Random,
    metrics: dict[MetricName, float],
) -> list[MetricSample]:
    out: list[MetricSample] = []
    for metric, mean in metrics.items():
        sigma = mean * _NOISE[metric]
        for _ in range(_REPS):
            out.append(MetricSample(metric=metric, value=round(rng.gauss(mean, sigma), 4)))
    return out


def build_dataset() -> TelemetryDataset:
    rng = random.Random(SEED)
    runs: list[TelemetryRun] = []

    # ---- Group A: x86 sim, cache_stress workload — INJECTED REGRESSION ---- #
    for i, commit in enumerate(_COMMITS):
        metrics = {
            MetricName.SIM_RUNTIME_S: _BASE[MetricName.SIM_RUNTIME_S],
            MetricName.PEAK_MEMORY_MB: _BASE[MetricName.PEAK_MEMORY_MB],
            MetricName.THROUGHPUT_MOPS: _BASE[MetricName.THROUGHPUT_MOPS],
            MetricName.COVERAGE_RATE_PCT: _BASE[MetricName.COVERAGE_RATE_PCT],
        }
        # Regression injected at commit index 2 and persists afterward:
        # sim runtime +35%, peak memory +18%.
        if i >= 2:
            metrics[MetricName.SIM_RUNTIME_S] *= 1.35
            metrics[MetricName.PEAK_MEMORY_MB] *= 1.18
        runs.append(
            TelemetryRun(
                run_id=f"A-{commit}",
                commit=commit,
                commit_order=i,
                config="opt3",
                workload="cache_stress",
                environment=_env_x86(),
                timestamp=f"2026-09-{10 + i:02d}T00:00:00Z",
                artifact_url=f"https://ci.example.org/artifacts/A/{commit}",
                samples=_samples(rng, metrics),
            )
        )

    # ---- Group B: x86 sim, random_rw workload — GENUINE IMPROVEMENT ---- #
    for i, commit in enumerate(_COMMITS):
        metrics = {
            MetricName.SIM_RUNTIME_S: _BASE[MetricName.SIM_RUNTIME_S] * 0.9,
            MetricName.THROUGHPUT_MOPS: _BASE[MetricName.THROUGHPUT_MOPS],
            MetricName.LATENCY_NS: _BASE[MetricName.LATENCY_NS],
        }
        # Throughput improves +22% at the last commit (optimization landed).
        if i >= 4:
            metrics[MetricName.THROUGHPUT_MOPS] *= 1.22
            metrics[MetricName.LATENCY_NS] *= 0.85
        runs.append(
            TelemetryRun(
                run_id=f"B-{commit}",
                commit=commit,
                commit_order=i,
                config="opt3",
                workload="random_rw",
                environment=_env_x86(),
                timestamp=f"2026-09-{10 + i:02d}T01:00:00Z",
                artifact_url=f"https://ci.example.org/artifacts/B/{commit}",
                samples=_samples(rng, metrics),
            )
        )

    # ---- Group C: x86 sim, smoke workload — PURE NOISE (must NOT flag) ---- #
    for i, commit in enumerate(_COMMITS):
        metrics = {
            MetricName.SIM_RUNTIME_S: _BASE[MetricName.SIM_RUNTIME_S] * 0.5,
            MetricName.PEAK_MEMORY_MB: _BASE[MetricName.PEAK_MEMORY_MB] * 0.7,
            MetricName.COVERAGE_RATE_PCT: _BASE[MetricName.COVERAGE_RATE_PCT],
        }
        runs.append(
            TelemetryRun(
                run_id=f"C-{commit}",
                commit=commit,
                commit_order=i,
                config="debug",
                workload="smoke",
                environment=_env_x86(),
                timestamp=f"2026-09-{10 + i:02d}T02:00:00Z",
                artifact_url=f"https://ci.example.org/artifacts/C/{commit}",
                samples=_samples(rng, metrics),
            )
        )

    # ---- Group D: FPGA build — STABLE with one outlier sample (must survive) ---- #
    for i, commit in enumerate(_COMMITS):
        metrics = {
            MetricName.FPGA_FMAX_MHZ: _BASE[MetricName.FPGA_FMAX_MHZ],
            MetricName.FPGA_LUT_UTIL_PCT: _BASE[MetricName.FPGA_LUT_UTIL_PCT],
            MetricName.FORMAL_RUNTIME_S: _BASE[MetricName.FORMAL_RUNTIME_S],
        }
        samples = _samples(rng, metrics)
        # Inject a single wild fmax outlier on the newest commit; robust stats
        # must reject it and keep the group STABLE (no false regression).
        if i == len(_COMMITS) - 1:
            samples.append(MetricSample(metric=MetricName.FPGA_FMAX_MHZ, value=150.0))
        runs.append(
            TelemetryRun(
                run_id=f"D-{commit}",
                commit=commit,
                commit_order=i,
                config="synth",
                workload="top_build",
                environment=_env_fpga(),
                timestamp=f"2026-09-{10 + i:02d}T03:00:00Z",
                artifact_url=f"https://ci.example.org/artifacts/D/{commit}",
                samples=samples,
            )
        )

    return TelemetryDataset(name="public-mock-benchmark", runs=runs)
