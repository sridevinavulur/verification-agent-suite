# Threat Model

FormalFlow-Scout is a deterministic preprocessing tool with no LLM in its
analysis path, so classic prompt/hallucination risks are limited. The dominant
risks are **unsound reductions**, **parser gaps**, and **misreading a heuristic
as a proof**. This document enumerates them and the mitigations in the code.

## 1. Unsound cone-of-influence (false negative dependency)

**Risk:** the COI misses a real dependency, so a downstream proof over the slice
passes while the full design fails (a false PASS — the worst outcome).

**Mitigations:**
- Lexical RHS extraction is an **over-approximation** (superset of identifiers).
- `if/case` **branch-guard** signals are added to every assignment in the block
  (`verilog_parser._parse_body_statements`), so control dependencies are never
  dropped. Tested: `test_analyzer.test_counter_known_coi` asserts `en` (a guard)
  is in the COI.
- Anything unparsed is recorded in `unresolved`, never silently dropped.
- Black-box outputs become free inputs and raise `blackbox_in_coi`.

**Residual risk:** a construct the parser mis-parses *without* flagging could
drop an edge. Mitigation: constrained subset + explicit `unresolved` list;
review it before trusting a slice.

## 2. Unsound partitioning presented as a valid reduction

**Risk:** a partition is treated as a sound proof decomposition.

**Mitigations:** every `CandidatePartition.soundness == HEURISTIC`; every cut
emits an `UNPROVEN` `EnvironmentAssumption`; `unproven_cut_assumptions` risk is
raised; README/ARCHITECTURE state the non-claim explicitly. Tested:
`test_all_partitions_labeled_heuristic`.

## 3. Cross-clock-domain unsoundness

**Risk:** partitioning a multi-clock cone per clock without CDC assumptions.

**Mitigation:** `multi_clock_coi` **HIGH** soundness risk when the COI spans >1
clock domain. Tested: `test_two_clock_flags_multi_clock_risk`. The tool does not
claim CDC-clean.

## 4. Feedback-loop unsoundness

**Risk:** cutting inside a combinational/sequential cycle.

**Mitigation:** Tarjan SCC; cyclic SCCs raise
`combinational_or_sequential_cycle`. Tested: `test_fifo_has_sequential_cycle`.

## 5. Hallucinated / mis-grounded signals

**Risk:** a property references a signal that does not exist, or resolves to the
wrong node.

**Mitigation:** unresolved seeds are reported in `unresolved_seed_signals` and
counted in stats; the COI for them is empty and a `notes` warning is emitted.
Suffix matching resolves un-prefixed names **only when unambiguous** (a single
match); ambiguous names stay unresolved. Tested:
`test_unresolved_seed_is_reported_not_silently_dropped`.

## 6. Non-reproducible results

**Risk:** output varies across runs/machines, undermining evidence.

**Mitigations:** dense stable ids, sorted adjacency, ascending-id output,
id-order Tarjan. Provenance records tool version, input SHA-256, and command.
Tested: `test_deterministic_output`. The C++ core is cross-checked against
Python and only used if it produces the identical set.

## 7. Data leakage / public-safety

**Risk:** committing proprietary RTL, paths, or secrets.

**Mitigations:** only public toy RTL in `examples/`. `.gitignore` excludes venv,
build artifacts, and local reports. The example report is generated with
relative paths (no absolute filesystem paths). No network calls, no credentials.

## 8. C++ core divergence

**Risk:** the optional C++ core computes a different COI than Python.

**Mitigation:** the CLI runs both and uses C++ **only** if the sets are
identical; otherwise it warns and falls back to Python. Tested:
`test_cpp_bridge.test_cpp_agrees_with_python` (skips if not built).

## Result vocabulary

This tool emits structural analysis, not formal verdicts. It never emits
PASS/FAIL/PROVEN. It emits `SOUND` (over-approximation), `HEURISTIC`, and
`UNPROVEN` labels, plus soundness-risk flags. Downstream formal tools own
PASS/FAIL/TIMEOUT/ERROR/INCONCLUSIVE.
