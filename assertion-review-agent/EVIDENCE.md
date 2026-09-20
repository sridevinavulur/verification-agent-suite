# Evidence

Each claim is tied to source, tests, and a reproduce command. Tool version
0.1.0. Commit: `<PLACEHOLDER_SHA>`. Run all tests with:

```bash
pip install -e ".[dev]" && pytest
```

Current status: **57 tests pass, `ruff check .` clean.**

| ID | Claim | Source | Test(s) | Reproduce |
| --- | --- | --- | --- | --- |
| C1 | Parses a constrained SVA subset (clock, disable iff, `\|->`/`\|=>`, delays, named blocks, inline, comments) | `src/assertion_review/parser.py` | `tests/test_parser.py` | `pytest tests/test_parser.py` |
| C2 | Detects missing clock | `checks/static_checks.py::check_missing_clock` | `test_missing_clock` | `pytest -k missing_clock` |
| C3 | Detects missing/incorrect `disable iff` | `check_disable_iff` | `test_missing_disable_iff_warns_with_reset_candidate` | `pytest -k disable_iff` |
| C4 | Detects reset-polarity risk vs manifest | `check_reset_polarity` | `test_reset_polarity_*` (3) | `pytest -k reset_polarity` |
| C5 | Detects `\|->` vs `\|=>` mismatch risk | `check_implication_style` | `test_implication_style_risk` | `pytest -k implication_style` |
| C6 | Detects unbounded/ambiguous temporal ops | `check_unbounded_temporal` | `test_unbounded_temporal_dollar` | `pytest -k unbounded` |
| C7 | Detects weak/constant consequent | `check_weak_consequent` | `test_weak_consequent_constant_true` | `pytest -k weak_consequent` |
| C8 | Detects antecedent duplicated in consequent | `check_antecedent_in_consequent` | `test_antecedent_equals_consequent` | `pytest -k antecedent` |
| C9 | Detects trivially-passing assertions | `check_trivially_passing` | `test_trivially_passing_*` (2) | `pytest -k trivially` |
| C10 | Detects assumptions constraining outputs/internal state | `check_assume_constrains_output` | `test_assume_constrains_output_is_error`, `test_assume_on_input_is_ok` | `pytest -k assume` |
| C11 | Detects undeclared / mismatched-width signals | `check_signals` | `test_undeclared_signal`, `test_width_mismatch` | `pytest -k "undeclared or width"` |
| C12 | Flags property names not reflecting semantics | `check_name_semantics` | `test_name_semantics_*` (2) | `pytest -k name_semantics` |
| C13 | Reports requirement-traceability status | `checks/traceability.py` | `test_traceability_*` (2) | `pytest -k traceability` |
| C14 | Vacuity **RISK** heuristic, labelled heuristic (NOT complete detection) | `check_vacuity_risk` | `test_vacuity_risk_is_heuristic_only` | `pytest -k vacuity` |
| C15 | Emits a reviewer checklist | `review.py::build_checklist` | `test_checklist_marks_attention_items` | `pytest -k checklist` |
| C16 | Review-quality scoring rubric | `scoring.py`, `docs/SCORING_RUBRIC.md` | `test_score_*` (2) | `pytest -k score` |
| C17 | LLM layer only annotates; never alters findings | `llm.py::annotate_report` | `test_mock_llm_only_annotates_never_changes_findings` | `pytest -k annotate` |
| C18 | Golden findings over curated good/bad corpus | `examples/golden/*.json` | `tests/test_golden.py` | `pytest tests/test_golden.py` |
| C19 | End-to-end CLI (text/json, exit codes, --explain) | `cli.py` | `tests/test_cli_and_llm.py` | `pytest -k cli` |
| C20 | Consumes the **canonical** RTL Intent Manifest from `rtl-intent-ingestor` (adapter maps modules/ports/nets/clock+reset candidates to the reviewer model) | `src/assertion_review/rtl_intent_adapter.py::from_rtl_intent_manifest` | `test_adapter_projects_canonical_manifest`, `test_adapter_width_from_integer_range_only`, `test_from_rtl_intent_manifest_module_selection` | `pytest tests/test_rtl_intent_adapter.py` |
| C21 | `--manifest-format auto` auto-detects canonical vs. fixture; fixture format still works (back-compat) | `rtl_intent_adapter.py::load_manifest`, `cli.py`, `review.py::review_file` | `test_auto_detect_selects_canonical_vs_fixture`, `test_cli_paths_agree_on_canonical_manifest` | `pytest -k "auto_detect or cli_paths_agree"` |
| C22 | Reviewer grounds SVA identifiers against the canonical manifest (real interop: flags signals absent from the canonical fifo_queue design) | `review.py`, `examples/manifests/fifo_queue.canonical.json` (copy of `rtl-intent-ingestor/examples/expected/fifo_queue.json`) | `test_review_grounds_against_canonical_manifest` | `pytest -k grounds_against_canonical` |

## Experimental-performance evidence

None claimed. This is a static-analysis prototype; there are no solver runs,
benchmarks, or performance numbers. Do not cite formal-signoff or vacuity-proof
capability.
