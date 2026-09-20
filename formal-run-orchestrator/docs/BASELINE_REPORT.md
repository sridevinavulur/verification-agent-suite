# Baseline Experiment Report

**Suite:** `public-toy-v1` (22 synthetic public benchmarks across 8 design families).
**Executor:** MOCK (deterministic pseudo-runs; no real formal tool).
**Catalog:** `2026.09.1`.

> All numbers below are produced by the mock executor and describe the **orchestration
> harness**, not any real solver. They are reproducible from a fresh clone.

## Reproduce

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
formal-orchestrator plan --policy rule_based --db reports/ledger.db      # note the plan_id
formal-orchestrator run <plan_id> --db reports/ledger.db
formal-orchestrator summarize --plan-id <plan_id> --db reports/ledger.db --out reports/baseline_summary.md
formal-orchestrator compare  --split test --out reports/policy_comparison.md
formal-orchestrator ablate   --out reports/ablation.md
```

## 1. Baseline run (rule-based policy, whole suite)

| Metric | Value |
| --- | --- |
| Designs / attempts | 22 / 22 |
| **Solved within budget** | **63.6%** (PASS+FAIL) |
| PASS / FAIL / TIMEOUT / ERROR / INCONCLUSIVE | 10 / 4 / 6 / 2 / 0 |
| Total CPU / wall time | 1051.5 s / 893.0 s |
| Peak memory | 15816 MB |
| Mean reward | 0.263  (95% CI [-0.089, 0.616]) |

Full rendered report: [`../reports/baseline_summary.md`](../reports/baseline_summary.md).

Note that TIMEOUT/ERROR runs are reported, not hidden, and are never counted as solved.

## 2. Offline policy comparison (held-out TEST split, leakage-free)

See [`../reports/policy_comparison.md`](../reports/policy_comparison.md) for the live
table. Summary of what the harness demonstrates:

- The split is at the **design-group level**, so no design family appears in both
  train and test.
- All four policies (fixed, random, rule-based, optional LinUCB bandit) are evaluated
  on the same split; the random baseline is the weakest by solved-% and reward (it
  frequently picks oversized configs that hit the memory cap and ERROR out), which is
  the expected sanity check.
- The mock cost model happens to favor the mid-tier BMC config broadly, so the
  `fixed` baseline is strong and ties the trained bandit at the top of the toy split —
  exactly the kind of honest, sometimes-counter-intuitive finding this harness is meant
  to surface rather than paper over. On this toy suite the rule-based heuristic lands
  between random and fixed/bandit.

## 3. Feature-group ablation (bandit)

See [`../reports/ablation.md`](../reports/ablation.md). Removing the `size` and
`property_type` feature groups changes the bandit's TEST metrics, indicating those
groups carry signal in this toy setting; `depth`/`difficulty` move it less. On a toy
suite these deltas are indicative only (see Threats to Validity).

## 4. Threats to validity (summary; full list in `THREAT_MODEL.md`)

- **Mock, not real:** the cost model is invented; numbers do not transfer to a solver.
- **Small sample / correlated designs:** few groups → wide CIs; treat as indicative.
- **Tool-version drift:** cross-version comparison is invalid; `tool_version` and
  `catalog_version` are recorded on every run to detect it.
- **Selective reporting / reward hacking:** the reward penalizes timeout, excess
  memory, and invalid configs; comparison and ablation report all variants.

## 5. Authority boundary

The orchestrator never modifies RTL/SVA/assumptions and never claims proof/signoff.
See [`HUMAN_GATE.md`](HUMAN_GATE.md).
