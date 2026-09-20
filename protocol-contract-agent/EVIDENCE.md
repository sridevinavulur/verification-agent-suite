# Evidence

Each claim is tied to source, a test, and a reproduce command. All commands run
from the repo root in the project venv. No experimental-performance claims are
made — this is an implementation-evidence document.

Reproduce the whole suite:

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/pytest
```

| ID | Claim | Source | Test | Reproduce |
|----|-------|--------|------|-----------|
| C1 | Consumes a real canonical RTL Intent Manifest subset (ignores unmodeled fields) | `models.py::RtlManifest` (`extra="ignore"`) | `test_models.py::test_manifest_view_ignores_extra_fields` | `pytest -k manifest_view` |
| C2 | Generates a full contract for all 5 protocols from bundled examples | `generator.py::generate_contract`, `templates.py` | `test_generator.py::test_generate_all_examples` | `protocol-contract demo` |
| C3 | Every property references only grounded RTL symbols (stable IDs) | `grounding.py`, `generator.py::_all_referenced_grounded` | `test_generator.py::test_every_property_is_grounded` | `pytest -k grounded` |
| C4 | No silently-added assumptions: assume-on-non-input is flagged | `templates.py::_assume_env` | `test_generator.py::test_assume_never_silently_constrains_output` | `pytest -k assume` |
| C5 | Output vs input ownership decides assert vs assume | `grounding.py::ground_signal`, `templates.py::valid_ready` | `test_generator.py::test_output_role_produces_guarantee_not_assumption`, `::test_input_valid_produces_assumption` | `pytest -k ownership or -k valid` |
| C6 | Reset polarity never inferred by name; unknown polarity skips properties | `grounding.py::resolve_reset`, `sva.py::disable_iff` | `test_grounding.py::test_resolve_reset_uses_manifest_polarity_not_name`, `test_generator.py::test_unknown_reset_polarity_skips_polarity_properties` | `pytest -k reset` |
| C7 | Multiple outstanding entries modeled with real count + explicit depth | `templates.py::fifo`, `::credit` | `test_generator.py::test_fifo_models_multiple_outstanding_not_single`, `::test_credit_no_send_without_credit_is_assert` | `pytest -k outstanding or -k credit` |
| C8 | Cycle bounds never invented (omitted with warning) | `templates.py::req_grant` | `test_generator.py::test_no_latency_bound_omits_grant_latency` | `pytest -k latency` |
| C9 | Safe SVA rendering rejects injection / unsafe syntax | `sva.py::safe_expr` | `test_sva.py::test_safe_expr_rejects_unsafe` | `pytest tests/test_sva.py` |
| C10 | Property-mutation operators change property meaning; suite is mutable | `mutation.py` | `test_mutation.py::test_generated_properties_are_mutable`, `::test_no_two_distinct_properties_collide_after_mutation` | `pytest tests/test_mutation.py` |
| C11 | Deterministic golden SVA output (regression-locked) | `report.py::render_sva_file`, `examples/golden_contracts/*.sva` | `test_golden_and_cli.py::test_golden_sva_matches` | `pytest -k golden` |
| C12 | CLI runs end to end (protocols/generate/demo/mutate/export-schemas) | `cli.py` | `test_golden_and_cli.py::test_cli_*` | `pytest -k cli` |
| C13 | Emits candidate SVA in sva-intent-engine style, labeled candidate | `sva.py::wrap`, `report.py` | golden files + `test_cli_generate_json_out` | `protocol-contract generate examples/specs/valid_ready.json examples/rtl_manifests/valid_ready.json -f sva` |
| C14 | JSON Schema export for public contracts | `schema_export.py` | `test_golden_and_cli.py::test_cli_export_schemas` | `protocol-contract export-schemas schemas` |

## Result vocabulary used

Only implementation-level statements are made: "property compiled" is **not**
claimed (no compiler is run here); no PASS/proven/FAIL is produced because no
formal tool is invoked. All generated properties are labeled **candidate**.

## Not claimed
- No property is verified, proven, vacuity-checked, or signoff-ready.
- No performance, scalability, or bug-detection-rate numbers.
- No claim that user-supplied role bindings are correct.
