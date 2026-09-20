# Coverage Closure Triage Report

- Tool version: `0.1.0`
- Coverage format: `mock-cov-1.0` (heuristic triage; tool is authoritative)
- Seed: `0`
- Coverage items: 10  |  Holes: 9

## Metrics
- Valid proposal rate: 1.00
- Provenance completeness: 1.00
- Total recommendations: 20

## Coverage-Hole Classifications (ranked actions)

### `cov.arb.fsm.error` -- no_linked_test (fsm_state, arbiter)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - No test is even intended to reach this point (testplan gap).
  - No requirement maps to this point either (spec/plan gap).
- Evidence:
  - (coverage_db) cov.arb.fsm.error has hits=0 (goal=1) -> uncovered [cov.arb.fsm.error]
  - (test_manifest) No test lists cov.arb.fsm.error in its 'covers' set [cov.arb.fsm.error]
  - (requirement_matrix) No requirement maps to cov.arb.fsm.error [cov.arb.fsm.error]
- Ranked next actions (all require human approval):
  1. **add_directed_test** (priority 0.70, expected impact ~1 item(s)) -- No test targets this point; add a directed test to close the plan gap.
     - Next step: Create a directed test for arbiter ERROR state reached.
  2. **add_cover_property** (priority 0.65, expected impact ~1 item(s)) -- Add a cover property to make reaching this point observable.
     - Next step: Add a cover for cov.arb.fsm.error in arbiter.
  3. **request_spec_clarification** (priority 0.30, expected impact ~0 item(s)) -- No requirement maps here; confirm whether the point should be covered.
     - Next step: Ask whether cov.arb.fsm.error is in scope for this release.

### `cov.arb.fsm.grant2` -- test_ran_but_failed (fsm_state, arbiter)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Coverage may be blocked by a failing/aborted test; fix the failure first.
- Evidence:
  - (coverage_db) cov.arb.fsm.grant2 has hits=0 (goal=1) -> uncovered [cov.arb.fsm.grant2]
  - (test_manifest) Linked test t_arb_grant finished with status=fail (not a pass) [t_arb_grant]
  - (failure_log) t_arb_grant: failure: assertion arb_grant_within_3 failed at cycle 118 [rtl/arbiter.sv:34]
  - (requirement_matrix) cov.arb.fsm.grant2 maps to requirements ['REQ-ARB-1'] [cov.arb.fsm.grant2]
- Ranked next actions (all require human approval):
  1. **run_existing_test** (priority 0.90, expected impact ~1 item(s)) -- Re-run the failing linked test after the failure is triaged (by a human).
     - Next step: After fix, re-run t_arb_grant and re-measure coverage.
  2. **request_spec_clarification** (priority 0.30, expected impact ~0 item(s)) -- If the failure is a spec ambiguity, clarify intent before re-testing.
     - Next step: Ask spec owner whether cov.arb.fsm.grant2 behavior is as intended.

### `cov.cnt.stmt.dead` -- likely_unreachable (statement, counter)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Point may be structurally unreachable; inspect before proposing tests.
- Evidence:
  - (coverage_db) cov.cnt.stmt.dead has hits=0 (goal=1) -> uncovered [cov.cnt.stmt.dead]
  - (rtl_intent_manifest) counter:90 flagged as likely-unreachable [counter:90]
  - (requirement_matrix) No requirement maps to cov.cnt.stmt.dead [cov.cnt.stmt.dead]
- Ranked next actions (all require human approval):
  1. **inspect_unreachable_code** (priority 0.80, expected impact ~0 item(s)) -- Point is flagged likely-unreachable; confirm before spending test effort.
     - Next step: Inspect counter around line 90 for reachability.
  2. **request_waiver_review** (priority 0.40, expected impact ~1 item(s)) -- If confirmed unreachable, a human may review a waiver (agent never waives).
     - Next step: Route cov.cnt.stmt.dead to a waiver reviewer with the reachability finding.

### `cov.cnt.toggle.msb` -- test_ran_still_uncovered (toggle, counter)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Stimulus does not exercise this point; needs directed/constrained-random work.
- Evidence:
  - (coverage_db) cov.cnt.toggle.msb has hits=0 (goal=1) -> uncovered [cov.cnt.toggle.msb]
  - (test_manifest) Linked test t_cnt_random passed but cov.cnt.toggle.msb still uncovered [t_cnt_random]
  - (requirement_matrix) cov.cnt.toggle.msb maps to requirements ['REQ-CNT-1'] [cov.cnt.toggle.msb]
