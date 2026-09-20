# Constraint Hygiene Report

> **STATIC HYGIENE ONLY. Absence of a flagged contradiction does NOT mean the constraint set is sound or that any proof is valid. All findings are static suspicions requiring human review; no assumption may be changed without human approval.**

- Tool: `constraint-hygiene-agent` v0.1.0
- Top module: `handshake_dut`
- Inputs: examples/bad/bad_constraints.sva, examples/dut_manifest.json

## Assumption inventory

| Name | Line | Signals | Expr |
|---|---|---|---|
| am_valid_true | 15 | in_valid | `in_valid` |
| am_valid_false | 16 | in_valid | `!in_valid` |
| am_mode_a | 19 | mode | `mode == 2'b01` |
| am_mode_b | 20 | mode | `mode == 2'b10` |
| am_force_out_valid | 23 | out_valid | `out_valid` |
| am_force_in_ready | 24 | in_ready | `in_ready` |
| am_force_state | 27 | state | `state == 2'b00` |
| am_force_count | 28 | fifo_count | `fifo_count == 0` |
| am_unused | 31 | spare_in | `spare_in == 0` |
| am_unknown | 34 | ghost_sig | `ghost_sig` |

## Signal ownership classification (10 signals)

| Signal | Ownership | Rationale |
|---|---|---|
| fifo_count | internal_state | 'fifo_count' is a register/internal net inside the DUT (not a boundary port). |
| ghost_sig | unknown | 'ghost_sig' not found among manifest ports or internal signals. |
| in_data | environment_input | 'in_data' is an input port of top module 'handshake_dut'. |
| in_ready | dut_output | 'in_ready' is an output port of top module 'handshake_dut'. |
| in_valid | environment_input | 'in_valid' is an input port of top module 'handshake_dut'. |
| mode | environment_input | 'mode' is an input port of top module 'handshake_dut'. |
| out_data | dut_output | 'out_data' is an output port of top module 'handshake_dut'. |
| out_valid | dut_output | 'out_valid' is an output port of top module 'handshake_dut'. |
| spare_in | environment_input | 'spare_in' is an input port of top module 'handshake_dut'. |
| state | internal_state | 'state' is a register/internal net inside the DUT (not a boundary port). |

## Contradiction candidates

| Code | Severity | Confidence | Message |
|---|---|---|---|
| CONSTANT_CONFLICT | error | static_suspicion | Assumptions 'am_mode_a' and 'am_mode_b' impose conflicting values on 'mode' (1 vs 2). |
| CONTRADICTION | error | static_suspicion | Assumptions 'am_valid_true' and 'am_valid_false' impose conflicting values on 'in_valid' (1 vs 0). |

## Unused assumption candidates

| Code | Severity | Confidence | Message |
|---|---|---|---|
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_force_count' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_force_in_ready' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_force_out_valid' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_force_state' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_mode_a' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_mode_b' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_unknown' constrains signals not referenced by any assertion or cover. |
| UNUSED_ASSUMPTION | warning | static_suspicion | Assumption 'am_unused' constrains signals not referenced by any assertion or cover. |

## Output / internal-state constraint warnings

| Code | Severity | Confidence | Message |
|---|---|---|---|
| INTERNAL_STATE_CONSTRAINT | warning | static_suspicion | Assumption 'am_force_count' constrains DUT INTERNAL STATE (a register/internal net). |
| INTERNAL_STATE_CONSTRAINT | warning | static_suspicion | Assumption 'am_force_state' constrains DUT INTERNAL STATE (a register/internal net). |
| OUTPUT_CONSTRAINT | error | static_suspicion | Assumption 'am_force_in_ready' constrains a DUT OUTPUT. |
| OUTPUT_CONSTRAINT | error | static_suspicion | Assumption 'am_force_out_valid' constrains a DUT OUTPUT. |
| UNKNOWN_SIGNAL | warning | static_suspicion | Assumption 'am_unknown' constrains a signal that could not be classified from the manifest. |

## Property dependency map

| Property | Signal | Constrained by assumptions |
|---|---|---|
| as_data_pipe | in_data | - |
| as_data_pipe | in_valid | am_valid_false, am_valid_true |
| as_data_pipe | out_data | - |

## Vacuity / reachability recommendations

| Code | Severity | Confidence | Message |
|---|---|---|---|
| VACUITY_RISK | error | static_suspicion | 2 contradiction candidate(s) present: high vacuity risk for ALL assertions under these assumptions. |
| REACHABILITY_RISK | info | static_suspicion | Assertion 'as_data_pipe' has no paired cover exercising its signals. |
| VACUITY_RISK | info | static_suspicion | Reminder: a clean hygiene report is NOT a soundness or validity result. |

## Human-review queue

| Priority | Subject | Reason | Findings |
|---|---|---|---|
| P1 | <constraint-set> | 2 contradiction candidate(s) present: high vacuity risk for ALL assertions under these assumptions. | VACUITY_RISK |
| P1 | am_force_in_ready | Assumption 'am_force_in_ready' constrains a DUT OUTPUT.; Assumption 'am_force_in_ready' constrains signals not referenced by any assertion or cover. | OUTPUT_CONSTRAINT, UNUSED_ASSUMPTION |
| P1 | am_force_out_valid | Assumption 'am_force_out_valid' constrains a DUT OUTPUT.; Assumption 'am_force_out_valid' constrains signals not referenced by any assertion or cover. | OUTPUT_CONSTRAINT, UNUSED_ASSUMPTION |
| P1 | am_mode_a | Assumption 'am_mode_a' constrains signals not referenced by any assertion or cover.; Assumptions 'am_mode_a' and 'am_mode_b' impose conflicting values on 'mode' (1 vs 2). | CONSTANT_CONFLICT, UNUSED_ASSUMPTION |
| P1 | am_valid_true | Assumptions 'am_valid_true' and 'am_valid_false' impose conflicting values on 'in_valid' (1 vs 0). | CONTRADICTION |
| P2 | am_force_count | Assumption 'am_force_count' constrains DUT INTERNAL STATE (a register/internal net).; Assumption 'am_force_count' constrains signals not referenced by any assertion or cover. | INTERNAL_STATE_CONSTRAINT, UNUSED_ASSUMPTION |
| P2 | am_force_state | Assumption 'am_force_state' constrains DUT INTERNAL STATE (a register/internal net).; Assumption 'am_force_state' constrains signals not referenced by any assertion or cover. | INTERNAL_STATE_CONSTRAINT, UNUSED_ASSUMPTION |
| P2 | am_unknown | Assumption 'am_unknown' constrains a signal that could not be classified from the manifest.; Assumption 'am_unknown' constrains signals not referenced by any assertion or cover. | UNKNOWN_SIGNAL, UNUSED_ASSUMPTION |
| P3 | am_mode_b | Assumption 'am_mode_b' constrains signals not referenced by any assertion or cover. | UNUSED_ASSUMPTION |
| P3 | am_unused | Assumption 'am_unused' constrains signals not referenced by any assertion or cover. | UNUSED_ASSUMPTION |
| P3 | as_data_pipe | Assertion 'as_data_pipe' has no paired cover exercising its signals. | REACHABILITY_RISK |
