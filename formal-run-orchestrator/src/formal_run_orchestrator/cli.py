"""Typer CLI for the Formal Run Orchestrator.

Commands: plan, run, ingest-result, summarize, compare (+ helpers: init-suite,
evaluate, ablate). Everything uses the MOCK executor; no real formal tool is invoked
and the orchestrator never modifies RTL/SVA/assumptions or claims proof/signoff.
"""

from __future__ import annotations

from pathlib import Path

import typer

from .catalog import CATALOG_VERSION, all_configs
from .evaluation import ablation_feature_groups, compare_policies, evaluate_policy_on_split
from .executor import execute
from .ledger import Ledger
from .metrics import compute_metrics
from .models import BenchmarkSuite
from .planner import plan_experiment
from .policies import available_policies, get_policy
from .report import render_ablation, render_comparison, render_summary
from .sample_suite import build_sample_suite

app = typer.Typer(
    add_completion=False,
    help=(
        "Formal Run Orchestrator (mock executor). Heuristic orchestration; "
        "formal-tool results remain authoritative. Never modifies RTL/SVA/assumptions "
        "and never claims proof/signoff."
    ),
)

DEFAULT_DB = "reports/ledger.db"


def _load_suite(suite_path: str | None) -> BenchmarkSuite:
    if suite_path is None:
        return build_sample_suite()
    return BenchmarkSuite.model_validate_json(Path(suite_path).read_text())


# --------------------------------------------------------------------------- #
@app.command("init-suite")
def init_suite(
    out: str = typer.Option("examples/benchmarks/sample_suite.json", help="Output path."),
) -> None:
    """Write the bundled public toy benchmark suite to a JSON file."""
    suite = build_sample_suite()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(suite.model_dump_json(indent=2))
    typer.echo(f"Wrote sample suite ({len(suite.items)} items) -> {out}")


@app.command("catalog")
def show_catalog() -> None:
    """Print the approved, versioned configuration catalog."""
    typer.echo(f"Catalog version: {CATALOG_VERSION}")
    for c in all_configs():
        typer.echo(
            f"  {c.config_id:<14} engine={c.engine.value:<13} depth={c.bmc_depth:<5} "
            f"timeout={c.timeout_s:<5}s mem={c.memory_cap_mb}MB "
            f"prep={c.preprocessing.value} part={c.partition_strategy.value}"
        )


@app.command("plan")
def plan_cmd(
    policy: str = typer.Option("rule_based", help=f"One of: {', '.join(available_policies())}"),
    suite: str | None = typer.Option(None, help="Suite JSON (default: bundled sample)."),
    db: str = typer.Option(DEFAULT_DB, help="SQLite ledger path."),
    base_seed: int = typer.Option(1234, help="Base seed for deterministic planning."),
    out: str | None = typer.Option(None, help="Also write the plan JSON here."),
) -> None:
    """Build a deterministic experiment plan and store it in the ledger."""
    suite_obj = _load_suite(suite)
    pol = get_policy(policy)
    plan = plan_experiment(suite_obj, pol, base_seed=base_seed)
    with Ledger(db) as ledger:
        ledger.save_suite(suite_obj)
        ledger.save_plan(plan)
    typer.echo(f"Planned {len(plan.planned_runs)} runs with policy '{policy}'.")
    typer.echo(f"plan_id={plan.plan_id}  (saved to {db})")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(plan.model_dump_json(indent=2))
        typer.echo(f"Plan JSON -> {out}")


@app.command("run")
def run_cmd(
    plan_id: str = typer.Argument(..., help="Plan ID from `plan`."),
    db: str = typer.Option(DEFAULT_DB, help="SQLite ledger path."),
    artifacts: str | None = typer.Option(
        "reports/artifacts", help="Directory for mock artifact logs."
    ),
) -> None:
    """Execute a stored plan with the MOCK executor and record full provenance."""
    with Ledger(db) as ledger:
        plan = ledger.get_plan(plan_id)
        if plan is None:
            typer.echo(f"ERROR: plan '{plan_id}' not found in {db}", err=True)
            raise typer.Exit(code=1)
        suite = ledger.get_suite(plan.suite_id)
        if suite is None:
            typer.echo(f"ERROR: suite '{plan.suite_id}' not found in {db}", err=True)
            raise typer.Exit(code=1)
        by_id = {i.benchmark_id: i for i in suite.items}
        n = 0
        for pr in plan.planned_runs:
            item = by_id[pr.benchmark_id]
            rec = execute(
                item,
                pr.config_id,
                pr.seed,
                plan_id=plan.plan_id,
                run_id=pr.plan_run_id,
                rationale=pr.rationale,
                artifact_dir=artifacts,
            )
            ledger.save_run(rec)
            n += 1
            typer.echo(f"  {rec.benchmark_id:<22} {rec.config_id:<14} -> {rec.status.value}")
    typer.echo(f"Executed {n} runs (mock). Records saved to {db}.")


