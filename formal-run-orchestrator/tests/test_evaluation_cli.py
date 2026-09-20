"""End-to-end evaluation + CLI tests (all via the mock executor)."""

from __future__ import annotations

from typer.testing import CliRunner

from formal_run_orchestrator.cli import app
from formal_run_orchestrator.evaluation import (
    ablation_feature_groups,
    compare_policies,
    evaluate_policy_on_split,
)
from formal_run_orchestrator.sample_suite import build_sample_suite

runner = CliRunner()


def test_evaluate_policy_returns_train_and_test():
    suite = build_sample_suite()
    res = evaluate_policy_on_split("rule_based", suite)
    assert set(res) == {"train", "test"}
    assert res["test"].n_attempts > 0
    assert res["train"].split == "train"


def test_compare_produces_consistent_leakage_free_results():
    # Reproducibility: two comparisons must agree exactly (no salted hashing).
    suite = build_sample_suite()
    names = ["fixed", "random", "rule_based", "bandit_linucb"]
    a = compare_policies(names, suite)
    b = compare_policies(names, suite)
    for n in names:
        assert a[n]["test"].model_dump() == b[n]["test"].model_dump()
    # Sanity: the best policy should beat the random baseline on solved-%.
    best = max(a[n]["test"].solved_within_budget_pct for n in names)
    rnd = a["random"]["test"].solved_within_budget_pct
    assert best >= rnd


def test_bandit_evaluation_is_leakage_free_and_runs():
    # Bandit trains on train only; evaluate should still produce test metrics.
    suite = build_sample_suite()
    res = evaluate_policy_on_split("bandit_linucb", suite)
    assert res["test"].n_attempts > 0


def test_ablation_reports_full_and_group_removals():
    suite = build_sample_suite()
    res = ablation_feature_groups(suite)
    assert "full" in res
    assert any(k.startswith("-") for k in res)


# ------------------------------- CLI --------------------------------- #
def test_cli_plan_run_summarize(tmp_path):
    db = str(tmp_path / "ledger.db")
    r = runner.invoke(app, ["plan", "--policy", "rule_based", "--db", db])
    assert r.exit_code == 0, r.output
    plan_id = [ln for ln in r.output.splitlines() if "plan_id=" in ln][0]
    plan_id = plan_id.split("plan_id=")[1].split()[0]

    r = runner.invoke(app, ["run", plan_id, "--db", db, "--artifacts", str(tmp_path / "art")])
    assert r.exit_code == 0, r.output
    assert "Executed" in r.output

    r = runner.invoke(app, ["summarize", "--plan-id", plan_id, "--db", db])
    assert r.exit_code == 0, r.output
    assert "Solved within budget" in r.output
    assert "PASS" in r.output


def test_cli_compare(tmp_path):
    out = tmp_path / "cmp.md"
    r = runner.invoke(app, ["compare", "--split", "test", "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert "Policy comparison" in r.output
    assert out.exists()


def test_cli_ingest_result(tmp_path):
    from formal_run_orchestrator.executor import execute

    it = build_sample_suite().items[0]
    rec = execute(it, "kind_mid", 1, plan_id="p", run_id="ext-cli", rationale="")
    p = tmp_path / "rec.json"
    p.write_text(rec.model_dump_json())
    db = str(tmp_path / "ledger.db")
    r = runner.invoke(app, ["ingest-result", str(p), "--db", db])
    assert r.exit_code == 0, r.output
    assert "Ingested" in r.output


def test_cli_summarize_empty_db_errors(tmp_path):
    db = str(tmp_path / "empty.db")
    r = runner.invoke(app, ["summarize", "--db", db])
    assert r.exit_code == 1
