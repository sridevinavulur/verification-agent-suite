# Evidence

Each resume-safe claim below is tied to source, tests, and a reproduce command. All
evidence is **implementation evidence** on a public toy suite via the **mock**
executor — not experimental evidence about a real formal tool.

Setup for every reproduce command:
```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

---

### C1 — Typed, validating data contracts (Pydantic v2)
- **Claim:** All experiment/result payloads are Pydantic v2 models that validate.
- **Source:** `src/formal_run_orchestrator/models.py`
- **Tests:** `tests/test_models.py`
- **Reproduce:** `pytest tests/test_models.py -q`
- **Limitation:** contracts cover the mock pipeline; a real backend adapter is future work.

### C2 — Never classifies TIMEOUT/ERROR/INCONCLUSIVE as PASS
- **Claim:** The classifier maps to a fixed vocabulary and cannot emit PASS for a
  non-conclusive or errored run; `RunRecord` rejects PASS with a nonzero return code.
- **Source:** `src/formal_run_orchestrator/classifier.py`,
  `RunRecord._no_pass_without_conclusion` in `models.py`
- **Tests:** `tests/test_classifier.py`, `test_executor.py::test_invalid_config_is_error_not_hidden`,
  `test_executor.py::test_shallow_bmc_on_deep_property_never_passes`
- **Reproduce:** `pytest tests/test_classifier.py tests/test_executor.py -q`

### C3 — Finite, versioned configuration catalog; policies choose only from it
- **Claim:** All configs come from a versioned catalog; every policy selects a valid
  catalog config.
- **Source:** `src/formal_run_orchestrator/catalog.py`, `policies/`
- **Tests:** `tests/test_planner_policies.py::test_all_policies_choose_only_catalog_configs`
- **Reproduce:** `pytest tests/test_planner_policies.py -q` ; `formal-orchestrator catalog`

### C4 — Deterministic, idempotent planner
- **Claim:** Planning `(suite, policy)` twice yields the same plan.
- **Source:** `src/formal_run_orchestrator/planner.py`
- **Tests:** `tests/test_planner_policies.py::test_planner_is_deterministic_and_idempotent`
- **Reproduce:** `pytest tests/test_planner_policies.py -q`

### C5 — Deterministic mock executor with full provenance
- **Claim:** Runs are reproducible and each record carries complete provenance
  (SHAs, hashes, tool+version, command, config, seed, machine, timing, memory, return
  code, status, artifacts, rationale, validation status).
- **Source:** `src/formal_run_orchestrator/executor.py`, `RunRecord` in `models.py`
- **Tests:** `tests/test_executor.py::{test_simulate_is_deterministic,test_execute_records_full_provenance}`
- **Reproduce:** `pytest tests/test_executor.py -q`

### C6 — SQLite ledger with validated round-trip + ingestion
- **Claim:** Suites/plans/runs persist and round-trip; external run JSON is validated
  on ingest and malformed records are rejected.
- **Source:** `src/formal_run_orchestrator/ledger.py`
- **Tests:** `tests/test_ledger.py`
- **Reproduce:** `pytest tests/test_ledger.py -q`

### C7 — Leakage-free (group-level) train/test split
- **Claim:** No design family straddles train and test; the split is stable.
- **Source:** `src/formal_run_orchestrator/split.py`
- **Tests:** `tests/test_split_reward_metrics.py::{test_split_has_no_group_leakage,test_split_is_stable_across_calls}`
- **Reproduce:** `pytest tests/test_split_reward_metrics.py -q`

### C8 — Reward penalizes timeout / excess memory / invalid configs
- **Claim:** The reward function penalizes non-conclusive and unsound choices.
- **Source:** `src/formal_run_orchestrator/reward.py`
- **Tests:** `tests/test_split_reward_metrics.py::{test_reward_penalizes_timeout_more_than_solved,test_reward_worst_for_invalid_config}`
- **Reproduce:** `pytest tests/test_split_reward_metrics.py -q`

### C9 — Metrics report + offline policy comparison + ablation
- **Claim:** Reports solved-within-budget %, status counts, CPU/wall/memory, attempts,
  per-design variance, and CIs (n≥3); compares fixed/random/rule/bandit on a held-out
  split; ablates bandit feature groups.
- **Source:** `metrics.py`, `evaluation.py`, `report.py`
- **Tests:** `tests/test_evaluation_cli.py`
- **Reproduce:**
  ```bash
  formal-orchestrator compare --split test --out reports/policy_comparison.md
  formal-orchestrator ablate --out reports/ablation.md
  ```
- **Output:** `reports/policy_comparison.md`, `reports/ablation.md`

### C10 — End-to-end CLI on the sample suite
- **Claim:** `plan -> run -> summarize` runs end-to-end and produces a baseline report.
- **Source:** `cli.py`, `sample_suite.py`
- **Tests:** `tests/test_evaluation_cli.py::test_cli_plan_run_summarize`
- **Reproduce:**
  ```bash
  formal-orchestrator plan --policy rule_based --db reports/ledger.db
  formal-orchestrator run <plan_id> --db reports/ledger.db
  formal-orchestrator summarize --plan-id <plan_id> --db reports/ledger.db
  ```
- **Output:** `reports/baseline_summary.md`, `docs/BASELINE_REPORT.md`

---

## Experimental-performance evidence
**None claimed.** All numbers are produced by the mock executor and describe the
*harness*, not any real solver. Do not cite the comparison numbers as solver results.
Release tag / commit: `TODO` (placeholder).
