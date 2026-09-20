"""Export JSON Schema for the core Pydantic contracts into schemas/."""

from __future__ import annotations

import json
from pathlib import Path

from formal_run_orchestrator.models import (
    BenchmarkSuite,
    ExperimentPlan,
    PolicyMetrics,
    RunRecord,
    SolverConfig,
)

OUT = Path(__file__).resolve().parent.parent / "schemas"

MODELS = {
    "benchmark_suite.schema.json": BenchmarkSuite,
    "solver_config.schema.json": SolverConfig,
    "experiment_plan.schema.json": ExperimentPlan,
    "run_record.schema.json": RunRecord,
    "policy_metrics.schema.json": PolicyMetrics,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, model in MODELS.items():
        (OUT / fname).write_text(json.dumps(model.model_json_schema(), indent=2))
        print(f"wrote schemas/{fname}")


if __name__ == "__main__":
    main()
