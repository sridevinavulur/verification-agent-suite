"""Deterministic experiment planner.

Given a benchmark suite and a policy, produce an ExperimentPlan: one PlannedRun per
benchmark item, with the policy's chosen catalog config, a fixed seed, and a
rationale. Plan IDs and run IDs are deterministic functions of their inputs so
re-planning the same suite+policy is idempotent and reproducible.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .catalog import CATALOG_VERSION
from .models import BenchmarkSuite, ExperimentPlan, PlannedRun
from .policies import Policy


def _plan_id(suite_id: str, policy_name: str, base_seed: int) -> str:
    h = hashlib.sha256(f"{suite_id}|{policy_name}|{base_seed}|{CATALOG_VERSION}".encode())
    return f"plan-{policy_name}-{h.hexdigest()[:10]}"


def _run_id(plan_id: str, benchmark_id: str) -> str:
    h = hashlib.sha256(f"{plan_id}|{benchmark_id}".encode())
    return f"run-{h.hexdigest()[:12]}"


def plan_experiment(
    suite: BenchmarkSuite,
    policy: Policy,
    *,
    base_seed: int = 1234,
    created_at: datetime | None = None,
) -> ExperimentPlan:
    """Build a deterministic plan. One planned run per item.

    The per-run seed is derived deterministically from the base seed and the
    benchmark id, so runs are reproducible yet distinct.
    """
    plan_id = _plan_id(suite.suite_id, policy.name, base_seed)
    created = created_at or datetime.now(UTC)

    planned: list[PlannedRun] = []
    for item in suite.items:
        seed = int(
            hashlib.sha256(f"{base_seed}|{item.benchmark_id}".encode()).hexdigest()[:8], 16
        )
        choice = policy.choose(item, seed)
        planned.append(
            PlannedRun(
                plan_run_id=_run_id(plan_id, item.benchmark_id),
                benchmark_id=item.benchmark_id,
                config_id=choice.config_id,
                seed=seed,
                rationale=choice.rationale,
                policy_name=policy.name,
            )
        )

    return ExperimentPlan(
        plan_id=plan_id,
        suite_id=suite.suite_id,
        catalog_version=CATALOG_VERSION,
        policy_name=policy.name,
        created_at=created,
        planned_runs=planned,
    )
