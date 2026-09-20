# Performance Regression Agent

Deterministic detection and explanation of **performance regressions** across
commits, configurations, workload traces, and platforms for RTL simulation,
formal, and FPGA-oriented experiments.

Given versioned telemetry (runtime, memory, throughput, latency, bandwidth,
utilization, coverage rate, FPGA fmax/resource, …), the agent performs a
**controlled baseline comparison** for every directly-comparable group, rejects
measurement outliers robustly, and reports each metric change as
`REGRESSION` / `IMPROVEMENT` / `STABLE` / `INCONCLUSIVE` with variance,
confidence, and the **evidence** behind the verdict.

## Scope (v0.1)

This is a **working detector**, not a skeleton. It implements:

- **Versioned metrics schema** (Pydantic v2, `schema_version`, `extra="forbid"`).
- **Controlled baseline comparison** — candidate runs are only compared against a
  baseline that shares the same `(config, workload, environment)` so a
  platform/tool-version change is never mistaken for a code regression.
- **Confidence / variance reporting** — mean, stdev, median, coefficient of
  variation, and a Student-t **95% CI** per metric.
- **Robust outlier detection** — Tukey IQR fence + modified (MAD-based) z-score;
  a single wild sample cannot create a false regression.
- **Robust change scoring** — change measured in baseline MAD-sigmas so the
  significance test is resistant to noise.
- **Hardware / tool-version tracking** — every run carries an `Environment`
  (platform, tool, tool version, CPU, RAM, OS); an `env.fingerprint()` groups
  comparable runs.
- **Artifact links** — per-run `artifact_url` is propagated into findings.
- **No root-cause claim without evidence** — the model layer *rejects* a
  `REGRESSION`/`IMPROVEMENT` finding that has no `evidence`; ambiguous cases are
  `INCONCLUSIVE`, never a false `STABLE`/PASS.
- **Public benchmark** of deterministic mock telemetry (20 runs, 5 commits, 2
  platforms) with **one injected regression** (sim runtime +35%, peak memory
  +18%), one genuine improvement, and noise-only / outlier groups that must
  **not** false-alarm.
- **Report generation**: JSON (validated contract) + Markdown, plus a committed
  **golden report**.

### Non-claims / limitations

- The agent does **not** perform root-cause analysis or bisection; it detects and
  quantifies changes and links the artifacts an engineer needs to investigate.
- Findings are **heuristic statistical comparisons**, explicitly labelled as such
  — not a formal/sound proof of a regression.
- It compares the **oldest vs newest** commit in each group (a first-and-last
  baseline). Per-commit change-point detection across the whole series is a
  documented future phase.
- No real tools are invoked and there is **no network access**; telemetry is an
  input artifact you supply (or generate with the bundled benchmark).

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Generate the public benchmark (deterministic mock telemetry)
perf-regress gen-benchmark examples/telemetry/benchmark.json

# Analyze it -> prints a summary, writes JSON + Markdown reports
perf-regress analyze examples/telemetry/benchmark.json \
    --json reports/report.json --md reports/report.md

# Or run the built-in demo directly
perf-regress demo
```

Expected demo output:

```
Runs=20 comparisons=13 regressions=2
  REGRESSION peak_memory_mb [opt3/cache_stress] +17.8% (robust z=+85.48, confidence=0.96)
  REGRESSION sim_runtime_s [opt3/cache_stress] +34.3% (robust z=+16.72, confidence=1.00)
```

The detector finds **exactly** the two injected regressions and does **not**
flag the pure-noise group or the group containing a wild FPGA-fmax outlier.

### Other commands

```bash
perf-regress show-report examples/telemetry/benchmark.json   # Markdown to stdout
perf-regress export-schemas schemas/                         # JSON Schema export
perf-regress analyze <dataset> --fail-on-regression          # CI gate (exit 1)
perf-regress analyze <dataset> --min-pct 10 --robust-z 4     # tune thresholds
```

## Telemetry format

See `schemas/telemetry_dataset.schema.json` and `examples/telemetry/benchmark.json`.
A dataset is a list of `TelemetryRun`s; each run has repeated `MetricSample`s per
metric so variance and confidence can be computed.

## Tests

```bash
ruff check .
pytest
```

## License

MIT — see `LICENSE`. All bundled data is public, synthetic mock telemetry.
