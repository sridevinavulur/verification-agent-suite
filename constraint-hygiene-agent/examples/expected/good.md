# Constraint Hygiene Report

> **STATIC HYGIENE ONLY. Absence of a flagged contradiction does NOT mean the constraint set is sound or that any proof is valid. All findings are static suspicions requiring human review; no assumption may be changed without human approval.**

- Tool: `constraint-hygiene-agent` v0.1.0
- Top module: `handshake_dut`
- Inputs: examples/good/good_constraints.sva, examples/dut_manifest.json

## Assumption inventory

| Name | Line | Signals | Expr |
|---|---|---|---|
| am_mode_legal | 17 | mode | `mode == 2'b01` |
| am_reset_input | 20 | rst_n | `rst_n` |
| am_valid_input | 23 | in_valid | `in_valid` |

## Signal ownership classification (5 signals)

| Signal | Ownership | Rationale |
|---|---|---|
| in_ready | dut_output | 'in_ready' is an output port of top module 'handshake_dut'. |
| in_valid | environment_input | 'in_valid' is an input port of top module 'handshake_dut'. |
| mode | environment_input | 'mode' is an input port of top module 'handshake_dut'. |
| out_valid | dut_output | 'out_valid' is an output port of top module 'handshake_dut'. |
| rst_n | environment_input | 'rst_n' is an input port of top module 'handshake_dut'. |

## Contradiction candidates

_None flagged._

## Unused assumption candidates

_None flagged._

## Output / internal-state constraint warnings

_None flagged._

## Property dependency map

| Property | Signal | Constrained by assumptions |
|---|---|---|
| as_out_valid_stable | mode | am_mode_legal |
| as_out_valid_stable | out_valid | - |
| as_ready_when_valid | in_ready | - |
| as_ready_when_valid | in_valid | am_valid_input |
| co_out_valid_seen | mode | am_mode_legal |
| co_out_valid_seen | out_valid | - |
| co_ready_seen | in_ready | - |
| co_ready_seen | in_valid | am_valid_input |
| co_ready_seen | rst_n | am_reset_input |

## Vacuity / reachability recommendations

| Code | Severity | Confidence | Message |
|---|---|---|---|
| VACUITY_RISK | info | static_suspicion | Reminder: a clean hygiene report is NOT a soundness or validity result. |

## Human-review queue

_Queue empty. NOTE: an empty queue is not a soundness result._
