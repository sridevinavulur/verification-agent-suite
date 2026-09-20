"""Deterministic clustering and statistical-baseline engine.

This is the authoritative layer. Every finding here is produced by deterministic
code from the ingested records -- no LLM, no randomness -- so results are stable
and reproducible (golden-testable). The LLM adapter (``explain.py``) may only
*narrate* findings that this module has already substantiated.

Analyses implemented (spec 6.9 outputs):
  * failure clusters            -> group FAIL runs by shared signature
  * timeout clusters            -> group TIMEOUT runs by shared config/budget
  * duplicate / near-duplicate  -> signature hashing over identical inputs
  * runtime-regression alerts   -> z-score / robust-z vs per-job baseline
  * memory-regression alerts    -> same, on peak_memory_mb
  * configuration-sensitivity   -> per-benchmark spread across configs
  * reproducibility warnings    -> status flips / high CoV across repeats of a job
  * prioritized investigation queue

Correlation != causation: none of these outputs asserts a root cause. Each is a
statistical/structural pattern labelled HEURISTIC.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence

from . import stats
from .models import (
    BaselineStats,
    ConfigSensitivityEvidence,
    Finding,
    FindingKind,
    InvestigationItem,
    RegressionEvidence,
    RegressionReport,
    ReproEvidence,
    RunRecord,
    Severity,
    severity_rank,
)


# --------------------------------------------------------------------------- #
# Thresholds (all explicit, all documented; deterministic)
# --------------------------------------------------------------------------- #
class Thresholds:
    """Tunable, explicit detection thresholds. Defaults chosen for clarity.

    Every threshold is a documented knob, not a hidden constant, so a reviewer
    can see exactly why a finding fired.
    """

    # A job needs at least this many *baseline* runs before a regression can fire.
    min_baseline_runs: int = 3
    # Robust-z above this flags a runtime/memory regression.
    regression_robust_z: float = 3.5
    # ...but only if the latest value is also at least this ratio over the median
    # (guards against flagging tiny absolute changes on very stable baselines).
    regression_min_ratio: float = 1.5
    # A benchmark whose per-config median wall time spreads by >= this ratio is
    # "configuration-sensitive".
    config_spread_ratio: float = 3.0
    # A cluster must have at least this many members to be reported.
    min_cluster_size: int = 2
    # A duplicate group must have at least this many identical-input runs.
    min_duplicate_group: int = 2


# --------------------------------------------------------------------------- #
# Grouping helpers
# --------------------------------------------------------------------------- #
def _by_job(records: Sequence[RunRecord]) -> dict[str, list[RunRecord]]:
    groups: dict[str, list[RunRecord]] = defaultdict(list)
    for r in records:
        groups[r.job_key].append(r)
    # Stable chronological-ish ordering: by (start_time or run_id, run_id).
    for key in groups:
        groups[key].sort(key=lambda r: (str(r.start_time), r.run_id))
    return groups


def _by_benchmark(records: Sequence[RunRecord]) -> dict[str, list[RunRecord]]:
    groups: dict[str, list[RunRecord]] = defaultdict(list)
    for r in records:
        groups[r.benchmark_id].append(r)
    return groups


def _signature_hash(fields: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(fields).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 1. Failure clusters
# --------------------------------------------------------------------------- #
def failure_clusters(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Group FAIL runs by (property_sha, return_code) signature.

    Runs that fail on the same property with the same return code are likely the
    same underlying issue and should be triaged together. Grouping is structural,
    not causal.
    """
    fails = [r for r in records if r.status.value == "FAIL"]
    buckets: dict[tuple[str, int], list[RunRecord]] = defaultdict(list)
    for r in fails:
        buckets[(r.property_sha, r.return_code)].append(r)

    findings: list[Finding] = []
    for (prop_sha, rc), members in sorted(buckets.items(), key=lambda kv: kv[0]):
        if len(members) < th.min_cluster_size:
            continue
        sig = _signature_hash((prop_sha, str(rc)))
        benches = sorted({m.benchmark_id for m in members})
        configs = sorted({m.config_id for m in members})
        sev = Severity.HIGH if len(members) >= 4 else Severity.MEDIUM
        findings.append(
            Finding(
                finding_id=f"failcluster-{sig}",
                kind=FindingKind.FAILURE_CLUSTER,
                severity=sev,
                title=f"{len(members)} FAIL runs share property/return-code signature",
                summary=(
                    f"{len(members)} runs across {len(benches)} benchmark(s) failed on the "
                    f"same property (sha {prop_sha[:8]}) with return_code={rc}. "
                    "Likely the same failure mode; triage together (HEURISTIC)."
                ),
                member_run_ids=[m.run_id for m in members],
                benchmark_ids=benches,
                config_ids=configs,
                evidence={
                    "property_sha": prop_sha,
                    "return_code": rc,
                    "n_members": len(members),
                    "n_benchmarks": len(benches),
                },
                priority_score=float(len(members)) * 2.0,
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# 2. Timeout clusters
# --------------------------------------------------------------------------- #
def timeout_clusters(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Group TIMEOUT runs by config_id.

    A config that times out repeatedly is a budget/engine-fit problem shared by
    many jobs. A TIMEOUT is never a PASS; it is reached-no-conclusion.
    """
    timeouts = [r for r in records if r.status.value == "TIMEOUT"]
    buckets: dict[str, list[RunRecord]] = defaultdict(list)
    for r in timeouts:
        buckets[r.config_id].append(r)

    findings: list[Finding] = []
    for config_id, members in sorted(buckets.items()):
        if len(members) < th.min_cluster_size:
            continue
        benches = sorted({m.benchmark_id for m in members})
        sig = _signature_hash((config_id, "timeout"))
        sev = Severity.HIGH if len(members) >= 4 else Severity.MEDIUM
        findings.append(
            Finding(
                finding_id=f"tocluster-{sig}",
                kind=FindingKind.TIMEOUT_CLUSTER,
                severity=sev,
                title=f"{len(members)} TIMEOUT runs on config '{config_id}'",
                summary=(
                    f"config '{config_id}' timed out on {len(members)} run(s) across "
                    f"{len(benches)} benchmark(s). No conclusion was reached (NOT a pass). "
                    "Budget/engine fit is a shared suspect (HEURISTIC)."
                ),
                member_run_ids=[m.run_id for m in members],
                benchmark_ids=benches,
                config_ids=[config_id],
                evidence={
                    "config_id": config_id,
                    "n_members": len(members),
                    "n_benchmarks": len(benches),
                },
                priority_score=float(len(members)) * 2.5,
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# 3. Duplicate / near-duplicate jobs (signature hashing)
# --------------------------------------------------------------------------- #
def duplicate_jobs(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Detect runs with identical inputs (same design/property/config/catalog).

    These are redundant work when they share a seed too (exact duplicate) or a
    resource-waste candidate when they differ only by seed (near-duplicate). We
    hash the signature fields. Exact duplicates (same seed) are flagged higher.
    """
    buckets: dict[tuple[str, ...], list[RunRecord]] = defaultdict(list)
    for r in records:
        buckets[r.signature_fields].append(r)

    findings: list[Finding] = []
    for fields, members in buckets.items():
        if len(members) < th.min_duplicate_group:
            continue
        sig = _signature_hash(fields)
        seeds = Counter(m.seed for m in members)
        exact_dupes = sum(c for c in seeds.values() if c > 1)
        near = len(members) - len(seeds)  # extra runs beyond one-per-seed
        benches = sorted({m.benchmark_id for m in members})
        configs = sorted({m.config_id for m in members})
        # Exact duplicates (repeated seed) are pure redundancy -> higher severity.
        if exact_dupes > 0:
            sev = Severity.MEDIUM
            kind_note = f"{exact_dupes} exact duplicate run(s) (repeated seed)"
        else:
            sev = Severity.LOW
            kind_note = f"{len(members)} runs differing only by seed"
        findings.append(
            Finding(
                finding_id=f"dup-{sig}",
                kind=FindingKind.DUPLICATE_JOBS,
                severity=sev,
                title=f"Duplicate inputs: {kind_note}",
                summary=(
                    f"{len(members)} runs share identical inputs "
                    f"(design {fields[0][:8]}, property {fields[1][:8]}, config {fields[2]}). "
                    f"{kind_note}. Redundant compute is a de-duplication candidate (HEURISTIC)."
                ),
                member_run_ids=sorted(m.run_id for m in members),
                benchmark_ids=benches,
                config_ids=configs,
                evidence={
                    "signature": sig,
                    "n_members": len(members),
                    "n_distinct_seeds": len(seeds),
                    "exact_duplicate_runs": exact_dupes,
                    "near_duplicate_extra_runs": near,
                },
                priority_score=1.0 + 1.5 * exact_dupes + 0.5 * near,
            )
        )
    findings.sort(key=lambda f: f.finding_id)
    return findings


# --------------------------------------------------------------------------- #
# 4 & 5. Runtime / memory regression alerts
# --------------------------------------------------------------------------- #
_METRICS = {
    "wall_time_s": FindingKind.RUNTIME_REGRESSION,
    "peak_memory_mb": FindingKind.MEMORY_REGRESSION,
}


def _metric_values(records: Sequence[RunRecord], metric: str) -> list[float]:
    return [float(getattr(r, metric)) for r in records]


def regression_alerts(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Flag the latest run of a job whose metric regressed vs its own baseline.

    Baseline = all-but-latest runs of the same ``job_key``. The latest run is
    compared with robust-z (median/MAD) AND a min-ratio gate so we only fire on
    changes that are both statistically large and materially large.

    Only runs that reached a *conclusion* are used for the runtime baseline, so a
    timeout (which just hits the budget ceiling) does not poison the runtime
    baseline. Memory uses all runs since memory is meaningful even on a timeout.
    """
    findings: list[Finding] = []
    jobs = _by_job(records)

    for job_key, runs in sorted(jobs.items()):
        if len(runs) < th.min_baseline_runs + 1:
            continue
        latest = runs[-1]
        baseline_runs = runs[:-1]

        for metric, kind in _METRICS.items():
            if metric == "wall_time_s":
                base_pool = [r for r in baseline_runs if r.status.is_conclusive]
                if not latest.status.is_conclusive:
                    continue  # do not compare a timeout's wall against solve times
            else:
                base_pool = list(baseline_runs)
            if len(base_pool) < th.min_baseline_runs:
                continue

            base_vals = _metric_values(base_pool, metric)
            base = stats.baseline_stats(base_vals)
            latest_val = float(getattr(latest, metric))

            rz = stats.robust_z(latest_val, base)
            zc = stats.z_score(latest_val, base)
            ratio = latest_val / base.median if base.median > 0 else float("inf")

            if rz >= th.regression_robust_z and ratio >= th.regression_min_ratio:
                findings.append(
                    _regression_finding(
                        job_key, metric, kind, latest, latest_val, base, zc, rz, ratio
                    )
                )
    return findings


def _regression_finding(
    job_key: str,
    metric: str,
    kind: FindingKind,
    latest: RunRecord,
    latest_val: float,
    base: BaselineStats,
    zc: float,
    rz: float,
    ratio: float,
) -> Finding:
    ev = RegressionEvidence(
        job_key=job_key,
        metric=metric,
        latest_run_id=latest.run_id,
        latest_value=latest_val,
        baseline=base,
        z_score=zc,
        robust_z=rz,
        ratio_to_median=ratio,
    )
    sev = Severity.HIGH if ratio >= 3.0 else Severity.MEDIUM
    label = "runtime" if metric == "wall_time_s" else "memory"
    unit = "s" if metric == "wall_time_s" else "MB"
    return Finding(
        finding_id=f"reg-{metric}-{job_key}",
        kind=kind,
        severity=sev,
        title=f"{label} regression on {job_key}: {ratio:.1f}x baseline median",
        summary=(
            f"Latest run {latest.run_id} of {job_key} used {latest_val:.1f}{unit}, "
            f"vs baseline median {base.median:.1f}{unit} over n={base.n} runs "
            f"(robust_z={rz:.1f}, ratio={ratio:.1f}x). Correlation only, not a root cause "
            "(HEURISTIC)."
        ),
        member_run_ids=[latest.run_id],
        benchmark_ids=[latest.benchmark_id],
        config_ids=[latest.config_id],
        evidence=ev.model_dump(),
        priority_score=min(rz, 100.0) + ratio,
    )


# --------------------------------------------------------------------------- #
# 6. Configuration-sensitivity summaries
# --------------------------------------------------------------------------- #
def config_sensitivity(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Summarize how each benchmark's outcome/runtime varies across configs.

    A benchmark that only some configs can solve, or whose runtime spreads widely
    across configs, is configuration-sensitive: config choice matters and should
    be reviewed. This is descriptive, not a recommendation to change any config.
    """
    findings: list[Finding] = []
    for bench_id, runs in sorted(_by_benchmark(records).items()):
        by_config: dict[str, list[RunRecord]] = defaultdict(list)
        for r in runs:
            by_config[r.config_id].append(r)
        if len(by_config) < 2:
            continue

        per_config_median_wall: dict[str, float] = {}
        solved_flags: dict[str, bool] = {}
        terminal_statuses: set[str] = set()
        for cfg, cruns in by_config.items():
            conclusive = [c for c in cruns if c.status.is_conclusive]
            if conclusive:
                per_config_median_wall[cfg] = stats.median(
                    [c.wall_time_s for c in conclusive]
                )
            solved_flags[cfg] = any(c.status.is_success for c in cruns)
            for c in cruns:
                terminal_statuses.add(c.status.value)

        best_cfg = worst_cfg = None
        best_med = worst_med = None
        spread = None
        if per_config_median_wall:
            best_cfg = min(per_config_median_wall, key=lambda k: per_config_median_wall[k])
            worst_cfg = max(per_config_median_wall, key=lambda k: per_config_median_wall[k])
            best_med = per_config_median_wall[best_cfg]
            worst_med = per_config_median_wall[worst_cfg]
            spread = worst_med / best_med if best_med > 0 else None

        solved_some = any(solved_flags.values())
        solved_all = all(solved_flags.values())

        ev = ConfigSensitivityEvidence(
            benchmark_id=bench_id,
            n_configs=len(by_config),
            distinct_terminal_statuses=sorted(
                (s for s in _status_enum(terminal_statuses)), key=lambda s: s.value
            ),
            best_config_id=best_cfg,
            worst_config_id=worst_cfg,
            best_median_wall_s=best_med,
            worst_median_wall_s=worst_med,
            wall_spread_ratio=spread,
            solved_by_some_config=solved_some,
            solved_by_all_configs=solved_all,
        )

        outcome_sensitive = solved_some and not solved_all
        runtime_sensitive = spread is not None and spread >= th.config_spread_ratio
        if not (outcome_sensitive or runtime_sensitive):
            continue

        if outcome_sensitive:
            sev = Severity.HIGH
            reason = "solved by some configs but not others"
        else:
            sev = Severity.MEDIUM
            reason = f"runtime spreads {spread:.1f}x across configs"
        findings.append(
            Finding(
                finding_id=f"configsens-{bench_id}",
                kind=FindingKind.CONFIG_SENSITIVITY,
                severity=sev,
                title=f"{bench_id} is configuration-sensitive: {reason}",
                summary=(
                    f"Benchmark {bench_id} run under {len(by_config)} configs is "
                    f"configuration-sensitive ({reason}). Config choice materially affects "
                    "the result; review before trusting a single config (HEURISTIC)."
                ),
                member_run_ids=sorted(r.run_id for r in runs),
                benchmark_ids=[bench_id],
                config_ids=sorted(by_config.keys()),
                evidence=ev.model_dump(),
                priority_score=(5.0 if outcome_sensitive else 0.0) + (spread or 1.0),
            )
        )
    return findings


def _status_enum(values: set[str]):
    from .models import RunStatus

    return [RunStatus(v) for v in values]


# --------------------------------------------------------------------------- #
# 7. Reproducibility / flakiness warnings
# --------------------------------------------------------------------------- #
def reproducibility_warnings(records: Sequence[RunRecord], th: Thresholds) -> list[Finding]:
    """Flag logical jobs whose repeated runs disagree (flaky) or vary wildly.

    A job whose repeats produce different *conclusive* verdicts (PASS vs FAIL) is
    a serious reproducibility problem. A job that flips between conclusive and
    non-conclusive, or whose runtime coefficient-of-variation is high, is a
    weaker warning. Flakiness is computed per ``job_key`` over its repeats.
    """
    findings: list[Finding] = []
    for job_key, runs in sorted(_by_job(records).items()):
        if len(runs) < 2:
            continue
        statuses = [r.status for r in runs]
        counts = Counter(s.value for s in statuses)
        distinct = sorted(set(statuses), key=lambda s: s.value)
        if len(distinct) < 2:
            continue  # perfectly reproducible outcome

        pass_c = counts.get("PASS", 0)
        fail_c = counts.get("FAIL", 0)
        noncon = sum(counts.get(k, 0) for k in ("TIMEOUT", "ERROR", "INCONCLUSIVE"))

        flips = sum(1 for a, b in zip(statuses, statuses[1:], strict=False) if a is not b)
        flip_rate = flips / (len(statuses) - 1)
        cov = stats.coefficient_of_variation([r.wall_time_s for r in runs])

        ev = ReproEvidence(
            job_key=job_key,
            n_runs=len(runs),
            distinct_statuses=distinct,
            status_counts=dict(counts),
            pass_count=pass_c,
            fail_count=fail_c,
            nonconclusive_count=noncon,
            flip_rate=flip_rate,
            coefficient_of_variation=cov,
        )

        # PASS<->FAIL disagreement is the worst: a conclusive verdict is unstable.
        if pass_c > 0 and fail_c > 0:
            sev = Severity.HIGH
            reason = f"conflicting verdicts (PASS x{pass_c}, FAIL x{fail_c})"
            score = 10.0 + flip_rate * 5.0
        else:
            sev = Severity.MEDIUM
            reason = f"unstable status across repeats ({dict(counts)})"
            score = 5.0 + flip_rate * 3.0

        findings.append(
            Finding(
                finding_id=f"repro-{job_key}",
                kind=FindingKind.REPRODUCIBILITY_WARNING,
                severity=sev,
                title=f"Flaky job {job_key}: {reason}",
                summary=(
                    f"Job {job_key} produced {len(distinct)} distinct statuses over "
                    f"{len(runs)} repeats ({reason}; flip_rate={flip_rate:.2f}). "
                    "Non-reproducible results block trust in any single run (HEURISTIC)."
                ),
                member_run_ids=[r.run_id for r in runs],
                benchmark_ids=sorted({r.benchmark_id for r in runs}),
                config_ids=sorted({r.config_id for r in runs}),
                evidence=ev.model_dump(),
                priority_score=score,
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# Orchestration: run every analysis + build the prioritized queue
# --------------------------------------------------------------------------- #
_NEXT_STEP = {
    FindingKind.FAILURE_CLUSTER: (
        "Open one representative failing run; confirm the shared property/RC is one "
        "root cause before fixing."
    ),
    FindingKind.TIMEOUT_CLUSTER: (
        "Review the config's budget/engine fit for these benchmarks; a higher timeout "
        "tier or different engine may be warranted."
    ),
    FindingKind.DUPLICATE_JOBS: (
        "Confirm the duplicate inputs are intentional; if not, de-duplicate to reclaim compute."
    ),
    FindingKind.RUNTIME_REGRESSION: (
        "Compare the latest run's tool/version and inputs against the baseline; bisect the change."
    ),
    FindingKind.MEMORY_REGRESSION: (
        "Inspect peak-memory drivers (COI/depth) for the latest run vs baseline; check "
        "memory-cap headroom."
    ),
    FindingKind.CONFIG_SENSITIVITY: (
        "Review why configs disagree; pick and document a defensible config, do not "
        "auto-change budgets."
    ),
    FindingKind.REPRODUCIBILITY_WARNING: (
        "Reproduce the job with fixed seed and environment; a flaky verdict must be "
        "resolved before signoff."
    ),
}


def analyze(records: Sequence[RunRecord], thresholds: Thresholds | None = None) -> RegressionReport:
    """Run all deterministic analyses and assemble the full report."""
    th = thresholds or Thresholds()

    findings: list[Finding] = []
    findings += failure_clusters(records, th)
    findings += timeout_clusters(records, th)
    findings += duplicate_jobs(records, th)
    findings += regression_alerts(records, th)
    findings += config_sensitivity(records, th)
    findings += reproducibility_warnings(records, th)

    # Deterministic global ordering: severity desc, priority desc, id asc.
    findings.sort(
        key=lambda f: (-severity_rank(f.severity), -f.priority_score, f.finding_id)
    )

    queue = [
        InvestigationItem(
            rank=i + 1,
            finding_id=f.finding_id,
            kind=f.kind,
            severity=f.severity,
            priority_score=f.priority_score,
            title=f.title,
            recommended_next_step=_NEXT_STEP[f.kind],
        )
        for i, f in enumerate(findings)
    ]

    status_totals = Counter(r.status.value for r in records)
    jobs = _by_job(records)
    benchmarks = {r.benchmark_id for r in records}

    return RegressionReport(
        n_records=len(records),
        n_jobs=len(jobs),
        n_benchmarks=len(benchmarks),
        status_totals=dict(status_totals),
        findings=findings,
        investigation_queue=queue,
    )
