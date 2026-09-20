"""Planner + policy tests."""

from __future__ import annotations

from formal_run_orchestrator.catalog import is_valid_config
from formal_run_orchestrator.planner import plan_experiment
from formal_run_orchestrator.policies import available_policies, get_policy
from formal_run_orchestrator.sample_suite import build_sample_suite


def test_planner_is_deterministic_and_idempotent():
    suite = build_sample_suite()
    pol = get_policy("rule_based")
    p1 = plan_experiment(suite, pol)
    p2 = plan_experiment(suite, pol)
    assert p1.plan_id == p2.plan_id
    assert [r.config_id for r in p1.planned_runs] == [r.config_id for r in p2.planned_runs]
    assert len(p1.planned_runs) == len(suite.items)


def test_all_policies_choose_only_catalog_configs():
    suite = build_sample_suite()
    for name in available_policies():
        pol = get_policy(name)
        for item in suite.items:
            choice = pol.choose(item, seed=123)
            assert is_valid_config(choice.config_id), f"{name} chose {choice.config_id}"
            assert choice.rationale


def test_rule_based_prefers_bmc_for_expected_counterexamples():
    suite = build_sample_suite()
    pol = get_policy("rule_based")
    bug = next(i for i in suite.items if i.benchmark_id == "cnt_wrap_bug")
    choice = pol.choose(bug, seed=1)
    assert choice.config_id.startswith("bmc")


def test_rule_based_prefers_inductive_for_holding_properties():
    suite = build_sample_suite()
    pol = get_policy("rule_based")
    hold = next(i for i in suite.items if i.benchmark_id == "arb_no_starve")
    choice = pol.choose(hold, seed=1)
    assert choice.config_id.startswith(("pdr", "kind"))


def test_random_policy_is_seed_deterministic():
    suite = build_sample_suite()
    pol = get_policy("random")
    it = suite.items[0]
    assert pol.choose(it, 5).config_id == pol.choose(it, 5).config_id
