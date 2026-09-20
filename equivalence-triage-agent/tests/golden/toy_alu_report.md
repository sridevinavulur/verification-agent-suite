# Equivalence Mismatch-Localization Report

- **Reference design:** `ref_alu`
- **Revised design:** `rev_alu`
- **Reported status (from tool, echoed):** `NOT_EQUIVALENT`
- **Compare points:** 9 matched / 13 total
- **Distinct mismatch points:** 5
- **Mismatch groups (deduplicated):** 3

> This report echoes the equivalence tool's own status; it does **not** independently prove equivalence or non-equivalence. All likely-cause entries are **heuristic**.

## Status evidence

- `examples/toy_alu/equivalence.eqlog: status: NOT_EQUIVALENT`
- `examples/toy_alu/equivalence.eqlog: compare_points: 9/13`

## Warnings

- Configuration/constraint differences detected between runs; these are surfaced in config_deltas and may explain mismatches.

## Configuration / constraint deltas

| Key | Reference | Revised | Differs |
| --- | --- | --- | --- |
| `reset_polarity` | active_low | active_high | YES |
| `abstraction` | none | none | no |

## Reset / initialization comparison

- Reference reset: signal=`rst_n`, polarity=active_low, sync=asynchronous
- Revised reset:   signal=`rst`, polarity=active_high, sync=synchronous
- Polarity differs: YES
- Sync differs: YES
- Init-value differences:
  - `result`: ref=00 != rev=0
- Reset polarity differs: ref=active_low, rev=active_high.
- Reset synchronization differs: ref=asynchronous, rev=synchronous.

## Mismatch groups

### Group 1 (x2) -- kind: output

- **Signature:** `output|same|result|result|a,b,op`
- **Members:** `result[7]`, `result[6]`
- **Mismatch cone:** `a`, `b`, `op`, `result[7]`, `result[6]`

**Likely causes (heuristic):**

- `polarity` (confidence 0.75, heuristic): Counterexample shows consistently inverted values (1 bit-pairs inverted); suggests polarity/inversion mismatch.
- `config_constraint` (confidence 0.50, heuristic): Run configuration/constraints differ (reset_polarity); mismatches may be an artifact of setup, not RTL.
- `reset_init` (confidence 0.40, heuristic): Reset/init behavior differs between designs.

**Ranked source locations for review:**

| Rank | Signal | Design | Location | Score | Reasons |
| --- | --- | --- | --- | --- | --- |
| 1 | `result[6]` | reference | ref_alu.v:10:22 [ref_alu] | 4.0 | direct compare point; in mismatch cone |
| 2 | `result[7]` | reference | ref_alu.v:10:22 [ref_alu] | 4.0 | direct compare point; in mismatch cone |
| 3 | `result[6]` | revised | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 4 | `result[7]` | revised | (no source-map entry) | 4.0 | direct compare point; in mismatch cone |
| 5 | `a` | reference | ref_alu.v:8:23 [ref_alu] | 1.0 | in mismatch cone |
| 6 | `b` | reference | ref_alu.v:9:23 [ref_alu] | 1.0 | in mismatch cone |
| 7 | `op` | reference | ref_alu.v:10:23 [ref_alu] | 1.0 | in mismatch cone |
| 8 | `a` | revised | (no source-map entry) | 1.0 | in mismatch cone |
| 9 | `b` | revised | (no source-map entry) | 1.0 | in mismatch cone |
| 10 | `op` | revised | (no source-map entry) | 1.0 | in mismatch cone |

### Group 2 (x2) -- kind: output

- **Signature:** `output|same|result||a,b,op`
- **Members:** `result[5]`, `result[4]`
- **Mismatch cone:** `a`, `b`, `op`

**Likely causes (heuristic):**

- `config_constraint` (confidence 0.50, heuristic): Run configuration/constraints differ (reset_polarity); mismatches may be an artifact of setup, not RTL.
- `reset_init` (confidence 0.40, heuristic): Reset/init behavior differs between designs.

**Ranked source locations for review:**

| Rank | Signal | Design | Location | Score | Reasons |
| --- | --- | --- | --- | --- | --- |
| 1 | `result[4]` | reference | (no source-map entry) | 3.0 | direct compare point |
| 2 | `result[5]` | reference | (no source-map entry) | 3.0 | direct compare point |
| 3 | `result[4]` | revised | (no source-map entry) | 3.0 | direct compare point |
| 4 | `result[5]` | revised | (no source-map entry) | 3.0 | direct compare point |
| 5 | `a` | reference | ref_alu.v:8:23 [ref_alu] | 1.0 | in mismatch cone |
| 6 | `b` | reference | ref_alu.v:9:23 [ref_alu] | 1.0 | in mismatch cone |
| 7 | `op` | reference | ref_alu.v:10:23 [ref_alu] | 1.0 | in mismatch cone |
| 8 | `a` | revised | (no source-map entry) | 1.0 | in mismatch cone |
| 9 | `b` | revised | (no source-map entry) | 1.0 | in mismatch cone |
| 10 | `op` | revised | (no source-map entry) | 1.0 | in mismatch cone |

### Group 3 (x1) -- kind: state

- **Signature:** `state|w8!=w4|result_reg|result,rst_n|rst,rst_n`
- **Members:** `result_reg`
- **Widths:** ref=8, rev=4
- **Mismatch cone:** `rst_n`, `rst`, `result`

**Likely causes (heuristic):**

- `width` (confidence 0.90, heuristic): Compare point width differs: ref=8 bits vs rev=4 bits.
- `polarity` (confidence 0.60, heuristic): Reset polarity differs between designs and a reset-like signal is in the mismatch cone.
- `reset_init` (confidence 0.60, heuristic): Reset/init behavior differs between designs and first difference occurs at t=0.
- `config_constraint` (confidence 0.50, heuristic): Run configuration/constraints differ (reset_polarity); mismatches may be an artifact of setup, not RTL.

**Ranked source locations for review:**

| Rank | Signal | Design | Location | Score | Reasons |
| --- | --- | --- | --- | --- | --- |
| 1 | `result` | reference | ref_alu.v:10:22 [ref_alu] | 4.0 | direct compare point; in mismatch cone |
| 2 | `result` | revised | rev_alu.v:12:22 [rev_alu] | 4.0 | direct compare point; in mismatch cone |
| 3 | `rst` | reference | (no source-map entry) | 1.0 | in mismatch cone |
| 4 | `rst_n` | reference | ref_alu.v:7:23 [ref_alu] | 1.0 | in mismatch cone |
| 5 | `rst` | revised | rev_alu.v:8:23 [rev_alu] | 1.0 | in mismatch cone |
| 6 | `rst_n` | revised | (no source-map entry) | 1.0 | in mismatch cone |

## Reproducible debug packet

- **Repro command:** `eq-triage demo toy_alu`
- **Input files:**
- **Focus compare points:** `result[7]`, `result[6]`, `result[5]`, `result[4]`, `result_reg`
- **Focus signals:** `result[6]`, `result[7]`, `result[4]`, `result[5]`, `result`, `rst`
- **Suggested next steps:**
  1. Reconcile configuration/constraint differences BEFORE debugging RTL -- mismatches may be a setup artifact.
  1. Re-run equivalence check with the same tool/version to confirm reproducibility.
  1. Inspect the ranked source locations for the top mismatch group.
  1. Compare reset/init sequences of both designs on the failing compare points.

## Provenance

- tool: `eq-triage` v`0.1.0` (schema `0.1.0`)
- command: `eq-triage demo toy_alu`
- git_sha: `GOLDEN`

