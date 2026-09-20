"""Tests for leakage-free split, reward design, and metrics."""

from __future__ import annotations

from formal_run_orchestrator.executor import execute
from formal_run_orchestrator.metrics import compute_metrics, status_counts
from formal_run_orchestrator.models import RunStatus
from formal_run_orchestrator.reward import (
    P_INVALID_CONFIG,
    P_TIMEOUT,
    reward,
)
from formal_run_orchestrator.sample_suite import build_sample_suite
from formal_run_orchestrator.split import group_holdout_split


def _item(bid):
    return next(i for i in build_sample_suite().items if i.benchmark_id == bid)


def test_split_has_no_group_leakage():
    suite = build_sample_suite()
    sp = group_holdout_split(suite, test_fraction=0.4)
    assert set(sp.train_groups).isdisjoint(sp.test_groups)
    # every item is on exactly one side
    train_ids = {i.benchmark_id for i in sp.train}
    test_ids = {i.benchmark_id for i in sp.test}
    assert train_ids.isdisjoint(test_ids)
    assert len(train_ids) + len(test_ids) == len(suite.items)
    assert sp.train and sp.test


def test_split_is_stable_across_calls():
    suite = build_sample_suite()
    a = group_holdout_split(suite, 0.4)
    b = group_holdout_split(suite, 0.4)
    assert a.test_groups == b.test_groups


def test_reward_penalizes_timeout_more_than_solved():
    solved = execute(_item("cnt_no_overflow"), "kind_mid", 1, plan_id="p",
                     run_id="s", rationale="")
    assert solved.status is RunStatus.PASS
    assert reward(solved) > 0
    # a timeout reward is the fixed penalty
    timeout = execute(_item("alu_add_comm"), "bmc_shallow", 9, plan_id="p",
                      run_id="t", rationale="")
    if timeout.status is RunStatus.TIMEOUT:
        assert reward(timeout) == -P_TIMEOUT


def test_reward_worst_for_invalid_config():
    inv = execute(_item("cnt_no_overflow"), "nope", 1, plan_id="p", run_id="i",
                  rationale="")
    assert reward(inv) == -P_INVALID_CONFIG


def test_metrics_never_count_nonsolved_as_solved():
    suite = build_sample_suite()
    runs = []
    for i, it in enumerate(suite.items):
        runs.append(execute(it, "bmc_shallow", i, plan_id="p", run_id=f"r{i}",
                            rationale=""))
    m = compute_metrics(runs, "test", "all")
    c = m.status_counts
    solved = c.PASS + c.FAIL
    # pct is rounded to 2 dp in the model; allow rounding tolerance
    assert abs(m.solved_within_budget_pct - 100.0 * solved / c.total) < 0.01
    # solved excludes timeout/error/inconclusive
    assert m.n_attempts == len(suite.items)


def test_status_counts_total_matches():
    suite = build_sample_suite()
    runs = [execute(it, "kind_mid", 0, plan_id="p", run_id=f"x{i}", rationale="")
            for i, it in enumerate(suite.items)]
    c = status_counts(runs)
    assert c.total == len(runs)
