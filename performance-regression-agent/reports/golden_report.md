# Performance Regression Report: public-mock-benchmark

- Schema version: `1.0.0`
- Runs analyzed: **20**
- Comparisons: **13**
- Regressions detected: **2**

## Detection configuration

- min |Δ%| to flag: `5.0%`
- robust z threshold: `3.5`
- min samples for confident verdict: `3`
- outlier rejection: IQR k=`1.5`, modified-z=`3.5`

## Summary

| Verdict | Metric | Config / Workload | Baseline mean | Candidate mean | Δ% | robust z | Confidence |
|---|---|---|---:|---:|---:|---:|---:|
| 🔴 REGRESSION | `peak_memory_mb` | opt3 / cache_stress | 2048.417 | 2412.908 | +17.8% | +85.48 | 0.96 |
| 🔴 REGRESSION | `sim_runtime_s` | opt3 / cache_stress | 120.122 | 161.307 | +34.3% | +16.72 | 1.00 |
| 🟢 IMPROVEMENT | `throughput_mops` | opt3 / random_rw | 847.265 | 1031.783 | +21.8% | +313.16 | 0.98 |
| ⚪ STABLE | `sim_runtime_s` | opt3 / random_rw | 108.598 | 106.824 | -1.6% | -6.04 | 0.60 |
| ⚪ STABLE | `latency_ns` | opt3 / random_rw | 41.616 | 35.503 | -14.7% | -3.12 | 0.60 |
| ⚪ STABLE | `coverage_rate_pct` | opt3 / cache_stress | 78.274 | 77.801 | -0.6% | -2.73 | 0.60 |
| ⚪ STABLE | `fpga_fmax_mhz` | synth / top_build | 298.960 | 301.879 | +1.0% | +1.98 | 0.60 |
| ⚪ STABLE | `formal_runtime_s` | synth / top_build | 299.590 | 312.214 | +4.2% | +1.61 | 0.60 |
| ⚪ STABLE | `throughput_mops` | opt3 / cache_stress | 856.920 | 854.567 | -0.3% | -1.54 | 0.60 |
| ⚪ STABLE | `peak_memory_mb` | debug / smoke | 1432.200 | 1439.629 | +0.5% | +0.55 | 0.60 |
| ⚪ STABLE | `coverage_rate_pct` | debug / smoke | 78.188 | 78.217 | +0.0% | -0.45 | 0.60 |
| ⚪ STABLE | `fpga_lut_util_pct` | synth / top_build | 55.201 | 55.093 | -0.2% | -0.24 | 0.60 |
| ⚪ STABLE | `sim_runtime_s` | debug / smoke | 59.586 | 59.614 | +0.0% | -0.01 | 0.60 |

## Regressions (with evidence)

### 🔴 `peak_memory_mb` — opt3 / cache_stress (+17.8%)

- Environment: `x86_64-linux|verilator@5.020`
- Baseline commit `a1b2c3d` → candidate commit `e5f6a7b`
- Baseline: mean=2048.417 (n=4, stdev=5.807, CV=0.003, 95% CI [2039.178, 2057.656])
- Candidate: mean=2412.908 (n=3, stdev=3.949, CV=0.002, 95% CI [2403.098, 2422.717])
- Confidence: **0.96**
- Evidence:
  - Mean changed +17.8% (unit: MB), |Δ%|=17.8% ≥ 5.0%.
  - Robust z=+85.48 (MAD-based) exceeds ±3.5: change is large relative to baseline noise.
  - Metric 'peak_memory_mb' is lower-is-better; observed direction is worse.
  - Outliers rejected before comparison: baseline=[2023.8623], candidate=[2396.7239, 2446.7847].
  - Baseline mean=2048.417 [95% CI 2039.178, 2057.656], candidate mean=2412.908 [95% CI 2403.098, 2422.717].
- Artifacts:
  - <https://ci.example.org/artifacts/A/a1b2c3d>
  - <https://ci.example.org/artifacts/A/e5f6a7b>

### 🔴 `sim_runtime_s` — opt3 / cache_stress (+34.3%)

- Environment: `x86_64-linux|verilator@5.020`
- Baseline commit `a1b2c3d` → candidate commit `e5f6a7b`
- Baseline: mean=120.122 (n=5, stdev=3.282, CV=0.027, 95% CI [116.048, 124.196])
- Candidate: mean=161.307 (n=5, stdev=4.841, CV=0.030, 95% CI [155.297, 167.317])
- Confidence: **1.00**
- Evidence:
  - Mean changed +34.3% (unit: s), |Δ%|=34.3% ≥ 5.0%.
  - Robust z=+16.72 (MAD-based) exceeds ±3.5: change is large relative to baseline noise.
  - Metric 'sim_runtime_s' is lower-is-better; observed direction is worse.
  - Baseline mean=120.122 [95% CI 116.048, 124.196], candidate mean=161.307 [95% CI 155.297, 167.317].
- Artifacts:
  - <https://ci.example.org/artifacts/A/a1b2c3d>
  - <https://ci.example.org/artifacts/A/e5f6a7b>

---
_Heuristic report. Findings are deterministic statistical comparisons, not a root-cause claim. Every REGRESSION/IMPROVEMENT verdict lists its supporting evidence; INCONCLUSIVE marks changes that lack enough samples or signal-to-noise to confirm._
