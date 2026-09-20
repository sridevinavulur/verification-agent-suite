# Evidence

Each resume-safe claim is tied to source, a test, and a reproduce command. This
is implementation evidence; no experimental-performance claims are made.

Environment: Python 3.11+, `pip install -e ".[dev]"`. Commit: `<PLACEHOLDER>`.

---

### CLAIM-1 — Real VCD parser for the common subset

- **Claim:** Parses `$timescale`/`$scope`/`$var`/`$enddefinitions`, `#time`, and
  scalar + vector value changes into a typed `WaveTrace`; rejects malformed input.
- **Source:** `src/cx_triage/parser.py` (`parse_vcd`, `parse_vcd_file`).
- **Tests:** `tests/test_parser.py::test_parse_vcd_basic_structure`,
  `::test_parse_vcd_scalar_and_vector_values`,
  `::test_parse_vcd_scope_qualification`, `::test_parse_vcd_x_z_normalized`,
  `::test_parse_vcd_real_values_skipped_not_crash`,
  `::test_parse_vcd_bad_timestamp_raises`,
  `::test_parse_vcd_malformed_var_raises`.
- **Reproduce:** `pytest tests/test_parser.py -q`

### CLAIM-2 — VCD and JSON traces are equivalent

- **Claim:** A VCD and a JSON trace of the same scenario yield an identical
  `WaveTrace` and an identical `TriageReport`.
- **Source:** `parser.py`, `triage.py`.
- **Tests:** `tests/test_parser.py::test_vcd_and_json_traces_equivalent`,
  `tests/test_report_golden.py::test_golden_json_structure`.
- **Reproduce:** `pytest tests/test_parser.py::test_vcd_and_json_traces_equivalent -q`

### CLAIM-3 — Antecedent activation and first-divergence detection

- **Claim:** Locates the first antecedent-activation cycle (skipping reset) and
  the first divergence for `|=>`/`|->` windows and for invariants.
- **Source:** `triage.py` (`find_antecedent_cycle`, `find_first_divergence`).
- **Tests:** `tests/test_triage.py::test_antecedent_and_divergence_cycles`
  (cycle 2 / cycle 6 on the toy benchmark),
  `::test_invariant_style_divergence`.
- **Reproduce:** `cx-triage demo` (see "Key cycles"), or
  `pytest tests/test_triage.py -q`

### CLAIM-4 — No design bug without evidence; alternatives retained

- **Claim:** A `design_bug` hypothesis is never emitted without trace-grounded
  evidence, and alternative categories are always retained.
- **Source:** `models.py` (`RootCauseHypothesis` validator),
  `triage.py` (`build_hypotheses`).
- **Tests:** `tests/test_models.py::test_design_bug_hypothesis_requires_evidence`,
  `tests/test_triage.py::test_alternatives_always_retained`,
  `::test_no_design_bug_when_antecedent_never_fires`,
  `::test_reset_active_at_divergence_yields_reset_hypothesis`.
- **Reproduce:** `pytest tests/test_models.py tests/test_triage.py -q`

### CLAIM-5 — Failing property is not necessarily a design bug

- **Claim:** For a failing property whose antecedent never fires, the top
  hypothesis is `environment_issue`, not `design_bug`.
- **Source:** `triage.py` (`build_hypotheses`); `examples/env_gap/`.
- **Test:** `tests/test_triage.py::test_no_design_bug_when_antecedent_never_fires`.
- **Reproduce:**
  `cx-triage triage --trace examples/env_gap/trace.json --failure examples/env_gap/failure.json`

### CLAIM-6 — Cone of influence + source citations

- **Claim:** Backward dependency traversal over the manifest includes the true
  bug source (`tb.stall`) and cites property + cone source locations.
- **Source:** `triage.py` (`compute_cone`, `build_citations`).
- **Tests:** `tests/test_triage.py::test_cone_includes_bug_source_stall`,
  `::test_citations_include_property_and_cone`.
- **Reproduce:** `cx-triage demo` (see "Relevant RTL cone" / "Source citations").

### CLAIM-7 — Golden, report-quality output

- **Claim:** The toy_counter Markdown and JSON reports are stable and match
  checked-in goldens.
- **Source:** `report.py`; `tests/golden/toy_counter_report.{md,json}`.
- **Tests:** `tests/test_report_golden.py::test_golden_markdown`,
  `::test_golden_json_structure`, `::test_mock_narrative_is_deterministic`.