- Ranked next actions (all require human approval):
  1. **add_directed_test** (priority 0.70, expected impact ~1 item(s)) -- Passing test does not reach this point; a directed test likely will.
     - Next step: Draft a directed test hitting counter MSB toggle.
  2. **add_constrained_random_scenario** (priority 0.55, expected impact ~1 item(s)) -- Alternatively widen constrained-random stimulus to reach the point.
     - Next step: Add a CR scenario biasing toward toggle in counter.

### `cov.dbg.stmt.excluded` -- likely_unreachable (statement, counter)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Point may be structurally unreachable; inspect before proposing tests.
- Evidence:
  - (coverage_db) cov.dbg.stmt.excluded has hits=0 (goal=1) -> uncovered [cov.dbg.stmt.excluded]
  - (coverage_db) cov.dbg.stmt.excluded carries a coverage-exclusion pragma [cov.dbg.stmt.excluded]
  - (requirement_matrix) No requirement maps to cov.dbg.stmt.excluded [cov.dbg.stmt.excluded]
- Ranked next actions (all require human approval):
  1. **inspect_unreachable_code** (priority 0.80, expected impact ~0 item(s)) -- Point is flagged likely-unreachable; confirm before spending test effort.
     - Next step: Inspect counter around line 95 for reachability.
  2. **request_waiver_review** (priority 0.40, expected impact ~1 item(s)) -- If confirmed unreachable, a human may review a waiver (agent never waives).
     - Next step: Route cov.dbg.stmt.excluded to a waiver reviewer with the reachability finding.

### `cov.fifo.branch.empty` -- test_ran_still_uncovered (branch, fifo)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Stimulus does not exercise this point; needs directed/constrained-random work.
- Evidence:
  - (coverage_db) cov.fifo.branch.empty has hits=0 (goal=1) -> uncovered [cov.fifo.branch.empty]
  - (test_manifest) Linked test t_fifo_full passed but cov.fifo.branch.empty still uncovered [t_fifo_full]
  - (requirement_matrix) cov.fifo.branch.empty maps to requirements ['REQ-FIFO-1'] [cov.fifo.branch.empty]
- Ranked next actions (all require human approval):
  1. **add_directed_test** (priority 0.70, expected impact ~1 item(s)) -- Passing test does not reach this point; a directed test likely will.
     - Next step: Draft a directed test hitting fifo empty branch taken.
  2. **add_constrained_random_scenario** (priority 0.55, expected impact ~1 item(s)) -- Alternatively widen constrained-random stimulus to reach the point.
     - Next step: Add a CR scenario biasing toward branch in fifo.

### `cov.fifo.branch.overflow_guard` -- test_exists_not_run (branch, fifo)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - A test targeting this point exists but was never executed.
- Evidence:
  - (coverage_db) cov.fifo.branch.overflow_guard has hits=0 (goal=1) -> uncovered [cov.fifo.branch.overflow_guard]
  - (test_manifest) Linked test t_fifo_overflow has status=not_run [t_fifo_overflow]
  - (requirement_matrix) cov.fifo.branch.overflow_guard maps to requirements ['REQ-FIFO-2'] [cov.fifo.branch.overflow_guard]
- Ranked next actions (all require human approval):
  1. **run_existing_test** (priority 0.90, expected impact ~1 item(s)) -- Test t_fifo_overflow targets this point but was never run.
     - Next step: Run test t_fifo_overflow with seed=7 config=sim_default.

### `cov.hs.assert.req_grant` -- test_ran_still_uncovered (assertion, handshake)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - Stimulus does not exercise this point; needs directed/constrained-random work.
- Evidence:
  - (coverage_db) cov.hs.assert.req_grant has hits=0 (goal=1) -> uncovered [cov.hs.assert.req_grant]
  - (test_manifest) Linked test t_hs_basic passed but cov.hs.assert.req_grant still uncovered [t_hs_basic]
  - (requirement_matrix) cov.hs.assert.req_grant maps to requirements ['REQ-HS-1'] [cov.hs.assert.req_grant]
- Ranked next actions (all require human approval):
  1. **add_directed_test** (priority 0.70, expected impact ~1 item(s)) -- Passing test does not reach this point; a directed test likely will.
     - Next step: Draft a directed test hitting req eventually granted assertion cover.
  2. **add_constrained_random_scenario** (priority 0.55, expected impact ~1 item(s)) -- Alternatively widen constrained-random stimulus to reach the point.
     - Next step: Add a CR scenario biasing toward assertion in handshake.
  3. **propose_assertion_candidate** (priority 0.50, expected impact ~1 item(s)) -- Assertion coverage suggests a candidate property for human review.
     - Next step: Propose an assertion for req eventually granted assertion cover.

