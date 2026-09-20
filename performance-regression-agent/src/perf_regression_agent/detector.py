"""Deterministic performance-regression detector.

Detection is *controlled*: candidate runs are only ever compared against a
baseline sharing the same (config, workload, environment) so we never confuse a
platform/tool change for a code regression. Every REGRESSION/IMPROVEMENT verdict
carries explicit supporting evidence; ambiguous cases are INCONCLUSIVE, never a
false PASS/STABLE dressed up as certainty.
"""

from __future__ import annotations

from collections import defaultdict

from . import statistics as st
from .models import (
    HIGHER_IS_BETTER,
    METRIC_UNITS,
    DetectionConfig,
    MetricName,
    RegressionFinding,
    RegressionReport,
    TelemetryDataset,
    TelemetryRun,
    Verdict,
)

# A comparison group: runs that are directly comparable to each other.
_GroupKey = tuple[str, str, str]  # (config, workload, env_fingerprint)


def _group_key(run: TelemetryRun) -> _GroupKey:
    return (run.config, run.workload, run.environment.fingerprint())


def _select_baseline_and_candidate(
    runs: list[TelemetryRun],
) -> tuple[TelemetryRun, TelemetryRun] | None:
    """Baseline = oldest commit in group; candidate = newest. Requires >= 2."""
    if len(runs) < 2:
        return None
    ordered = sorted(runs, key=lambda r: r.commit_order)
    baseline = ordered[0]
    candidate = ordered[-1]
    if baseline.commit == candidate.commit:
        return None
    return baseline, candidate


def _classify(
    metric: MetricName,
    delta_pct: float,
    robust_z: float,
    cfg: DetectionConfig,
    baseline_n: int,
    candidate_n: int,
) -> tuple[Verdict, float, list[str]]:
    """Pure classification from computed statistics -> (verdict, confidence, evidence)."""
    unit = METRIC_UNITS[metric]
    higher_better = HIGHER_IS_BETTER[metric]
    evidence: list[str] = []

    abs_pct = abs(delta_pct)
    abs_z = abs(robust_z)

    # A change is "significant" only when BOTH the effect size (%) and the
    # robustness-to-noise (robust z) thresholds are met.
    significant = abs_pct >= cfg.min_pct_change and abs_z >= cfg.robust_z_threshold

    # Determine whether the (significant) change moved in the bad direction.
    got_worse = (delta_pct < 0) if higher_better else (delta_pct > 0)

    min_n = min(baseline_n, candidate_n)

    if not significant:
        # Not enough evidence of a real change -> STABLE, unless too few samples
        # AND the point estimate looks large (then we refuse to call it stable).
        if min_n < cfg.min_samples_for_confident and abs_pct >= cfg.min_pct_change:
            return (
                Verdict.INCONCLUSIVE,
                0.3,
                [
                    f"Point estimate moved {delta_pct:+.1f}% but only {min_n} "
                    f"sample(s) and robust z={robust_z:+.2f} < "
                    f"{cfg.robust_z_threshold}: insufficient to confirm."
                ],
            )
        return (Verdict.STABLE, 0.6, [])

    # Significant change: build evidence.
    direction = "worse" if got_worse else "better"
    evidence.append(
        f"Mean changed {delta_pct:+.1f}% (unit: {unit}), "
        f"|Δ%|={abs_pct:.1f}% ≥ {cfg.min_pct_change}%."
    )
    evidence.append(
        f"Robust z={robust_z:+.2f} (MAD-based) exceeds ±{cfg.robust_z_threshold}: "
        f"change is large relative to baseline noise."
    )
    evidence.append(
        f"Metric '{metric.value}' is "
        f"{'higher-is-better' if higher_better else 'lower-is-better'}; "
        f"observed direction is {direction}."
    )

    # Confidence scales with sample count and effect size (bounded).
    conf = 0.5
    if min_n >= cfg.min_samples_for_confident:
        conf += 0.25
    conf += min(0.15, (abs_z - cfg.robust_z_threshold) * 0.02)
    conf += min(0.10, (abs_pct - cfg.min_pct_change) * 0.005)
    conf = max(0.0, min(1.0, conf))

    if got_worse:
        return (Verdict.REGRESSION, conf, evidence)
    return (Verdict.IMPROVEMENT, conf, evidence)