- **Reproduce:** `pytest tests/test_report_golden.py -q`

### CLAIM-8 — Offline mock LLM adapter (no network in CI)

- **Claim:** The optional narrative is produced by a deterministic offline mock
  and is labeled advisory-only.
- **Source:** `src/cx_triage/llm.py` (`MockLLMAdapter`).
- **Test:** `tests/test_report_golden.py::test_mock_narrative_is_deterministic`.
- **Reproduce:** `cx-triage demo --narrate`

### CLAIM-9 — End-to-end CLI on a real VCD counterexample

- **Claim:** The CLI runs end-to-end on the bundled VCD and emits a triage report.
- **Source:** `src/cx_triage/cli.py`; `examples/toy_counter/counter_fail.vcd`.
- **Tests:** `tests/test_cli.py::test_demo_runs`, `::test_triage_writes_json`.
- **Reproduce:** `cx-triage demo`

### CLAIM-10 — Canonical RTL Intent Manifest interop (back-compatible)

- **Claim:** The manifest input accepts both the repo's native fixture and the
  canonical `rtl-intent-ingestor` schema; the canonical structure is projected
  onto the engine's symbol/driver model with fan-in edges reconstructed from
  continuous assigns and procedures (self-loops and foreign refs dropped), and
  the result drives the real cone traversal end-to-end.
- **Source:** `src/cx_triage/manifest_adapter.py` (`load_manifest`,
  `from_canonical_manifest`); fixture `examples/toy_counter/manifest_canonical.json`;
  schema read from `rtl-intent-ingestor/schemas/manifest.schema.json`.
- **Tests:** `tests/test_manifest_adapter.py::test_native_fixture_still_loads`,
  `::test_canonical_manifest_detected_and_projected`,
  `::test_canonical_unqualified_names`,
  `::test_canonical_manifest_drives_cone_traversal`,
  `::test_self_loop_dropped_and_foreign_refs_skipped`.
- **Reproduce:** `pytest tests/test_manifest_adapter.py -q`

### CLAIM-11 — Optional real-reproduction adapter degrades gracefully

- **Claim:** A clean `ReproExecutor` interface offers a deterministic default
  (no subprocess) and an optional Verilator/cocotb path that returns `SKIPPED`
  when Verilator is absent and never classifies a `SKIPPED`/`TIMEOUT`/`ERROR`
  outcome as a pass.
- **Source:** `src/cx_triage/executor.py`
  (`DeterministicExecutor`, `VerilatorReproExecutor`, `get_executor`). Verilator/
  cocotb sequence adapted (not imported) from `spec-to-cov-agent`
  `veri_forge/sim/{runner.py,verilator.py}`.
- **Tests:** `tests/test_executor.py::test_deterministic_executor_reproduces_present_artifacts`,
  `::test_deterministic_executor_errors_on_missing_artifacts`,
  `::test_deterministic_executor_errors_on_empty_trace`,
  `::test_verilator_executor_skips_when_absent`,
  `::test_verilator_executor_errors_on_missing_rtl`,
  `::test_get_executor_rejects_unknown_kind`.
- **Reproduce:** `pytest tests/test_executor.py -q`

### CLAIM-12 — Reproduction is advisory only; deterministic ranking authoritative

- **Claim:** Attaching a reproduction outcome (CRAVS-style structured-or-fallback
  composition) never re-orders, adds, or removes hypotheses and never adds
  evidence; a non-conclusive reproduction is surfaced transparently and never
  treated as a pass.
- **Source:** `src/cx_triage/compose.py` (`compose_report`, `advisory_hints_for`).
  Pattern adapted (not imported) from `spec-to-cov-agent`
  `veri_forge/cravs/integration.py`, with authority inverted.
- **Tests:** `tests/test_executor.py::test_compose_attaches_advisory_without_reranking`,
  `::test_compose_skip_is_never_a_pass_and_is_surfaced`,
  `::test_compose_not_reproduced_adds_caution_note`.
- **Reproduce:** `pytest tests/test_executor.py -q`, or
  `cx-triage triage --trace examples/toy_counter/counter_fail.vcd
  --failure examples/toy_counter/failure.json
  --manifest examples/toy_counter/manifest_canonical.json --reproduce`
