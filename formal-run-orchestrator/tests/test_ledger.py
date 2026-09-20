"""Ledger data-access tests (in-memory SQLite + round-trip)."""

from __future__ import annotations

import json

from formal_run_orchestrator.executor import execute
from formal_run_orchestrator.ledger import Ledger
from formal_run_orchestrator.planner import plan_experiment
from formal_run_orchestrator.policies import get_policy
from formal_run_orchestrator.sample_suite import build_sample_suite


def test_suite_plan_run_roundtrip():
    suite = build_sample_suite()
    plan = plan_experiment(suite, get_policy("rule_based"))
    with Ledger(":memory:") as led:
        led.save_suite(suite)
        led.save_plan(plan)
        item = suite.items[0]
        pr = plan.planned_runs[0]
        rec = execute(item, pr.config_id, pr.seed, plan_id=plan.plan_id,
                      run_id=pr.plan_run_id, rationale=pr.rationale)
        led.save_run(rec)

        assert led.get_suite(suite.suite_id).suite_id == suite.suite_id
        assert led.get_plan(plan.plan_id).plan_id == plan.plan_id
        got = led.get_run(rec.run_id)
        assert got is not None
        assert got.model_dump() == rec.model_dump()
        assert len(led.runs_for_plan(plan.plan_id)) == 1


def test_ingest_result_validates(tmp_path):
    suite = build_sample_suite()
    plan = plan_experiment(suite, get_policy("fixed"))
    item = suite.items[0]
    pr = plan.planned_runs[0]
    rec = execute(item, pr.config_id, pr.seed, plan_id=plan.plan_id,
                  run_id="external-1", rationale="ext")
    p = tmp_path / "rec.json"
    p.write_text(rec.model_dump_json())

    with Ledger(":memory:") as led:
        ingested = led.ingest_result_json(p)
        assert ingested.run_id == "external-1"
        assert led.get_run("external-1") is not None


def test_ingest_rejects_malformed(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"run_id": "x"}))  # missing required fields
    with Ledger(":memory:") as led:
        try:
            led.ingest_result_json(p)
            raise AssertionError("expected validation failure")
        except Exception:  # pydantic ValidationError
            pass
