"""Tests for the statistical primitives."""

from __future__ import annotations

import math

from formal_regression_intelligence import stats


def test_mean_median_stdev():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert stats.mean(xs) == 2.5
    assert stats.median(xs) == 2.5
    assert stats.median([1.0, 2.0, 3.0]) == 2.0
    assert stats.sample_stdev([2.0, 2.0]) == 0.0
    assert math.isclose(stats.sample_stdev([1.0, 3.0]), math.sqrt(2.0))


def test_mad_robust():
    # median=3; abs deviations [2,1,0,1,2]; mad = median = 1
    assert stats.mad([1.0, 2.0, 3.0, 4.0, 5.0]) == 1.0


def test_baseline_stats():
    b = stats.baseline_stats([10.0, 10.0, 10.0, 40.0])
    assert b.n == 4
    assert b.median == 10.0
    assert b.maximum == 40.0
    assert b.minimum == 10.0


def test_z_and_robust_z_flag_outlier():
    b = stats.baseline_stats([10.0, 10.2, 9.8, 10.1])
    # A 60s value is a huge outlier vs a ~10s stable baseline.
    assert stats.robust_z(60.0, b) > 3.5
    assert stats.z_score(60.0, b) > 3.5


def test_zero_variance_baseline_does_not_divide_by_zero():
    b = stats.baseline_stats([5.0, 5.0, 5.0])
    assert stats.z_score(5.0, b) == 0.0
    assert stats.robust_z(5.0, b) == 0.0
    # A change against a perfectly-stable baseline yields a large sentinel.
    assert stats.robust_z(50.0, b) > 100.0


def test_coefficient_of_variation():
    assert stats.coefficient_of_variation([5.0]) is None
    assert stats.coefficient_of_variation([0.0, 0.0]) is None
    cov = stats.coefficient_of_variation([9.0, 11.0])
    assert cov is not None and cov > 0
