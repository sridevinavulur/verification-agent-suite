# Evidence

Each claim is tied to source, a test, and a reproduce command. Distinguishes
implementation evidence from (absent) experimental-performance evidence. Commit
hash placeholder: `UNKNOWN` (fill on release).

| ID | Claim | Source | Test | Reproduce |
|---|---|---|---|---|
| C1 | Parses a constrained Verilog subset (module, ports, always blocks, sensitivity, NB assigns) into a structural model | `rtl_parser.py:parse_text` | `tests/test_parser.py` | `pytest tests/test_parser.py` |
| C2 | Async vs sync reset classified structurally (edge-list vs body guard) | `analyzer.py:_detect_reset_candidates` | `test_async_active_low_counter`, `test_sync_active_high_multi_reg_domain` | `pytest tests/test_analyzer.py` |
| C3 | Reset polarity decided by evidence voting; conflicts/absence → `unknown` (never silent) | `analyzer.py:_vote_polarity`, `_polarity_from_*` | `test_vote_conflict_yields_unknown`, `test_vote_no_evidence_never_infers`, `test_ambiguous_polarity_not_inferred` | `pytest tests/test_analyzer.py` |
| C4 | `else if (en)` and non-constant RHS are NOT mistaken for reset | `rtl_parser.py:_parse_block_body` | `test_reset_branch_only_constants_attributed` | `pytest tests/test_parser.py -k constants` |
| C5 | Reset domains grouped and labelled `heuristic=True` | `analyzer.py:_domains` | `test_sync_active_high_multi_reg_domain` | `pytest tests/test_analyzer.py -k domain` |
| C6 | Possible reset-domain crossings detected structurally (heuristic) | `analyzer.py:_crossings` | `test_reset_domain_crossing_detected` | `pytest tests/test_analyzer.py -k crossing` |
| C7 | `no_reset` HIGH risk raised for sequential logic without a reset | `analyzer.py:_risks` | `test_no_reset_flags_high_risk` | `pytest tests/test_analyzer.py -k no_reset` |
| C8 | Candidate SVA is always `status=candidate`; unknown polarity emits a REVIEW placeholder | `analyzer.py:generate_candidate_sva` | `tests/test_sva.py` | `pytest tests/test_sva.py` |
| C9 | Consumes the canonical RTL Intent Manifest schema (INTEROP) | `manifest_adapter.py` | `tests/test_manifest_adapter.py` | `pytest tests/test_manifest_adapter.py` |
| C10 | Reset-defect mutants generated (polarity flip, value change, removal) with exact source change | `mutations.py` | `tests/test_mutations.py` | `pytest tests/test_mutations.py` |
| C11 | Deterministic Graphviz DOT + JSON reset graph | `graph.py`, `analyzer.py:_graph` | `test_cli_graph_dot`, `test_dot_is_deterministic` | `reset-intent graph examples/rtl/dual_reset_domains.sv` |
| C12 | Markdown report foregrounds STRUCTURAL/HEURISTIC labels | `report.py` | `test_cli_report_markdown`, `test_report_contains_candidate_sva` | `reset-intent report examples/rtl/dual_reset_domains.sv` |
| C13 | Provenance records tool version, command, input SHA-256 | `agent.py:_build_provenance`, `_sha256` | `test_manifest_has_provenance_with_hash` | `pytest tests/test_cli_and_outputs.py -k provenance` |
| C14 | Exported JSON Schema validates emitted manifests | `models.py`, `cli.py:schema` | `test_cli_analyze_valid_json`, `test_cli_schema` | `reset-intent schema` |

## Not claimed (no evidence)

- Semantic correctness of any candidate SVA (no compile/simulate/formal run).
- CDC/RDC signoff quality.
- Verified reset intent or verified reset-domain definitions.
- Full SystemVerilog parsing.
- Mutation *detection* scores (no execution adapter in v0.1).

## Reproduce everything

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .        # clean
pytest              # green (42 tests)
reset-intent analyze examples/rtl/dual_reset_domains.sv
```
