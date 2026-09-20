# Evidence

Each claim is tied to source, test, and a reproduce command. Distinguishes
*implementation evidence* (the code does X, proven by tests) from
*experimental-performance evidence* (none is claimed — the bundled ledger is a
public toy, not a benchmark of any tool).

Reproduce environment:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Release/commit: `<placeholder-sha>`. Tool version: `0.1.0`.

| ID | Claim | Source | Test(s) | Reproduce |
|----|-------|--------|---------|-----------|
| C1 | Ingests a formal-run ledger (JSON array or JSONL) into validated `RunRecord`s, reusing the orchestrator's field names. | `ledger.py`, `models.py::RunRecord` | `test_load_json_array`, `test_extra_fields_ignored_for_interop` | `pytest -k "load_json or extra_fields"` |
| C2 | Malformed records (e.g. PASS with return_code≠0) are rejected, not dropped. | `models.py::RunRecord._pass_needs_rc0`, `ledger.py` | `test_bad_record_is_reported_not_dropped`, `test_pass_requires_return_code_zero` | `pytest -k "bad_record or return_code_zero"` |
| C3 | Failure clusters group FAIL runs by shared property/return-code signature; singletons are not clusters. | `analysis.py::failure_clusters` | `test_failure_cluster_groups_shared_signature`, `test_single_failure_is_not_a_cluster` | `pytest -k failure_cluster` |
| C4 | Timeout clusters group TIMEOUT runs by config; a TIMEOUT is never a PASS. | `analysis.py::timeout_clusters` | `test_timeout_cluster_by_config`, `test_timeout_never_classified_as_pass` | `pytest -k timeout` |
| C5 | Duplicate detection via signature hashing distinguishes exact (repeated seed) from near (seed-only) duplicates. | `analysis.py::duplicate_jobs` | `test_exact_duplicate_detected`, `test_near_duplicate_only_by_seed_is_low`, `test_distinct_inputs_are_not_duplicates` | `pytest -k duplicate` |
| C6 | Runtime & memory regressions use robust-z (median/MAD) + a min-ratio gate vs a per-job baseline; stable jobs do not fire; a timeout does not poison the runtime baseline; a minimum baseline size is enforced. | `analysis.py::regression_alerts`, `stats.py` | `test_runtime_regression_fires`, `test_memory_regression_fires`, `test_no_regression_when_stable`, `test_regression_needs_min_baseline`, `test_timeout_does_not_poison_runtime_baseline` | `pytest -k regression` |
| C7 | Configuration-sensitivity flags benchmarks solved by some-but-not-all configs (HIGH) or with wide per-config runtime spread (MEDIUM); single-config benchmarks are not flagged. | `analysis.py::config_sensitivity` | `test_config_sensitivity_outcome`, `test_config_sensitivity_runtime_spread`, `test_single_config_is_not_sensitive` | `pytest -k config_sensitivity` |
| C8 | Reproducibility warnings flag jobs whose repeats disagree; PASS↔FAIL is HIGH, non-conclusive instability is MEDIUM; stable jobs are silent. | `analysis.py::reproducibility_warnings` | `test_flaky_pass_fail_is_high`, `test_pass_then_timeout_is_medium`, `test_stable_job_is_not_flaky` | `pytest -k "flaky or repro or stable_job"` |
| C9 | A single prioritized investigation queue ranks all findings deterministically with a recommended next step each. | `analysis.py::analyze` | `test_analyze_builds_sorted_queue` | `pytest -k sorted_queue` |
| C10 | The analysis reproduces a checked-in golden report on the bundled public ledger, exercising all 7 finding kinds. | `analysis.py`, `examples/golden_report.json` | `test_golden_report_matches`, `test_golden_covers_every_finding_kind` | `pytest -k golden` |
| C11 | The LLM layer is a deterministic offline mock that only narrates existing evidence and cites only real run IDs. | `explain.py::MockLLM` | `test_mock_llm_is_deterministic_and_grounded` | `pytest -k mock_llm` |
| C12 | CLI runs end-to-end (analyze/report/queue/explain/schema) on the bundled example. | `cli.py` | `test_cli_analyze_json`, `test_cli_queue`, `test_cli_report_markdown_and_explain`, `test_cli_schema_export` | `pytest -k cli` |

## Non-claims (no evidence, do not assert)

- No claim about any real formal tool's runtime, memory, flakiness, or accuracy.
- No root-cause determination for any finding.
- No learned/tuned thresholds; no statistical guarantee (false-positive rate) on
  real telemetry.