### `cov.misc.bin.orphan` -- no_linked_test (covergroup_bin, misc)
- Heuristic: True  |  Provenance complete: True
- Root-cause hypotheses:
  - No test is even intended to reach this point (testplan gap).
  - No requirement maps to this point either (spec/plan gap).
- Evidence:
  - (coverage_db) cov.misc.bin.orphan has hits=0 (goal=1) -> uncovered [cov.misc.bin.orphan]
  - (test_manifest) No test lists cov.misc.bin.orphan in its 'covers' set [cov.misc.bin.orphan]
  - (requirement_matrix) No requirement maps to cov.misc.bin.orphan [cov.misc.bin.orphan]
- Ranked next actions (all require human approval):
  1. **add_directed_test** (priority 0.70, expected impact ~1 item(s)) -- No test targets this point; add a directed test to close the plan gap.
     - Next step: Create a directed test for orphan covergroup bin with no plan mapping.
  2. **add_cover_property** (priority 0.65, expected impact ~1 item(s)) -- Add a cover property to make reaching this point observable.
     - Next step: Add a cover for cov.misc.bin.orphan in misc.
  3. **request_spec_clarification** (priority 0.30, expected impact ~0 item(s)) -- No requirement maps here; confirm whether the point should be covered.
     - Next step: Ask whether cov.misc.bin.orphan is in scope for this release.

## Independent-Measurement Manifest
The agent cannot claim closure. Re-measure coverage independently:
- `cov.arb.fsm.error`: After approved actions for cov.arb.fsm.error, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.arb.fsm.grant2`: After approved actions for cov.arb.fsm.grant2, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.cnt.stmt.dead`: After approved actions for cov.cnt.stmt.dead, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.cnt.toggle.msb`: After approved actions for cov.cnt.toggle.msb, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.dbg.stmt.excluded`: After approved actions for cov.dbg.stmt.excluded, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.fifo.branch.empty`: After approved actions for cov.fifo.branch.empty, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.fifo.branch.overflow_guard`: After approved actions for cov.fifo.branch.overflow_guard, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.hs.assert.req_grant`: After approved actions for cov.hs.assert.req_grant, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export
- `cov.misc.bin.orphan`: After approved actions for cov.misc.bin.orphan, re-export the coverage DB and confirm the item is covered. The agent does not and cannot mark it closed.
  - Verify covered when: hits >= goal in a fresh coverage export

## Human-Review Queue
- `cov.arb.fsm.error`: Heuristic category 'no_linked_test' with 3 proposed action(s) require human approval. Actions: [add_directed_test, add_cover_property, request_spec_clarification]
- `cov.arb.fsm.grant2`: Heuristic category 'test_ran_but_failed' with 2 proposed action(s) require human approval. Actions: [run_existing_test, request_spec_clarification]
- `cov.cnt.stmt.dead`: Heuristic category 'likely_unreachable' with 2 proposed action(s) require human approval. Actions: [inspect_unreachable_code, request_waiver_review]
- `cov.cnt.toggle.msb`: Heuristic category 'test_ran_still_uncovered' with 2 proposed action(s) require human approval. Actions: [add_directed_test, add_constrained_random_scenario]
- `cov.dbg.stmt.excluded`: Heuristic category 'likely_unreachable' with 2 proposed action(s) require human approval. Actions: [inspect_unreachable_code, request_waiver_review]
- `cov.fifo.branch.empty`: Heuristic category 'test_ran_still_uncovered' with 2 proposed action(s) require human approval. Actions: [add_directed_test, add_constrained_random_scenario]
- `cov.fifo.branch.overflow_guard`: Heuristic category 'test_exists_not_run' with 1 proposed action(s) require human approval. Actions: [run_existing_test]
- `cov.hs.assert.req_grant`: Heuristic category 'test_ran_still_uncovered' with 3 proposed action(s) require human approval. Actions: [add_directed_test, add_constrained_random_scenario, propose_assertion_candidate]
- `cov.misc.bin.orphan`: Heuristic category 'no_linked_test' with 3 proposed action(s) require human approval. Actions: [add_directed_test, add_cover_property, request_spec_clarification]

## Enforced Prohibited Actions
- NEVER: modify_rtl
- NEVER: auto_waive_coverage
- NEVER: change_coverage_scope
- NEVER: claim_closure_without_measurement
- NEVER: alter_tests_or_constraints

> Triage is heuristic; coverage-tool measurement remains authoritative. This run did not modify RTL, tests, constraints, scope, or waivers.
