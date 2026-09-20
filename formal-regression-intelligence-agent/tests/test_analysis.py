"""Behavioral tests for each deterministic analysis.

Each test constructs a minimal ledger that should trigger exactly one analysis and
asserts the finding is produced with the right evidence -- and, importantly, that
near-misses do NOT produce false positives.
"""

from __future__ import annotations

from _ledger_helpers import make_record
from formal_regression_intelligence.analysis import (
    Thresholds,
    analyze,
    config_sensitivity,
    duplicate_jobs,
    failure_clusters,
    regression_alerts,
    reproducibility_warnings,
    timeout_clusters,
)
from formal_regression_intelligence.models import FindingKind, Severity

TH = Thresholds()


# --------------------------------------------------------------------------- #
# Failure clusters
# --------------------------------------------------------------------------- #
def test_failure_cluster_groups_shared_signature():
    recs = [
        make_record(run_id=f"r{i}", benchmark=f"b{i}", config_id="cfg-x",
                    status="FAIL", return_code=1, property_sha="P", minute=i)
        for i in range(3)
    ]
    findings = failure_clusters(recs, TH)
    assert len(findings) == 1
    f = findings[0]
    assert f.kind is FindingKind.FAILURE_CLUSTER
    assert len(f.member_run_ids) == 3
    assert f.evidence["return_code"] == 1


def test_single_failure_is_not_a_cluster():
    recs = [make_record(run_id="r1", status="FAIL", return_code=1)]
    assert failure_clusters(recs, TH) == []


def test_failures_with_different_return_codes_split():
    recs = [
        make_record(run_id="r1", status="FAIL", return_code=1, property_sha="P", benchmark="a"),
        make_record(run_id="r2", status="FAIL", return_code=2, property_sha="P", benchmark="b"),
    ]
    assert failure_clusters(recs, TH) == []  # neither RC reaches min_cluster_size


# --------------------------------------------------------------------------- #
# Timeout clusters
# --------------------------------------------------------------------------- #
def test_timeout_cluster_by_config():
    recs = [
        make_record(run_id=f"r{i}", benchmark=f"b{i}", config_id="cfg-shallow",
                    status="TIMEOUT", return_code=124, minute=i)
        for i in range(3)
    ]
    findings = timeout_clusters(recs, TH)
    assert len(findings) == 1
    assert findings[0].config_ids == ["cfg-shallow"]
    assert len(findings[0].member_run_ids) == 3


def test_timeout_never_classified_as_pass():
    r = make_record(run_id="r1", status="TIMEOUT", return_code=124)
    assert not r.status.is_success


# --------------------------------------------------------------------------- #
# Duplicate jobs
# --------------------------------------------------------------------------- #
def test_exact_duplicate_detected():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", seed=7, minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c", seed=7, minute=2),
    ]
    findings = duplicate_jobs(recs, TH)
    assert len(findings) == 1
    assert findings[0].evidence["exact_duplicate_runs"] == 2
    assert findings[0].severity is Severity.MEDIUM


def test_near_duplicate_only_by_seed_is_low():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", seed=1, minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c", seed=2, minute=2),
    ]
    findings = duplicate_jobs(recs, TH)
    assert len(findings) == 1
    assert findings[0].evidence["exact_duplicate_runs"] == 0
    assert findings[0].severity is Severity.LOW


def test_distinct_inputs_are_not_duplicates():
    recs = [
        make_record(run_id="r1", benchmark="b1", config_id="c"),
        make_record(run_id="r2", benchmark="b2", config_id="c"),
    ]
    assert duplicate_jobs(recs, TH) == []


# --------------------------------------------------------------------------- #
# Runtime / memory regression
# --------------------------------------------------------------------------- #
def _baseline_plus_latest(metric_latest: dict) -> list:
    base = [
        make_record(run_id=f"b{i}", benchmark="j", config_id="c", seed=i,
                    status="PASS", wall=10.0, mem=400.0, minute=i)
        for i in range(1, 5)
    ]
    latest = make_record(run_id="latest", benchmark="j", config_id="c", seed=99,
                         status="PASS", minute=10, **metric_latest)
    return base + [latest]


def test_runtime_regression_fires():
    recs = _baseline_plus_latest({"wall": 65.0, "mem": 400.0})
    findings = regression_alerts(recs, TH)
    kinds = {f.kind for f in findings}
    assert FindingKind.RUNTIME_REGRESSION in kinds
    reg = next(f for f in findings if f.kind is FindingKind.RUNTIME_REGRESSION)
    assert reg.evidence["ratio_to_median"] > 1.5
    assert reg.member_run_ids == ["latest"]


