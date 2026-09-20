# Threat Model

Scope: a workflow coordinator that dispatches verification agents (mocked in
v0.1). The threats below are about the *coordinator's* integrity and safety, and
how the design mitigates each.

## 1. Hallucinated / ungrounded signal grounding

- **Risk:** a candidate property references a signal that does not exist in the
  design, producing a meaningless or trivially-true assertion.
- **Mitigation:** `validators.check_grounding` rejects any ungrounded term and any
  grounding to a symbol absent from the RTL manifest. Enforced before partition
  and before execution. Red-team: `test_ungrounded_property_is_rejected_not_executed`.

## 2. Ambiguous clock / reset

- **Risk:** temporal semantics are undefined without an unambiguous clock; reset
  exceptions with unknown polarity silently change meaning.
- **Mitigation:** `validators.check_clock_reset` rejects missing clock, non-candidate
  clocks, and unknown/ambiguous reset polarity. Red-team:
  `test_ambiguous_reset_property_is_rejected`.

## 3. "Compiles == correct" fallacy

- **Risk:** treating front-end syntax acceptance as semantic validity.
- **Mitigation:** `FormalResult.COMPILED` exists but the `RunRecord` validator
  forbids it as a run outcome; the supervisor never labels a property "valid".
  Red-team: `test_run_record_rejects_non_execution_result`.

## 4. Unsafe changes without human approval

- **Risk:** an agent changes assumptions, abstraction, budget, or proof scope and
  proceeds to execution unreviewed.
- **Mitigation:** mandatory human-approval checkpoint
  (`Supervisor._needs_human_approval` + `_approval_gate`) plus a second refusal in
  the orchestrator backend. Partition cut obligations also trigger the gate.
  Red-team: `test_gated_task_without_approval_is_blocked`,
  `test_partition_cut_assumptions_force_the_human_gate`,
  `test_orchestrator_refuses_unapproved_execution`.

## 5. State-machine bypass

- **Risk:** skipping ingestion/review/approval by jumping states.
- **Mitigation:** every move goes through `assert_transition`; anything outside
  `ALLOWED_TRANSITIONS` raises `ProhibitedTransition`. Red-team:
  `test_cannot_transition_created_to_execution`, `test_skipping_review_is_prohibited`.

## 6. Reward hacking / out-of-catalog solver tuning

- **Risk:** an agent invents an unbounded/unsafe solver configuration to force a
  pass.
- **Mitigation:** configs come only from the finite, versioned catalog
  (`catalog.get_config`); out-of-catalog ids raise `ConfigNotInCatalog`; field
  constraints forbid degenerate configs (e.g. `bmc_depth >= 1`). Red-team:
  `test_config_outside_catalog_is_rejected`, `test_cannot_build_config_with_zero_depth`.

## 7. Misclassifying inconclusive results as PASS

- **Risk:** reporting a TIMEOUT/ERROR/UNKNOWN as success.
- **Mitigation:** result vocabulary is preserved end-to-end; the packet reports the
  exact backend classification. Red-team: `test_timeout_is_not_reported_as_pass`,
  `test_error_result_is_surfaced_not_passed`.

## 8. Non-reproducibility

- **Risk:** unrepeatable runs; missing provenance.
- **Mitigation:** deterministic seeded mock backends (no network); append-only
  JSONL audit log with monotonic `seq`; `RunRecord` captures command, seed,
  tool/version, timing, memory, return code, artifacts, and rationale.

## 9. Leakage of proprietary content

- **Risk:** committing employer/customer RTL, internal tool names, or credentials.
- **Mitigation:** examples are public toy RTL only; no secrets in code or CI; see
  the data policy in `README.md`. `.gitignore` excludes local `artifacts/`.

## Residual limitations

The syntax gate is a smoke check, not a parser; the mock backends are illustrative;
partition proposals are heuristic. None of these are represented as sound.
