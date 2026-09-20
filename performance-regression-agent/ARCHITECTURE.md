# Architecture

## Overview

The Performance Regression Agent is a deterministic pipeline: **load →
group → summarize → compare → classify → render**. There is no LLM in the
decision path; every verdict is a reproducible function of the input telemetry
and the (versioned) `DetectionConfig`.

```
TelemetryDataset (JSON)
        │  io_utils.load_dataset  (Pydantic validation)
        ▼
   group by (config, workload, env.fingerprint())      detector.analyze
        │
        ▼
   pick baseline (oldest commit) & candidate (newest)  detector._select_baseline_and_candidate
        │
        ▼
   per shared metric:
     summarize(baseline), summarize(candidate)          statistics.summarize
        │   └─ robust outlier rejection (IQR + modified-z)
        ▼
     delta_abs, delta_pct, robust_z (MAD-based)          detector.compare_pair
        ▼
     classify -> Verdict + confidence + evidence         detector._classify
        ▼
   RegressionReport ──► JSON (io_utils) / Markdown (renderer)
```

## Components

| Module | Responsibility |
|---|---|
| `models.py` | Versioned Pydantic v2 contracts; metric metadata (units, higher-is-better); safety validators |
| `statistics.py` | Pure-stdlib robust statistics: percentile, MAD, outlier rejection, summary stats with 95% CI, robust-z change |
| `detector.py` | Controlled grouping, baseline/candidate selection, per-metric comparison, deterministic classification |
| `benchmark.py` | Seeded generator for the public mock-telemetry benchmark with an injected regression |
| `renderer.py` | Markdown report rendering (mirrors JSON; adds no new claims) |
| `io_utils.py` | Load/validate datasets, serialize reports deterministically |
| `schema_export.py` | Export JSON Schema for the public contracts |
| `cli.py` | Typer CLI (`analyze`, `demo`, `gen-benchmark`, `export-schemas`, `show-report`, `version`) |

## Typed input/output contracts

- **Input**: `TelemetryDataset { schema_version, name, runs: [TelemetryRun] }`
  where `TelemetryRun` carries `commit`, `commit_order`, `config`, `workload`,
  `Environment`, `artifact_url`, and repeated `MetricSample`s.
- **Output**: `RegressionReport { schema_version, dataset_name, detection_config,
  counts, findings: [RegressionFinding] }`. Each `RegressionFinding` contains both
  sides' `MetricStats`, `delta_pct`, `robust_z`, `verdict`, `confidence`,
  `evidence`, and `artifact_urls`.

All models use `extra="forbid"`; unknown fields are rejected at load time.

## Authority boundaries

- The tool is **read-only** with respect to source/RTL/telemetry. It only writes
  report artifacts to paths the user specifies.
- It emits **heuristic** verdicts, never a signoff or a root-cause conclusion.
- It never reclassifies an ambiguous or low-sample result as a PASS/STABLE:
  large-but-unconfirmed changes are `INCONCLUSIVE`.
- The `RegressionFinding` model *enforces* that a `REGRESSION`/`IMPROVEMENT`
  cannot exist without `evidence` — the safety rule is a code invariant, not a
  convention.

## Determinism

- Statistics use the standard library only (no numpy) so results are identical
  across platforms.
- The benchmark generator is seeded (`SEED = 20260920`).
- `analyze(build_dataset())` is verified byte-stable by `test_analysis_is_deterministic`
  and the golden-report tests.

## Detection algorithm (per metric)

1. Reject outliers on each side (Tukey IQR fence **or** modified z-score).
2. Compute mean/median/stdev/CV and a Student-t 95% CI on the kept samples.
3. `delta_pct` = signed % change of the mean; `robust_z` = `(cand_mean −
   base_median) / (MAD·1.4826)`.
4. A change is **significant** only if `|delta_pct| ≥ min_pct_change` **and**
   `|robust_z| ≥ robust_z_threshold` (both effect size and signal-to-noise).
5. Direction is resolved against the metric's `higher-is-better` flag: a
   significant change in the bad direction is `REGRESSION`, in the good direction
   `IMPROVEMENT`; otherwise `STABLE`; large-but-unconfirmed (too few samples) is
   `INCONCLUSIVE`.
