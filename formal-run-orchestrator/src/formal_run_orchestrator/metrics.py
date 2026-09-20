"""Metrics + summarize/compare aggregation.

Computes the report metrics required by the policy extension:
  * solved-within-budget %
  * PASS/FAIL/TIMEOUT/ERROR/INCONCLUSIVE counts
  * total CPU / wall time, peak memory
  * number of configuration attempts
  * per-design reward variance
  * 95% confidence interval on mean reward where sample size permits.

"Solved within budget" == the tool reached a conclusion (PASS or FAIL) within
budget. TIMEOUT/ERROR/INCONCLUSIVE are never counted as solved.
"""

from __future__ import annotations

import math
from collections import defaultdict

from .models import PolicyMetrics, RunRecord, StatusCounts
from .reward import reward


def status_counts(runs: list[RunRecord]) -> StatusCounts:
    c = StatusCounts()
    for r in runs:
        setattr(c, r.status.value, getattr(c, r.status.value) + 1)
    return c


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _ci95(xs: list[float]) -> tuple[float, float] | None:
    """Normal-approx 95% CI on the mean. Requires >= 3 samples."""
    n = len(xs)
    if n < 3:
        return None
    m = _mean(xs)
    sd = math.sqrt(_variance(xs))
    half = 1.96 * sd / math.sqrt(n)
    return (round(m - half, 4), round(m + half, 4))


def compute_metrics(
    runs: list[RunRecord], policy_name: str, split: str = "all"
) -> PolicyMetrics:
    """Aggregate a set of run records into PolicyMetrics."""
    counts = status_counts(runs)
    solved = counts.PASS + counts.FAIL
    n_attempts = len(runs)
    solved_pct = (100.0 * solved / n_attempts) if n_attempts else 0.0

    designs = {r.benchmark_id for r in runs}
    rewards = [reward(r) for r in runs]

    # Per-design reward: average reward over that design's attempts, then variance.
    by_design: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        by_design[r.benchmark_id].append(reward(r))
    per_design_mean = [_mean(v) for v in by_design.values()]

    return PolicyMetrics(
        policy_name=policy_name,
        split=split,
        n_designs=len(designs),
        n_attempts=n_attempts,
        status_counts=counts,
        solved_within_budget_pct=round(solved_pct, 2),
        total_cpu_time_s=round(sum(r.cpu_time_s for r in runs), 3),
        total_wall_time_s=round(sum(r.wall_time_s for r in runs), 3),
        peak_memory_mb=round(max((r.peak_memory_mb for r in runs), default=0.0), 1),
        mean_reward=round(_mean(rewards), 4),
        per_design_reward_variance=round(_variance(per_design_mean), 6),
        reward_ci95=_ci95(rewards),
    )
