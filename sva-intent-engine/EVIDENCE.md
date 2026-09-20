# Evidence

Each claim is tied to a source location, a test, and a reproduce command. Run
commands from the repo root inside the venv. Distinguishes **implementation
evidence** (what the code does) from experimental-performance evidence (none is
claimed in this phase).

Commit/tag: `TBD` (placeholder).

---

### C1 — Deterministic decomposition splits, classifies, and flags vague terms

- **Claim**: requirements are split into classified atomic clauses; vague terms
  are flagged; bounds/signals/clocks are never inferred.
- **Source**: `src/sva_intent_engine/decompose.py` (`decompose`, `_classify`,
  `_extract_bounds`, `_detect_vague`).
- **Tests**: `tests/test_decompose.py` (12 tests, incl.
  `test_flags_vague_terms_as_ambiguity`, `test_never_infers_missing_bound`,
  `test_never_infers_clock_or_reset`).
- **Reproduce**: `pytest tests/test_decompose.py -q`

### C2 — Ranked, deterministic symbol grounding; unresolved stops emission

- **Claim**: exact > case-insensitive > alias ranking; multiple matches kept;
  absent signals unresolved.
- **Source**: `src/sva_intent_engine/grounding.py` (`ground_clause`,
  `_match_term`); `src/sva_intent_engine/pipeline.py` (`build_intent` returns
  `None` when `not grounding.fully_resolved`).
- **Tests**: `tests/test_grounding.py` (9 tests);
  `tests/test_pipeline_cli.py::test_unresolved_term_blocks_emission`.
- **Reproduce**: `pytest tests/test_grounding.py tests/test_pipeline_cli.py -q`

### C3 — Safe SVA renderer with whitelist and safety rejections

- **Claim**: renders the listed forms; rejects absent clock, invalid timing,
  unknown reset polarity for reset-state, and unsafe expressions.
- **Source**: `src/sva_intent_engine/renderer.py` (`safe_expr`, `render`,
  `render_property`).
- **Tests**: `tests/test_renderer.py` (20 tests, incl.
  `test_render_rejects_absent_clock`, `test_safe_expr_rejects_system_task`,
  `test_reset_state_rejects_unknown_polarity`,
  `test_next_cycle_uses_non_overlapping`).
- **Reproduce**: `pytest tests/test_renderer.py -q`

### C4 — Golden temporal-intent JSON and rendered SVA for five examples

- **Claim**: the five public examples produce stable, grounded golden output.
- **Source**: `examples/golden_intent/*.json`, `examples/golden_sva/*.sva`;
  generator `scripts/gen_golden.py`.
- **Tests**: `tests/test_golden.py` (11 parametrized checks).
- **Reproduce**: `pytest tests/test_golden.py -q`

### C5 — CLI runs end to end offline

- **Claim**: `demo` and `ingest/ground/generate/validate` work with no LLM/network.
- **Source**: `src/sva_intent_engine/cli.py`.
- **Tests**: `tests/test_pipeline_cli.py` (`test_cli_demo_runs`,
  `test_cli_generate_end_to_end`, `test_cli_ingest_json`).
- **Reproduce**: `sva-intent demo` ; `pytest tests/test_pipeline_cli.py -q`

### C6 — Typed contracts validate and export to JSON Schema

- **Claim**: Pydantic v2 models validate (reject extra fields, bad ranges) and
  export JSON Schema.
- **Source**: `src/sva_intent_engine/models.py`,
  `src/sva_intent_engine/schema_export.py`; `schemas/*.schema.json`.
- **Tests**: `tests/test_models.py` (5), `tests/test_schema_and_llm.py` (2).
- **Reproduce**: `pytest tests/test_models.py tests/test_schema_and_llm.py -q`

### C7 — Mock-only LLM; deterministic path independent of any model

- **Claim**: no real LLM/network is used; the mock is inert.
- **Source**: `src/sva_intent_engine/llm_adapter.py`.
- **Tests**: `tests/test_schema_and_llm.py::test_mock_llm_is_deterministic_and_offline`.
- **Reproduce**: `pytest tests/test_schema_and_llm.py -q`

---

### C-interop — Consumes the canonical rtl-intent-ingestor manifest

- **Claim**: the engine grounds requirement terms and selects clock/reset against
  the REAL canonical RTL Intent Manifest produced by `rtl-intent-ingestor`
  (schema `rtl-intent` 0.1.0), not only its own fixture shape. `--manifest-format
  auto` (default) auto-detects canonical vs. engine fixture; the fixture format
  still works (back-compat). Producer widths kept as parameter text stay `null`
  (never guessed); heuristic reset polarity is carried into `signal_type`.
- **Source**: `src/sva_intent_engine/rtl_intent_adapter.py`
  (`from_rtl_intent_manifest`, `load_manifest`); `io_utils.load_manifest`; `cli.py`
  (`--manifest-format`). Fixture: `examples/rtl_manifests/valid_ready.canonical.json`
  (verbatim copy of `rtl-intent-ingestor/examples/expected/valid_ready.json`).
- **Tests**: `tests/test_rtl_intent_adapter.py`
  (`test_adapter_projects_canonical_manifest`,
  `test_adapter_width_unknown_for_parameter_range`,
  `test_auto_detect_selects_canonical_vs_fixture`,
  `test_grounding_end_to_end_against_canonical_manifest`,
  `test_grounding_blocks_on_unknown_term`).
- **Reproduce**: `pytest tests/test_rtl_intent_adapter.py -q`

---

## Not claimed (no evidence in this phase)

- Semantic correctness, completeness, or vacuity-freedom of any property.
- Any formal/simulation execution, mutation score, or coverage result.
- Any performance/scale benchmark.