@app.command("ingest-result")
def ingest_result_cmd(
    path: str = typer.Argument(..., help="RunRecord JSON produced externally."),
    db: str = typer.Option(DEFAULT_DB, help="SQLite ledger path."),
) -> None:
    """Validate and ingest an externally-produced RunRecord JSON into the ledger."""
    with Ledger(db) as ledger:
        rec = ledger.ingest_result_json(path)
    typer.echo(f"Ingested run {rec.run_id} status={rec.status.value} into {db}.")


@app.command("summarize")
def summarize_cmd(
    plan_id: str | None = typer.Option(None, help="Summarize one plan (default: all runs)."),
    db: str = typer.Option(DEFAULT_DB, help="SQLite ledger path."),
    out: str | None = typer.Option(None, help="Write Markdown report here."),
) -> None:
    """Summarize ledger runs into a status/resource/reward report."""
    with Ledger(db) as ledger:
        runs = ledger.runs_for_plan(plan_id) if plan_id else ledger.all_runs()
        policy_name = "mixed"
        if plan_id:
            plan = ledger.get_plan(plan_id)
            policy_name = plan.policy_name if plan else "unknown"
    if not runs:
        typer.echo("No runs found. Did you `plan` then `run`?", err=True)
        raise typer.Exit(code=1)
    metrics = compute_metrics(runs, policy_name, "all")
    md = render_summary(metrics)
    typer.echo(md)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(md)
        typer.echo(f"Report -> {out}")


@app.command("compare")
def compare_cmd(
    policies: str = typer.Option(
        "fixed,random,rule_based,bandit_linucb",
        help="Comma-separated policy names to compare.",
    ),
    suite: str | None = typer.Option(None, help="Suite JSON (default: bundled sample)."),
    split: str = typer.Option("test", help="Split to rank on: train|test."),
    test_fraction: float = typer.Option(0.4, help="Group-holdout test fraction."),
    out: str | None = typer.Option(None, help="Write Markdown comparison here."),
) -> None:
    """Offline, leakage-free comparison of policies on the sample suite (mock executor)."""
    suite_obj = _load_suite(suite)
    names = [p.strip() for p in policies.split(",") if p.strip()]
    results = compare_policies(names, suite_obj, test_fraction=test_fraction)
    md = render_comparison(results, split=split)
    typer.echo(md)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(md)
        typer.echo(f"Comparison -> {out}")


@app.command("evaluate")
def evaluate_cmd(
    policy: str = typer.Option("rule_based", help="Policy to evaluate."),
    suite: str | None = typer.Option(None, help="Suite JSON (default: bundled sample)."),
    test_fraction: float = typer.Option(0.4, help="Group-holdout test fraction."),
) -> None:
    """Evaluate one policy on train + held-out test splits (leakage-free)."""
    suite_obj = _load_suite(suite)
    res = evaluate_policy_on_split(policy, suite_obj, test_fraction=test_fraction)
    typer.echo(render_summary(res["train"]))
    typer.echo(render_summary(res["test"]))


@app.command("ablate")
def ablate_cmd(
    suite: str | None = typer.Option(None, help="Suite JSON (default: bundled sample)."),
    test_fraction: float = typer.Option(0.4, help="Group-holdout test fraction."),
    out: str | None = typer.Option(None, help="Write Markdown ablation here."),
) -> None:
    """Run the bandit feature-group ablation on the held-out test split."""
    suite_obj = _load_suite(suite)
    res = ablation_feature_groups(suite_obj, test_fraction=test_fraction)
    md = render_ablation(res)
    typer.echo(md)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(md)
        typer.echo(f"Ablation -> {out}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
