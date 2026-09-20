# Formal Regression Intelligence Agent

Deterministic clustering and statistical-baseline analytics over **formal-run
ledgers**. Given the run records produced by a formal-verification orchestrator,
it surfaces the jobs a verification team should investigate first: flaky, slow,
duplicate, configuration-sensitive, failing, timing-out, and resource-intensive
jobs.

The deterministic engine is authoritative. An LLM is used **only** to narrate
findings the engine has already substantiated, via an offline **mock adapter**.

> Spec: prompt pack section 6.9 (Formal Regression Intelligence Agent).
> Engineering rules: `BUILD_STANDARD.md`.

## What it does (v0.1 scope)

Every output below is produced by pure, deterministic Python from the ingested
records — no randomness, no network — so results are reproducible and
golden-testable.

| Output | How it is computed |
|--------|--------------------|
| **Failure clusters** | Group `FAIL` runs by `(property_sha, return_code)` signature. |
| **Timeout clusters** | Group `TIMEOUT` runs by `config_id`. |
| **Duplicate / near-duplicate jobs** | Signature-hash identical inputs `(design_sha, property_sha, config_id, catalog_version)`; exact = repeated seed, near = differing only by seed. |
| **Runtime-regression alerts** | Robust z-score (median / MAD) + min-ratio gate on `wall_time_s` of a job's latest run vs its own baseline history. |
| **Memory-regression alerts** | Same statistics on `peak_memory_mb`. |
| **Configuration-sensitivity summaries** | Per-benchmark outcome/runtime spread across configs (solved-by-some vs solved-by-all; per-config median wall-time spread ratio). |
| **Reproducibility warnings** | Per-job status disagreement across repeats (PASS↔FAIL is HIGH), status-flip rate, runtime coefficient of variation. |
| **Prioritized investigation queue** | All findings ranked by severity then deterministic priority score, each with a recommended next step. |

## Install

```bash
python3.13 -m venv .venv         # 3.11+ works; 3.13 used here
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Full machine-readable report (JSON)
formal-regress analyze examples/sample_ledger.jsonl

# Human-readable Markdown, with mock-LLM explanations
formal-regress report examples/sample_ledger.jsonl --explain

# Just the ranked investigation queue
formal-regress queue examples/sample_ledger.jsonl

# Mock-LLM explanations for each finding
formal-regress explain examples/sample_ledger.jsonl

# Export a JSON Schema contract
formal-regress schema run-record
```

On the bundled 20-record public ledger the queue looks like:

```
#1  [  high] runtime_regression       score= 105.9  runtime regression on arbiter::cfg-pdr: 5.9x baseline median
#2  [  high] memory_regression        score= 105.2  memory regression on arbiter::cfg-pdr: 5.2x baseline median
#3  [  high] reproducibility_warning  score=  15.0  Flaky job handshake::cfg-kind: conflicting verdicts (PASS x2, FAIL x1)
...
```

## Interop with `formal-run-orchestrator`

The ingested run-record contract mirrors the `RunRecord` emitted by the sibling
[`formal-run-orchestrator`](../formal-run-orchestrator) project. Field names and
semantics are reused verbatim (`run_id`, `benchmark_id`, `design_sha`,
`property_sha`, `input_hash`, `config_id`, `catalog_version`, `tool_name`,
`tool_version`, `seed`, `wall_time_s`, `cpu_time_s`, `peak_memory_mb`,
`return_code`, `status`, …). A ledger exported by that orchestrator — as a JSON
array **or** JSONL — ingests here with no transformation. Unknown extra fields
from a newer producer are ignored rather than rejected, so this analytics tool
does not brittle-break on schema evolution.

The shared result vocabulary (`PASS`/`FAIL`/`TIMEOUT`/`ERROR`/`INCONCLUSIVE`) is
identical, and a `PASS` with a non-zero return code is rejected on ingest.

## Regenerate the fixtures / golden output

```bash
python scripts/make_fixtures.py
```

This writes `examples/sample_ledger.jsonl` and `examples/golden_report.json`.
`tests/test_golden_and_cli.py::test_golden_report_matches` pins the analysis to
that golden.

## Limitations and non-claims

- **This tool does not determine root cause.** Every finding is a HEURISTIC
  statistical or structural pattern. It reports correlations and asks a human to
  investigate; it never asserts *why* a job regressed, failed, or flaked.
- **A TIMEOUT / ERROR / INCONCLUSIVE result is never treated as a PASS**, and a
  timeout's wall-time never poisons a runtime baseline.
- It does **not** modify RTL, properties, assumptions, budgets, configs, or any
  signoff conclusion. It only reads a ledger and emits observations.
- The bundled LLM adapter is a **deterministic offline mock**. No real model is
  called; there is no network dependency and no API key. A real provider would
  implement the same `explain(finding)` contract behind an env-gated flag (not
  wired up in v0.1).
- The example ledger is a **public toy** hand-crafted to exercise each analysis;
  it is not real telemetry and implies nothing about any tool's performance.
- Thresholds (`analysis.Thresholds`) are explicit, documented knobs, not tuned
  against any real dataset.

## Repository layout

```
src/formal_regression_intelligence/
  models.py     typed contracts (RunRecord interop + findings/report)
  stats.py      robust statistical primitives (median/MAD/z/robust-z)
  analysis.py   the 7 deterministic analyses + prioritized queue
  ledger.py     JSON-array / JSONL ingestion with loud validation
  explain.py    mock-LLM explanation adapter (offline, deterministic)
  report.py     Markdown renderer
  cli.py        Typer CLI (analyze/report/queue/explain/schema)
examples/       public sample ledger + golden report
schemas/        exported JSON Schema contracts
scripts/        fixture generator
tests/          pytest suite (golden + per-analysis behavior)
```

## License

MIT (placeholder) — see `LICENSE`.
