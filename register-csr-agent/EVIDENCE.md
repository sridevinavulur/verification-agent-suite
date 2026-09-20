# Evidence

Each claim is tied to source, a test, and a reproduce command. Run from repo
root inside the venv (`pip install -e ".[dev]"`).

| # | Claim | Source | Test | Reproduce |
|---|---|---|---|---|
| 1 | JSON & YAML parse to the same manifest | `parsers.py:_map_from_dict` | `test_parsers.py::test_json_and_yaml_agree` | `pytest -k json_and_yaml` |
| 2 | CSV groups rows into registers+fields | `parsers.py:_parse_csv` | `test_parsers.py::test_csv_grouping_and_fields` | `register-csr normalize examples/register_maps/gpio_block.csv` |
| 3 | Markdown pipe table parses | `parsers.py:_parse_markdown` | `test_parsers.py::test_markdown_table_parse` | `register-csr normalize examples/register_maps/uart_block.md` |
| 4 | Unknown access token rejected (no invention) | `parsers.py:_parse_access` | `test_parsers.py::test_unknown_access_rejected` | `pytest -k unknown_access` |
| 5 | Field reset overflow rejected | `models.py:Field_._reset_fits` | `test_parsers.py::test_field_reset_overflow_rejected` | `pytest -k reset_overflow` |
| 6 | Clean map yields zero errors | `checks.py:run_all_checks` | `test_checks.py::test_clean_map_has_no_errors` | `register-csr check examples/register_maps/timer_block.yaml` |
| 7 | Buggy map catches all defect families | `checks.py` (all) | `test_checks.py::test_buggy_map_catches_all_defect_families` | `register-csr check examples/register_maps/buggy_block.json` |
| 8 | Duplicate address detected | `checks.py:check_address_uniqueness_and_alignment` | `test_checks.py::test_address_dup_detected` | `pytest -k address_dup` |
| 9 | Reset-vs-field-sum math correct | `checks.py:check_reset_value_consistency` | `test_checks.py::test_reset_field_sum_math` | `pytest -k reset_field_sum` |
| 10 | Grounding exact matches, reports unmatched | `grounding.py:ground` | `test_grounding_and_generators.py::test_grounding_exact_and_unmatched` | `register-csr ground examples/register_maps/timer_block.yaml examples/rtl_symbols/timer_block.json` |
| 11 | RTL Intent Manifest ingest (INTEROP) | `rtl_symbols.py:_load_intent_manifest` | `test_grounding_and_generators.py::test_grounding_intent_manifest_source` | `register-csr ground examples/register_maps/timer_block.json examples/rtl_symbols/timer_block.intent.json` |
| 12 | No false-positive grounding | `grounding.py:ground` | `test_grounding_and_generators.py::test_grounding_no_false_positive` | `pytest -k no_false_positive` |
| 13 | SVA always `candidate`, covers access types | `generators.py:generate_sva` | `test_grounding_and_generators.py::test_sva_all_candidate_and_covers_access_types` | `register-csr generate examples/register_maps/timer_block.yaml` |
| 14 | LLM cannot change code/severity | `llm_adapter.py:annotate_discrepancies` | `test_grounding_and_generators.py::test_llm_cannot_change_code_or_severity` | `pytest -k llm_cannot` |
| 15 | LLM cannot fabricate discrepancies | `llm_adapter.py` | `test_grounding_and_generators.py::test_llm_does_not_fabricate_discrepancies` | `pytest -k does_not_fabricate` |
| 16 | Golden SVA / discrepancies / coverage stable | `renderer.py` | `test_golden_and_cli.py::test_golden_*` | `pytest -k golden` |
| 17 | CLI exits 1 on ERROR | `cli.py:check` | `test_golden_and_cli.py::test_cli_check_exits_nonzero_on_error` | `register-csr check examples/register_maps/buggy_block.json; echo $?` |
| 18 | `package` writes all artifacts + provenance | `cli.py:package` | `test_golden_and_cli.py::test_cli_package_writes_artifacts` | `register-csr package examples/register_maps/timer_block.yaml examples/rtl_symbols/timer_block.json --out /tmp/p` |

## Full-suite reproduction

```bash
ruff check .          # clean
pytest                # 29 passed
register-csr demo     # clean=0 errors, buggy=7 errors
```
