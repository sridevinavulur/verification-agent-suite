# Benchmarks

## Source & license
The bundled suite (`public-toy-v1`) is **fully synthetic**, authored for this repo.
There is no third-party or proprietary RTL. All design/property SHAs are **placeholders**
(`sha256:<hash-of-design-name>`), not real git objects. License: MIT (same as repo).

Generate the JSON form:
```bash
formal-orchestrator init-suite --out examples/benchmarks/sample_suite.json
```

## Contents
22 `(design, property)` items across 8 correlated design families (`group`):

| Group | Designs | Notes |
| --- | --- | --- |
| counter | counter, counter_buggy | overflow/reset props + a wrap bug |
| fifo | sync_fifo(+buggy) | overflow/underflow + a cover |
| arbiter | rr_arbiter | one-hot grant, no-starvation (deep) |
| handshake | valid_ready(+buggy) | data-stable, no-drop bug |
| alu | alu(+buggy) | hard commutativity + shift bug |
| shifter | barrel_shifter(+buggy) | rotate-inverse, sign-leak bug, cover |
| crc | crc32(+buggy) | reset-seed, idle-stable, poly bug |
| stack | lifo_stack(+buggy) | overflow/underflow, LIFO order, cover |

Each item carries observable features a policy may condition on: `rtl_lines`,
`register_count`, `coi_size`, `max_depth_hint`, `intrinsic_difficulty`, property
`kind`, and a toy `is_holds` ground truth used only by the mock executor.

## Split methodology (leakage-free)
- Splitting is at the **group** level via `split.group_holdout_split`.
- Groups are hashed into 100 buckets with a fixed salt; the lowest `test_fraction`
  buckets form TEST. A whole family is entirely train or entirely test.
- Default: `test_fraction=0.4`, salt `frv-holdout-b`. Deterministic and stable when
  items are added to an existing group.

## Metrics
Reported per policy per split (`metrics.py`):
solved-within-budget %, PASS/FAIL/TIMEOUT/ERROR/INCONCLUSIVE counts, total CPU & wall
time, peak memory, number of attempts, per-design reward variance, and a 95% CI on
mean reward when n ≥ 3.

## Exclusions
- No real solver output is included (mock only).
- INCONCLUSIVE/ERROR/TIMEOUT runs are **retained and reported**, never excluded from
  counts; they are only excluded from the "solved" numerator (by definition).

## Reproducibility
All metrics are deterministic functions of the suite, catalog, policy, and seeds; a
fresh clone reproduces `reports/*.md` (modulo host metadata in per-run provenance).