def compare_pair(
    baseline: TelemetryRun,
    candidate: TelemetryRun,
    metric: MetricName,
    cfg: DetectionConfig,
) -> RegressionFinding | None:
    """Compare a single metric between two directly-comparable runs."""
    base_raw = baseline.values_for(metric)
    cand_raw = candidate.values_for(metric)
    if not base_raw or not cand_raw:
        return None

    base_stats = st.summarize(
        metric, base_raw, iqr_k=cfg.outlier_iqr_k, z_threshold=cfg.outlier_z_threshold
    )
    cand_stats = st.summarize(
        metric, cand_raw, iqr_k=cfg.outlier_iqr_k, z_threshold=cfg.outlier_z_threshold
    )

    delta_abs = cand_stats.mean - base_stats.mean
    delta_pct = (delta_abs / base_stats.mean * 100.0) if base_stats.mean != 0 else 0.0
    robust_z = st.robust_z_change(cand_stats.mean, base_stats, base_stats.kept)

    verdict, confidence, evidence = _classify(
        metric, delta_pct, robust_z, cfg, base_stats.n, cand_stats.n
    )

    if verdict in (Verdict.REGRESSION, Verdict.IMPROVEMENT):
        if base_stats.outliers or cand_stats.outliers:
            evidence.append(
                f"Outliers rejected before comparison: "
                f"baseline={base_stats.outliers}, candidate={cand_stats.outliers}."
            )
        evidence.append(
            f"Baseline mean={base_stats.mean:.3f} "
            f"[95% CI {base_stats.ci95_low:.3f}, {base_stats.ci95_high:.3f}], "
            f"candidate mean={cand_stats.mean:.3f} "
            f"[95% CI {cand_stats.ci95_low:.3f}, {cand_stats.ci95_high:.3f}]."
        )

    artifacts = [u for u in (baseline.artifact_url, candidate.artifact_url) if u]

    return RegressionFinding(
        metric=metric,
        unit=METRIC_UNITS[metric],
        config=candidate.config,
        workload=candidate.workload,
        env_fingerprint=candidate.environment.fingerprint(),
        baseline_commit=baseline.commit,
        candidate_commit=candidate.commit,
        baseline_stats=base_stats,
        candidate_stats=cand_stats,
        delta_abs=delta_abs,
        delta_pct=delta_pct,
        robust_z=robust_z,
        verdict=verdict,
        confidence=confidence,
        evidence=evidence,
        artifact_urls=artifacts,
    )


def analyze(
    dataset: TelemetryDataset,
    cfg: DetectionConfig | None = None,
) -> RegressionReport:
    """Run the full controlled comparison over every comparable group & metric."""
    cfg = cfg or DetectionConfig()

    groups: dict[_GroupKey, list[TelemetryRun]] = defaultdict(list)
    for run in dataset.runs:
        groups[_group_key(run)].append(run)

    findings: list[RegressionFinding] = []
    n_comparisons = 0

    for key in sorted(groups):
        runs = groups[key]
        pair = _select_baseline_and_candidate(runs)
        if pair is None:
            continue
        baseline, candidate = pair

        # Only compare metrics present in both runs.
        base_metrics = {s.metric for s in baseline.samples}
        cand_metrics = {s.metric for s in candidate.samples}
        for metric in sorted(base_metrics & cand_metrics, key=lambda m: m.value):
            finding = compare_pair(baseline, candidate, metric, cfg)
            if finding is None:
                continue
            n_comparisons += 1
            findings.append(finding)

    # Sort: regressions first (by severity), then others.
    def _sort_key(f: RegressionFinding) -> tuple[int, float]:
        rank = {Verdict.REGRESSION: 0, Verdict.INCONCLUSIVE: 1,
                Verdict.IMPROVEMENT: 2, Verdict.STABLE: 3}[f.verdict]
        return (rank, -abs(f.robust_z))

    findings.sort(key=_sort_key)

    n_regressions = sum(1 for f in findings if f.verdict == Verdict.REGRESSION)

    return RegressionReport(
        dataset_name=dataset.name,
        detection_config=cfg,
        n_runs=len(dataset.runs),
        n_comparisons=n_comparisons,
        n_regressions=n_regressions,
        findings=findings,
    )
