# Formal Run Orchestrator

Reproducible, provenance-tracked orchestration of formal-verification experiments on
**public** RTL/SVA. This v0.1 ships the **data schemas, a deterministic planner, and a
MOCK executor** (no real formal tool), plus a result classifier, a SQLite run ledger,
and an offline, leakage-free **policy-evaluation** harness.

> **This is a research prototype and orchestration harness, not a formal tool.**
> Orchestration is heuristic. Formal-tool results remain authoritative. The mock
> executor produces *deterministic pseudo-runs* to exercise the pipeline end-to-end;
> it does **not** prove anything about any real design.

## What it does (v0.1, all real and working)

- **Typed contracts (Pydantic v2)** for configs, benchmarks, plans, run records, and
  metrics — models *validate*, they don't just annotate.
- **Finite, versioned configuration catalog** (`catalog.py`): fixed engine catalog,
  BMC depth tiers, timeout tiers, memory-cap tiers, preprocessing and partition
  choices. Nothing outside the catalog is plannable or runnable.
- **Deterministic planner** (`planner.py`): idempotent `(suite, policy)` → plan.
- **Mock executor** (`executor.py`): a transparent, documented pseudo-run model.
  Same `(benchmark, config, seed)` → same result. No shell/network/formal tool.
- **Result classifier** (`classifier.py`): maps raw signals to the fixed vocabulary
  `PASS / FAIL / TIMEOUT / ERROR / INCONCLUSIVE`. **Never** classifies a timeout,
  error, or inconclusive run as PASS (enforced in code *and* tests).
- **SQLite ledger** (`ledger.py`): durable store of suites, plans, and run records
  with **full provenance** (design/property SHA placeholders, input hashes, tool
  name+version, command line, config ID, seed, machine/OS metadata, start/end,
  CPU/wall time, peak memory, return code, status, artifact paths/hashes, rationale,
  validation status).
- **Policy layer** (`policies/`): fixed baseline, random baseline, rule-based
  heuristic, and an optional **contextual-bandit (LinUCB, pure-Python)** policy.
- **Leakage-free evaluation** (`split.py`, `evaluation.py`): group-level holdout so
  correlated designs never straddle train/test; reward penalizes timeout, excess
  memory, and invalid configs; metrics report + feature-group ablation.
- **CLI** (`cli.py`): `plan`, `run`, `ingest-result`, `summarize`, `compare`
  (+ `evaluate`, `ablate`, `catalog`, `init-suite`).

## Install

```bash
python3.11 -m venv .venv          # 3.11+ required
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart (end-to-end on the bundled public toy suite)

```bash
# Inspect the approved configuration catalog
formal-orchestrator catalog

# Plan a baseline experiment (deterministic), store it in the SQLite ledger
formal-orchestrator plan --policy rule_based --db reports/ledger.db
# -> prints plan_id=plan-rule_based-XXXXXXXXXX

# Execute the plan with the MOCK executor (records full provenance)
formal-orchestrator run <plan_id> --db reports/ledger.db

# Summarize the ledger into a status/resource/reward report
formal-orchestrator summarize --plan-id <plan_id> --db reports/ledger.db

# Offline, leakage-free comparison of all policies on the held-out test split
formal-orchestrator compare --split test --out reports/policy_comparison.md

# Bandit feature-group ablation
formal-orchestrator ablate --out reports/ablation.md
```

Ingesting a run record produced by an external (future real) backend adapter:

```bash
formal-orchestrator ingest-result path/to/run_record.json --db reports/ledger.db
```

Sample generated reports are checked in under [`reports/`](reports/) and a baseline
writeup is in [`docs/BASELINE_REPORT.md`](docs/BASELINE_REPORT.md).

## Result vocabulary

| Outcome        | Meaning |
| -------------- | ------- |
| `PASS`         | Backend returned a passing result under the exact recorded design, assumptions, property, tool version, and configuration. |
| `FAIL`         | A counterexample/failure was produced; triage required before calling it a design bug. |
| `TIMEOUT`      | No conclusion within the resource budget. **Never a pass.** |
| `ERROR`        | Run invalid/incomplete or tool execution failed. **Never a pass.** |
| `INCONCLUSIVE` | No proof or counterexample (e.g. BMC exhausted a bound). **Never a pass.** |

"Solved within budget" = the tool reached a **conclusion (PASS or FAIL)** within its
budget. A `FAIL` (counterexample) is a useful, legitimate outcome.

## Scope & limitations (read this)

- **Mock executor only.** No real formal engine is invoked in v0.1. The mock's cost
  model is a documented heuristic, not a claim about any solver's behavior.
- **Public toy benchmark only.** SHAs are placeholders; there is no proprietary RTL.
- **Policies are heuristic**, explicitly labeled as such. The bandit is optional and
  trained offline on the train split only.
- **The orchestrator never modifies RTL/SVA/assumptions and never claims
  proof/signoff.** See the human gate below.

## Non-claims

This project does **not** claim: autonomous proof, solver optimization, formal
signoff, verified assertion generation, commercial-grade solving, or that any policy's
mock-measured advantage transfers to a real tool. See `EVIDENCE.md` and
`THREAT_MODEL.md`.

## Human gate (authority boundary)

Changing a property, assumption, abstraction boundary, or resource budget requires
**explicit human approval** — the orchestrator will not do it. See
[`docs/HUMAN_GATE.md`](docs/HUMAN_GATE.md).

## Roadmap (later phases, intentionally not built yet)

- Real backend adapter (e.g. an open-source model checker) behind the same
  `RawResult` interface the classifier already consumes. *(TODO)*
- Containerized execution worker (Docker) with resource limits. *(TODO — see
  `docs/CONTAINER_STRATEGY.md`.)*
- Triage agent summarizing logs/counterexamples with artifact citations. *(TODO)*
- Bayesian-optimization policy alongside the contextual bandit. *(TODO)*

## License

MIT (placeholder) — see `LICENSE`.
