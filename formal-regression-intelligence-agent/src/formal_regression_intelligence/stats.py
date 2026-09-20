"""Deterministic statistical primitives.

Pure-Python, no numpy dependency, fully reproducible. These are the building
blocks for the runtime/memory regression baselines. We prefer *robust* statistics
(median / MAD) alongside the classic mean/stdev because formal-run telemetry is
heavy-tailed (a few timeouts dominate the mean) and z-scores against a
non-robust mean over-flag.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import BaselineStats

# 0.6745 = Phi^{-1}(0.75); scales MAD to be a consistent estimator of stdev for
# normal data, so robust_z is comparable in magnitude to a classic z-score.
_MAD_TO_SIGMA = 0.6744897501960817


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean of empty sequence")
    return sum(xs) / len(xs)


def median(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("median of empty sequence")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def sample_stdev(xs: Sequence[float]) -> float:
    """Sample standard deviation (n-1). Returns 0.0 for n < 2."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var)


def mad(xs: Sequence[float]) -> float:
    """Median absolute deviation about the median (raw, un-scaled)."""
    if not xs:
        raise ValueError("mad of empty sequence")
    med = median(xs)
    return median([abs(x - med) for x in xs])


def baseline_stats(xs: Sequence[float]) -> BaselineStats:
    """Compute the full robust baseline summary for a metric history."""
    if not xs:
        raise ValueError("baseline_stats of empty sequence")
    return BaselineStats(
        n=len(xs),
        mean=mean(xs),
        stdev=sample_stdev(xs),
        median=median(xs),
        mad=mad(xs),
        minimum=min(xs),
        maximum=max(xs),
    )


def z_score(value: float, base: BaselineStats) -> float:
    """Classic z = (value - mean) / stdev.

    If stdev is 0 (baseline perfectly stable) we return 0.0 when the value equals
    the mean, else a large sentinel so a real change is still flagged rather than
    dividing by zero.
    """
    if base.stdev == 0.0:
        return 0.0 if value == base.mean else math.copysign(1e9, value - base.mean)
    return (value - base.mean) / base.stdev


def robust_z(value: float, base: BaselineStats) -> float:
    """Robust z-score using median and scaled MAD.

    robust_z = 0.6745 * (value - median) / MAD.  Falls back to a mean/stdev-free
    sentinel when MAD is 0 (all baseline points identical).
    """
    scaled = base.mad / _MAD_TO_SIGMA if base.mad > 0 else 0.0
    if scaled == 0.0:
        return 0.0 if value == base.median else math.copysign(1e9, value - base.median)
    return (value - base.median) / scaled


def coefficient_of_variation(xs: Sequence[float]) -> float | None:
    """stdev / mean. None if mean is 0 or sequence too small."""
    if len(xs) < 2:
        return None
    m = mean(xs)
    if m == 0:
        return None
    return sample_stdev(xs) / m
