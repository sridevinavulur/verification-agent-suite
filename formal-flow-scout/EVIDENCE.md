# Evidence

Each claim is tied to source, a test, and a reproduce command. Run all tests
with:

```bash
source .venv/bin/activate
pytest -q          # expect: 41 passed  (40 if C++ core not built -> 1 skipped)
ruff check .       # expect: All checks passed!
```

Git SHA: `UNKNOWN` (placeholder; fill at release/commit time).
Tool version: `formal_flow_scout.__version__ == "0.1.0"`. Python 3.10+.

| ID | Claim | Source | Test | Reproduce |
| --- | --- | --- | --- | --- |
| E1 | Backward combinational COI stops at register boundaries; sequential expansion crosses them | `graph_core.PackedGraph.backward_coi` | `test_graph_core.py::test_backward_coi_combinational_stops_at_seq` | `pytest tests/test_graph_core.py -k combinational` |
| E2 | COI is a correct over-approximation on a known chain | `graph_core.backward_coi` | `test_graph_core.py::test_backward_coi_over_approximation_chain` | `pytest tests/test_graph_core.py -k over_approximation` |
| E3 | Tarjan finds cyclic SCCs and singletons deterministically | `graph_core.tarjan_scc` | `test_graph_core.py::test_tarjan_simple_cycle`, `::test_tarjan_dag_all_singletons` | `pytest tests/test_graph_core.py -k tarjan` |
| E4 | Known COI for the counter includes register, its consumers, clock, reset, and branch-guard `en` | `analyzer.Analyzer.analyze` + `verilog_parser` guard capture | `test_analyzer.py::test_counter_known_coi` | `pytest tests/test_analyzer.py -k counter_known` |
| E5 | Unrelated FIFO pointers are correctly EXCLUDED with reasons | `analyzer._excluded` | `test_analyzer.py::test_fifo_excludes_unrelated_pointers` | `pytest tests/test_analyzer.py -k excludes_unrelated` |
| E6 | Genuine FIFO feedback cycle is detected and flagged | `graph_core.tarjan_scc`, `analyzer._global_risks` | `test_analyzer.py::test_fifo_has_sequential_cycle` | `pytest tests/test_analyzer.py -k sequential_cycle` |
| E7 | Multi-clock cone raises a HIGH soundness risk | `analyzer._global_risks` | `test_analyzer.py::test_two_clock_flags_multi_clock_risk` | `pytest tests/test_analyzer.py -k multi_clock` |
| E8 | All candidate partitions are HEURISTIC; every cut carries an UNPROVEN assumption | `analyzer._candidate_partitions`, `_make_partition` | `test_analyzer.py::test_all_partitions_labeled_heuristic` | `pytest tests/test_analyzer.py -k heuristic` |
| E9 | Unresolved property seeds are reported, not silently dropped | `analyzer._resolve_seeds` | `test_analyzer.py::test_unresolved_seed_is_reported_not_silently_dropped` | `pytest tests/test_analyzer.py -k unresolved_seed` |
| E10 | Output is deterministic (byte-identical across runs) | `graph_core` ordering + `analyzer` | `test_analyzer.py::test_deterministic_output` | `pytest tests/test_analyzer.py -k deterministic` |
| E11 | Manifest and RTL paths agree on the data cone; RTL additionally recovers guards | `graph_builder.build_from_manifest` / `build_from_parse` | `test_analyzer.py::test_manifest_and_rtl_agree_on_data_coi` | `pytest tests/test_analyzer.py -k agree` |
| E12 | Sized Verilog literals are not treated as signals; inline if/else targets the real signal | `verilog_parser._rhs_identifiers`, `_strip_control_prefixes` | `test_parser.py::test_sized_literals_not_treated_as_signals`, `::test_inline_if_else_targets_real_signal_not_keyword` | `pytest tests/test_parser.py` |
| E13 | Small generated-RTL COI scales (12.8k regs) within a bounded time and gives the exact expected size | `test_perf._generate_pipeline`, `graph_core` | `test_perf.py::test_generated_pipeline_coi_scales` | `pytest tests/test_perf.py -k scales` |
| E14 | Optional C++ core, when built, computes the identical COI to Python | `cpp/coi_core.cpp`, `cpp_bridge.coi_via_cpp` | `test_cpp_bridge.py::test_cpp_agrees_with_python` | `cd cpp && make && cd .. && pytest tests/test_cpp_bridge.py` |
| E15 | CLI produces a valid report JSON + well-formed DOT end to end | `cli.analyze`, `reporting.to_dot` | `test_cli.py::test_cli_analyze_rtl_emits_valid_report` | `pytest tests/test_cli.py -k emits_valid` |
| E16 | JSON Schema for the report contract is exportable | `models.CoiReport.model_json_schema`, `cli.schema` | `test_cli.py::test_cli_schema_exports_json_schema` | `formal-flow-scout schema` |
| E17 | Pydantic contracts are strict (reject unknown fields, negative ids) | `models._Strict`, field constraints | `test_models.py::test_models_forbid_extra_fields`, `::test_graph_edge_rejects_negative_ids` | `pytest tests/test_models.py` |

## Benchmark / example inputs (public, license: MIT with this repo)

- `examples/fifo_ctrl.v` — toy synchronous FIFO controller (authored here).
- `examples/counter.v` — saturating counter (authored here).
- `examples/two_clock.v` — two-clock compare (authored here).
- `examples/counter_manifest.json` — hand-written RTL Intent Manifest fixture
  matching the `rtl-intent-ingestor` contract.
- `examples/fifo_report.json`, `examples/fifo_coi.dot` — generated artifacts
  (reproduce: `cd examples && formal-flow-scout analyze fifo_property.json
  --rtl fifo_ctrl.v -o fifo_report.json --dot fifo_coi.dot`).

## Implementation evidence vs performance evidence

E1–E12, E14–E17 are **implementation-correctness** evidence (deterministic unit
tests). E13 is a **scaling smoke test**, not a calibrated performance benchmark:
it asserts correctness at ~12.8k registers and a generous time bound, not a
throughput number. No billion-gate or absolute-speed claims are made.
