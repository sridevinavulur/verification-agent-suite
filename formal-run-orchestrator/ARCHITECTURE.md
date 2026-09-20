# Architecture

## Overview

```
                         +------------------+
   BenchmarkSuite  --->  |     Planner      |  ---> ExperimentPlan
   (public toy)          | (deterministic)  |       (PlannedRun[])
        ^                +---------+--------+
        |                          |
   Policy layer  <-----------------+  (chooses config_id from catalog)
   fixed/random/rule/bandit
                                   |
                                   v
   Catalog (finite,        +------------------+       +--------------+
   versioned) ---------->  |  Mock Executor   | --->  |  Classifier  | ---> RunStatus
                           | (pseudo-run)     |       | (safety-first)|
                           +---------+--------+       +--------------+
                                     |
                                     v
                            +------------------+
                            |  SQLite Ledger   |  <--- ingest-result (external JSON)
                            | (provenance)     |
                            +---------+--------+
                                      |
                     +----------------+----------------+
                     v                                 v
              summarize (metrics)               compare / evaluate / ablate
              -> Markdown report                (offline, leakage-free split)
```

## Components and typed contracts

| Module | Responsibility | Key types (in `models.py`) |
| --- | --- | --- |
| `catalog.py` | Finite, versioned config catalog; the only source of runnable configs. | `SolverConfig`, `CATALOG_VERSION` |
| `models.py` | All Pydantic v2 contracts + fixed enums. | `RunStatus`, `EngineFamily`, `BenchmarkSuite`, `BenchmarkItem`, `ExperimentPlan`, `PlannedRun`, `RunRecord`, `PolicyMetrics`, `ValidationStatus` |
| `planner.py` | Deterministic `(suite, policy) -> ExperimentPlan`. Idempotent IDs. | `ExperimentPlan`, `PlannedRun` |
| `policies/` | Config-selection policies. Choose only from the catalog. | `Policy`, `PolicyChoice` |
| `executor.py` | **Mock** execution worker; deterministic `RawResult` + provenance. | `RunRecord`, `RawResult` |
| `classifier.py` | Maps `RawResult` -> `RunStatus`. Safety-first precedence. | `RawResult`, `RunStatus` |
| `ledger.py` | SQLite data-access layer; durable provenance store; ingestion. | all persisted models |
| `split.py` | Group-level leakage-free train/test holdout. | `Split` |
| `reward.py` | Scalar reward (penalizes timeout/memory/invalid). | — |
| `metrics.py` | Aggregate runs -> `PolicyMetrics` (+CIs). | `PolicyMetrics`, `StatusCounts` |
| `evaluation.py` | Offline policy eval, comparison, ablation. | `PolicyMetrics` |
| `report.py` | Render metrics/comparison/ablation to Markdown. | — |
| `cli.py` | Typer CLI surface. | — |

## Deterministic vs heuristic layers (kept separate)

- **Deterministic / authoritative-facing:** the classifier's status mapping, the
  provenance schema and its validators, the ledger, and the leakage-free split. These
  encode hard rules (e.g. "never PASS a timeout").
- **Heuristic:** the planner's policy choices and the mock executor's cost model.
  These are explicitly labeled heuristic and are never presented as sound.

A real backend would replace only the *inside* of `executor.simulate`, emitting the
same `RawResult`; the classifier, ledger, provenance, and metrics are unchanged.

## Data flow contracts

- **plan:** `BenchmarkSuite` + `Policy` → `ExperimentPlan` (persisted).
- **run:** `ExperimentPlan` (+ suite) → `RunRecord[]` (persisted, one per item).
- **ingest-result:** external `RunRecord` JSON → validated → persisted.
- **summarize:** `RunRecord[]` → `PolicyMetrics` → Markdown.
- **compare/evaluate:** `BenchmarkSuite` → leakage-free `Split` → per-policy
  `PolicyMetrics` for `train` and `test`.

## Authority boundary

The orchestrator selects among **pre-approved** configurations and records results. It
**never** modifies RTL, SVA, or assumptions; never changes proof scope or budgets;
never claims proof/signoff; never hides failed/inconclusive runs. Those actions are
gated on human approval (`docs/HUMAN_GATE.md`).

## Reproducibility

Every stage is deterministic given its inputs and seed. Plan IDs, run IDs, per-run
seeds, the split assignment, and the mock results are all pure functions of their
inputs, so a fresh clone reproduces the bundled reports exactly (modulo host metadata
fields like hostname and timestamps).
