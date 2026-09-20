# Threat Model

Scope: a read-only analytics tool over formal-run ledgers. It does not execute
formal tools, modify designs, or make signoff decisions. The risks below are the
ones relevant to that role.

## 1. Hallucination / fabricated findings

- **Risk:** an LLM invents a cluster, a run ID, a status, or a root cause.
- **Mitigation:** the LLM never produces findings. All findings come from the
  deterministic engine. The `MockLLM` adapter consumes only fields already on the
  `Finding` and cites only its `member_run_ids`. `test_mock_llm_is_deterministic_
  and_grounded` asserts every cited run ID is present in the finding and that the
  output is deterministic.

## 2. Correlation mistaken for causation

- **Risk:** presenting a statistical/structural pattern as a proven root cause.
- **Mitigation:** every finding is `heuristic=True`, every summary and every
  explanation is tagged `HEURISTIC` and repeats "correlation is not causation".
  The recommended next step is always an *investigation*, never a fix or a config
  change.

## 3. Unsafe result classification

- **Risk:** treating a TIMEOUT/ERROR/INCONCLUSIVE as a PASS, or trusting a
  mislabeled record.
- **Mitigation:** `RunStatus` is the fixed shared vocabulary; `is_success` is
  true only for `PASS`. A `PASS` with non-zero `return_code` is rejected on
  ingest. A timeout's wall-time is excluded from runtime baselines
  (`test_timeout_does_not_poison_runtime_baseline`).

## 4. Silently dropping runs

- **Risk:** hiding a failed/malformed run makes the picture look healthier than
  it is.
- **Mitigation:** `load_ledger` raises with the offending `run_id` on any
  validation failure rather than skipping (`test_bad_record_is_reported_not_dropped`).

## 5. Non-reproducible analysis

- **Risk:** unstable output across runs/orderings undermines trust.
- **Mitigation:** the engine is a pure function; ordering is fully specified; a
  golden-output test pins the analysis. No wall-clock, RNG, or environment input
  affects findings.

## 6. Data leakage / proprietary content

- **Risk:** committing real telemetry, internal design/tool/host names, or paths.
- **Mitigation:** the only bundled data is a synthetic public toy ledger built by
  `scripts/make_fixtures.py` (generic names, placeholder SHAs). No secrets, no API
  keys, no network. See `RELEASE_CHECKLIST.md`.

## 7. Threshold gaming / false confidence

- **Risk:** hidden thresholds make findings look authoritative.
- **Mitigation:** all thresholds live in `analysis.Thresholds` as documented,
  overridable knobs, and each finding's `evidence` contains the numbers that
  fired it, so a reviewer can audit the decision.
