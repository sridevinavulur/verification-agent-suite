"""Tests for the robust statistics core."""

from __future__ import annotations

import math

from perf_regression_agent import statistics as st
from perf_regression_agent.models import MetricName


def test_percentile_linear_interpolation():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert math.isclose(st._percentile(vals, 50.0), 2.5)
    assert math.isclose(st._percentile(vals, 25.0), 1.75)
    assert math.isclose(st._percentile(vals, 75.0), 3.25)


def test_reject_outliers_flags_wild_point():
    vals = [100.0, 101.0, 99.0, 100.5, 300.0]
    kept, out = st.reject_outliers(vals)
    assert 300.0 in out
    assert 300.0 not in kept
    assert len(kept) == 4


def test_reject_outliers_keeps_clean_data():
    vals = [10.0, 10.1, 9.9, 10.05, 9.95]
    kept, out = st.reject_outliers(vals)
    assert out == []
    assert len(kept) == 5


def test_reject_outliers_too_few_samples_keeps_all():
    vals = [1.0, 100.0, 2.0]
    kept, out = st.reject_outliers(vals)
    assert out == []
    assert kept == vals


def test_summarize_basic_stats():
    vals = [10.0, 12.0, 11.0, 9.0, 13.0]
    s = st.summarize(MetricName.LATENCY_NS, vals)
    assert s.n == 5
    assert math.isclose(s.mean, 11.0)
    assert s.stdev > 0
    assert s.ci95_low < s.mean < s.ci95_high
    assert s.cv > 0


def test_summarize_rejects_outlier_from_mean():
    clean = [100.0, 101.0, 99.0, 100.5, 99.5]
    dirty = clean + [500.0]
    s = st.summarize(MetricName.PEAK_MEMORY_MB, dirty)
    # Mean should be near 100, not dragged toward 500.
    assert abs(s.mean - 100.0) < 2.0
    assert 500.0 in s.outliers


def test_robust_z_change_zero_when_no_shift():
    vals = [50.0, 51.0, 49.0, 50.5, 49.5]
    s = st.summarize(MetricName.THROUGHPUT_MOPS, vals)
    z = st.robust_z_change(s.mean, s, s.kept)
    assert abs(z) < 1.0


def test_robust_z_change_large_on_real_shift():
    base = [100.0, 101.0, 99.0, 100.5, 99.5]
    s = st.summarize(MetricName.SIM_RUNTIME_S, base)
    z = st.robust_z_change(135.0, s, s.kept)
    assert z > 5.0
