# Equivalence Mismatch-Localization Report

- **Reference design:** `ref_fsm`
- **Revised design:** `rev_fsm`
- **Reported status (from tool, echoed):** `NOT_EQUIVALENT`
- **Compare points:** 3 matched / 5 total
- **Distinct mismatch points:** 3
- **Mismatch groups (deduplicated):** 2

> This report echoes the equivalence tool's own status; it does **not** independently prove equivalence or non-equivalence. All likely-cause entries are **heuristic**.

## Status evidence

- `examples/toy_counter/equivalence.eqlog: status: NOT_EQUIVALENT`
- `examples/toy_counter/equivalence.eqlog: compare_points: 3/5`

## Configuration / constraint deltas

| Key | Reference | Revised | Differs |
| --- | --- | --- | --- |
| `abstraction` | none | none | no |

## Reset / initialization comparison

- Reference reset: signal=`rst_n`, polarity=active_low, sync=asynchronous
- Revised reset:   signal=`rst_n`, polarity=active_low, sync=asynchronous
- Polarity differs: no
- Sync differs: no
- Init-value differences:
  - `state_r`: ref=00 != rev=001

## Mismatch groups

### Group 1 (x2) -- kind: output

- **Signature:** `output|same|state|state|en,state_r`
- **Members:** `state[0]`, `state[1]`
- **Mismatch cone:** `en`, `state_r`, `state[0]`, `state[1]`

**Likely causes (heuristic):**

- `polarity` (confidence 0.75, heuristic): Counterexample shows consistently inverted values (1 bit-pairs inverted); suggests polarity/inversion mismatch.
- `state_encoding` (confidence 0.65, heuristic): State signal 'state_r' encoding differs: ref=binary, rev=onehot.
- `gating` (confidence 0.55, heuristic): Enable/gating-like signal(s) in cone: en -- check clock-gating / enable-condition changes.

**Ranked source locations for review:**

| Rank | Signal | Design | Location | Score | Reasons |
| --- | --- | --- | --- | --- | --- |
| 1 | `state[0]` | reference | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 2 | `state[1]` | reference | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 3 | `state[0]` | revised | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 4 | `state[1]` | revised | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 5 | `en` | reference | ref_fsm.v:7:18 [ref_fsm] | 1.5 | in mismatch cone; implicated by gating |
| 6 | `en` | revised | rev_fsm.v:7:18 [rev_fsm] | 1.5 | in mismatch cone; implicated by gating |
| 7 | `state_r` | reference | ref_fsm.v:10:5 [ref_fsm] | 1.0 | in mismatch cone |
| 8 | `state_r` | revised | rev_fsm.v:10:5 [rev_fsm] | 1.0 | in mismatch cone |

### Group 2 (x1) -- kind: state

- **Signature:** `state|w2!=w3|state_r|state|en,rst_n`
- **Members:** `state_r`
- **Widths:** ref=2, rev=3
- **Mismatch cone:** `en`, `rst_n`, `state`

**Likely causes (heuristic):**

- `width` (confidence 0.90, heuristic): Compare point width differs: ref=2 bits vs rev=3 bits.
- `state_encoding` (confidence 0.65, heuristic): State signal 'state' encoding differs: ref=binary, rev=onehot.
- `reset_init` (confidence 0.60, heuristic): Reset/init behavior differs between designs and first difference occurs at t=0.
- `gating` (confidence 0.55, heuristic): Enable/gating-like signal(s) in cone: en -- check clock-gating / enable-condition changes.

**Ranked source locations for review:**

| Rank | Signal | Design | Location | Score | Reasons |
| --- | --- | --- | --- | --- | --- |
| 1 | `state` | reference | ref_fsm.v:8:18 [ref_fsm] | 4.0 | direct compare point; in mismatch cone |
| 2 | `state` | revised | rev_fsm.v:8:18 [rev_fsm] | 4.0 | direct compare point; in mismatch cone |
| 3 | `en` | reference | ref_fsm.v:7:18 [ref_fsm] | 1.5 | in mismatch cone; implicated by gating |
| 4 | `en` | revised | rev_fsm.v:7:18 [rev_fsm] | 1.5 | in mismatch cone; implicated by gating |
| 5 | `rst_n` | reference | (no source-map entry) | 1.0 | in mismatch cone |
| 6 | `rst_n` | revised | (no source-map entry) | 1.0 | in mismatch cone |

## Reproducible debug packet

- **Repro command:** `eq-triage demo toy_counter`
- **Input files:**
- **Focus compare points:** `state[0]`, `state[1]`, `state_r`
- **Focus signals:** `state[0]`, `state[1]`, `state`, `en`
- **Suggested next steps:**
  1. Re-run equivalence check with the same tool/version to confirm reproducibility.
  1. Inspect the ranked source locations for the top mismatch group.
  1. Compare reset/init sequences of both designs on the failing compare points.

## Provenance

- tool: `eq-triage` v`0.1.0` (schema `0.1.0`)
- command: `eq-triage demo toy_counter`
- git_sha: `GOLDEN`

