"""Deterministic statistics: robust outlier rejection and summary stats.

Pure standard-library implementation (no numpy) so the tool has zero heavy
runtime deps and produces identical, reproducible results everywhere.
"""

from __future__ import annotations

import math
from statistics import median as _median

from .models import MetricName, MetricStats

# Student's t 95% two-sided critical values for small samples (df = n-1).
# Falls back to the normal approximation (1.96) for df >= 30.
_T95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    25: 2.060,
    29: 2.045,
}

# Scale factor making MAD a consistent estimator of stdev for normal data.
_MAD_SCALE = 1.4826


def _t95(df: int) -> float:
    if df <= 0:
        return 0.0
    if df in _T95:
        return _T95[df]
    if df >= 30:
        return 1.96
    # nearest known key below df
    keys = sorted(k for k in _T95 if k <= df)
    return _T95[keys[-1]]


def mad(values: list[float], center: float | None = None) -> float:
    """Median absolute deviation (unscaled)."""
    if not values:
        return 0.0
    c = center if center is not None else _median(values)
    return _median([abs(v - c) for v in values])


def reject_outliers(
    values: list[float],
    *,
    iqr_k: float = 1.5,
    z_threshold: float = 3.5,
) -> tuple[list[float], list[float]]:
    """Robustly split ``values`` into (kept, outliers).

    Uses two complementary robust rules and rejects a point if *either* flags
    it:
      * Tukey IQR fence: outside [Q1 - k*IQR, Q3 + k*IQR]
      * Modified z-score (MAD-based, Iglewicz & Hoaglin): |0.6745*(x-med)/MAD|

    Robust methods are used instead of mean/stdev fences because the latter are
    themselves corrupted by the outliers we want to find. With <4 samples there
    is not enough data to reject anything, so all are kept.
    """
    if len(values) < 4:
        return list(values), []

    med = _median(values)
    m = mad(values, med)

    # Quartiles via linear interpolation (type-7 / numpy-default).
    q1 = _percentile(values, 25.0)
    q3 = _percentile(values, 75.0)
    iqr = q3 - q1
    lo = q1 - iqr_k * iqr
    hi = q3 + iqr_k * iqr

    kept: list[float] = []
    outliers: list[float] = []
    for v in values:
        is_iqr_out = v < lo or v > hi
        if m > 0:
            mz = abs(0.6745 * (v - med) / m)
            is_mz_out = mz > z_threshold
        else:
            is_mz_out = False
        if is_iqr_out or is_mz_out:
            outliers.append(v)
        else:
            kept.append(v)

    # Never reject everything; if the filter is too aggressive, keep all.
    if not kept:
        return list(values), []
    return kept, outliers


def _percentile(values: list[float], pct: float) -> float:
    """Type-7 linear-interpolation percentile (matches numpy default)."""
    if not values:
        raise ValueError("percentile of empty sequence")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (pct / 100.0) * (len(s) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return s[lo]
    frac = rank - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def summarize(
    metric: MetricName,
    raw_values: list[float],
    *,
    iqr_k: float = 1.5,
    z_threshold: float = 3.5,
) -> MetricStats:
    """Compute robust summary statistics after outlier rejection."""
    if not raw_values:
        raise ValueError("cannot summarize empty samples")

    kept, outliers = reject_outliers(
        raw_values, iqr_k=iqr_k, z_threshold=z_threshold
    )
    n = len(kept)
    mean = sum(kept) / n
    med = _median(kept)

    if n >= 2:
        var = sum((x - mean) ** 2 for x in kept) / (n - 1)
        stdev = math.sqrt(var)
    else:
        stdev = 0.0

    if n >= 2:
        se = stdev / math.sqrt(n)
        half = _t95(n - 1) * se
    else:
        half = 0.0

    cv = stdev / abs(mean) if mean != 0 else 0.0

    return MetricStats(
        metric=metric,
        n=n,
        mean=mean,
        stdev=stdev,
        median=med,
        ci95_low=mean - half,
        ci95_high=mean + half,
        cv=cv,
        kept=sorted(kept),
        outliers=sorted(outliers),
    )


def robust_z_change(candidate_mean: float, baseline_stats: MetricStats,
                    baseline_raw: list[float]) -> float:
    """Change of candidate mean expressed in baseline robust sigmas (MAD).

    Uses MAD-scaled sigma so a single noisy baseline sample cannot inflate the
    denominator and mask a real shift. Returns signed value (candidate - base).
    """
    med = baseline_stats.median
    m = mad(baseline_raw, med) * _MAD_SCALE
    if m <= 0:
        # Degenerate baseline spread: fall back to classic stdev if available.
        m = baseline_stats.stdev
    if m <= 0:
        return 0.0
    return (candidate_mean - med) / m