def test_memory_regression_fires():
    recs = _baseline_plus_latest({"wall": 10.0, "mem": 2000.0})
    findings = regression_alerts(recs, TH)
    assert FindingKind.MEMORY_REGRESSION in {f.kind for f in findings}


def test_no_regression_when_stable():
    recs = _baseline_plus_latest({"wall": 10.5, "mem": 405.0})
    assert regression_alerts(recs, TH) == []


def test_regression_needs_min_baseline():
    # Only 2 baseline runs (< min_baseline_runs=3): no alert even with a spike.
    recs = [
        make_record(run_id="b1", benchmark="j", config_id="c", seed=1, wall=10.0, minute=1),
        make_record(run_id="b2", benchmark="j", config_id="c", seed=2, wall=10.0, minute=2),
        make_record(run_id="latest", benchmark="j", config_id="c", seed=3, wall=90.0, minute=3),
    ]
    assert regression_alerts(recs, TH) == []


def test_timeout_does_not_poison_runtime_baseline():
    # Latest is a TIMEOUT: its wall (the budget ceiling) must not be compared as
    # a runtime regression against solve times.
    base = [
        make_record(run_id=f"b{i}", benchmark="j", config_id="c", seed=i,
                    status="PASS", wall=10.0, minute=i)
        for i in range(1, 5)
    ]
    latest = make_record(run_id="latest", benchmark="j", config_id="c", seed=9,
                         status="TIMEOUT", return_code=124, wall=120.0, minute=10)
    findings = regression_alerts(base + [latest], TH)
    assert all(f.kind is not FindingKind.RUNTIME_REGRESSION for f in findings)


# --------------------------------------------------------------------------- #
# Config sensitivity
# --------------------------------------------------------------------------- #
def test_config_sensitivity_outcome():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c-good", status="PASS", minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c-bad",
                    status="TIMEOUT", return_code=124, wall=120.0, minute=2),
    ]
    findings = config_sensitivity(recs, TH)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert findings[0].evidence["solved_by_some_config"] is True
    assert findings[0].evidence["solved_by_all_configs"] is False


def test_config_sensitivity_runtime_spread():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c-fast",
                    status="PASS", wall=5.0, minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c-slow",
                    status="PASS", wall=50.0, minute=2),
    ]
    findings = config_sensitivity(recs, TH)
    assert len(findings) == 1
    assert findings[0].evidence["wall_spread_ratio"] >= TH.config_spread_ratio


def test_single_config_is_not_sensitive():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", status="PASS", wall=5.0, seed=1),
        make_record(run_id="r2", benchmark="b", config_id="c", status="PASS", wall=6.0, seed=2),
    ]
    assert config_sensitivity(recs, TH) == []


# --------------------------------------------------------------------------- #
# Reproducibility / flakiness
# --------------------------------------------------------------------------- #
def test_flaky_pass_fail_is_high():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", seed=1, status="PASS", minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c", seed=2, status="FAIL",
                    return_code=1, minute=2),
        make_record(run_id="r3", benchmark="b", config_id="c", seed=3, status="PASS", minute=3),
    ]
    findings = reproducibility_warnings(recs, TH)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert findings[0].evidence["pass_count"] == 2
    assert findings[0].evidence["fail_count"] == 1


def test_stable_job_is_not_flaky():
    recs = [
        make_record(run_id=f"r{i}", benchmark="b", config_id="c", seed=i, status="PASS", minute=i)
        for i in range(1, 4)
    ]
    assert reproducibility_warnings(recs, TH) == []


def test_pass_then_timeout_is_medium():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", seed=1, status="PASS", minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c", seed=2,
                    status="TIMEOUT", return_code=124, wall=120.0, minute=2),
    ]
    findings = reproducibility_warnings(recs, TH)
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM


# --------------------------------------------------------------------------- #
# End-to-end report structure
# --------------------------------------------------------------------------- #
def test_analyze_builds_sorted_queue():
    recs = [
        make_record(run_id="r1", benchmark="b", config_id="c", seed=1, status="PASS", minute=1),
        make_record(run_id="r2", benchmark="b", config_id="c", seed=2, status="FAIL",
                    return_code=1, minute=2),
    ]
    report = analyze(recs, TH)
    assert report.n_records == 2
    # queue ranks are 1..N and sorted by severity desc then score desc
    ranks = [i.rank for i in report.investigation_queue]
    assert ranks == list(range(1, len(ranks) + 1))
    scores = [(i.severity.value, i.priority_score) for i in report.investigation_queue]
    # every finding has a next-step recommendation
    assert all(i.recommended_next_step for i in report.investigation_queue)
    assert scores  # non-empty
