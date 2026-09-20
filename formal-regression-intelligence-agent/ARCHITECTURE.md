# Architecture

## Overview

```
run ledger (.json / .jsonl)          RunRecord[]              RegressionReport
  produced by                 load_ledger()            analyze()          render_markdown()
  formal-run-orchestrator  ───────────────►  validate  ──────────►  ┌── findings ──┐  ──► JSON / Markdown
                                                                     │  queue       │
                                                                     └──────────────┘
                                                                            │
                                                          explain() ── MockLLM (offline)
```

Two clearly separated layers, per `BUILD_STANDARD.md`:

1. **Deterministic layer (authoritative).** `stats.py` + `analysis.py` compute
   every cluster, baseline, alert, and the prioritized queue with pure functions
   over the ingested records. No randomness, no I/O, no LLM. This layer alone
   decides what is a finding.
2. **LLM layer (narration only).** `explain.py` turns a finding's *own* evidence
   into prose. It cannot create findings, statuses, or run IDs. The default and
   CI adapter is a deterministic offline `MockLLM`.

## Components and contracts

| Module | Responsibility | Key types |
|--------|----------------|-----------|
| `models.py` | Typed I/O contracts (Pydantic v2, validating). | `RunRecord`, `RunLedger`, `Finding`, `RegressionReport`, `Severity`, `FindingKind`, evidence models |
| `stats.py` | Robust statistical primitives. | `baseline_stats`, `z_score`, `robust_z`, `mad`, `coefficient_of_variation` |
| `analysis.py` | The 7 deterministic analyses + queue assembly. | `analyze`, `Thresholds`, per-analysis functions |
| `ledger.py` | Ingest JSON array or JSONL; validate loudly. | `load_ledger` |
| `explain.py` | Mock-LLM explanation adapter. | `LLMAdapter` (Protocol), `MockLLM` |
| `report.py` | Markdown rendering. | `render_markdown` |
| `cli.py` | Typer CLI. | `app` |

### Input contract — `RunRecord`

Mirrors `formal-run-orchestrator`'s `RunRecord`. Only the fields this agent reads
are declared; `extra="ignore"` accepts (and drops) unknown fields from newer
producers. Derived identities:

- `job_key = "{benchmark_id}::{config_id}"` — a *logical job*; its repeats
  (across seeds/commits) form the baseline for regression and flakiness.
- `signature_fields = (design_sha, property_sha, config_id, catalog_version)` —
  content identity for duplicate detection.

### Output contract — `RegressionReport`

`n_records`, `n_jobs`, `n_benchmarks`, `status_totals`, a list of `Finding`, and
an `investigation_queue` of `InvestigationItem`. Each `Finding` carries
`member_run_ids` (the exact records it was computed from), machine-readable
`evidence`, a `severity`, and a deterministic `priority_score`. `heuristic=True`
on every finding.

## Determinism and ordering

- Findings are globally sorted by `(-severity_rank, -priority_score, finding_id)`
  so the queue is stable regardless of input order.
- Job/benchmark grouping sorts members by `(start_time, run_id)`.
- All hashing is SHA-256 over documented field tuples.

This determinism is what makes the golden-output test (`test_golden_report_matches`)
meaningful.

## Authority boundary

- **May:** read a ledger, compute statistics, cluster, rank, emit reports, and
  narrate findings with a mock LLM.
- **Must not:** modify RTL / properties / assumptions / budgets / configs;
  declare a root cause; call a TIMEOUT/ERROR/INCONCLUSIVE a PASS; hide or drop a
  run (malformed records raise, they are not silently skipped).
- **Human required:** all remediation. The queue recommends a *next investigation
  step*, never an automatic change.
