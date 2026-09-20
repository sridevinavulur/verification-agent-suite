# Evidence

Each capability claim is tied to its implementation, a test, and a reproduce
command. Run everything from the repo root in the activated venv.

| Claim | Source | Test | Reproduce |
| --- | --- | --- | --- |
| Parses `EQLOG/1` logs into a validated model | `parser.parse_equivalence_log` | `test_parser.py::test_parse_toy_alu_log` | `eq-triage parse --log examples/toy_alu/equivalence.eqlog` |
| Parses widths / kind / CEX first-diff time | `parser._parse_mismatch`, `_parse_cex` | `test_parse_widths_and_kind`, `test_parse_cex_attachment_and_first_diff` | `pytest tests/test_parser.py -q` |
| Rejects malformed logs loudly | `parser` (`LogParseError`) | `test_parse_rejects_*`, `test_parse_missing_required_header` | `pytest tests/test_parser.py -q` |
| Interops with canonical RTL Intent Manifest | `parser.normalize_manifest`, `_from_canonical_manifest` | `test_canonical_manifest_normalization` | `pytest tests/test_parser.py -q` |
| Groups duplicate mismatch signatures (bit-slices collapse) | `triage.TriageEngine.signature`, `group_signatures` | `test_signature_grouping_collapses_bit_indices` | `eq-triage demo toy_alu` |
| Identifies mismatch cones | `group_signatures` (cone union) | golden tests | `eq-triage demo toy_alu` |
| Compares reset/init behavior | `TriageEngine.compare_reset` | `test_reset_comparison` | `eq-triage demo toy_alu` |
| Detects **width** cause | `classify_causes` (rule 1) | `test_width_cause_detected` | `eq-triage demo toy_alu` |
| Detects **polarity** cause | `classify_causes` (rule 2), `_inverted_cex_evidence` | `test_polarity_cause_detected` | `eq-triage demo toy_alu` |
| Detects **gating** cause | `classify_causes` (rule 3) | `test_state_encoding_and_gating_counter` | `eq-triage demo toy_counter` |
| Detects **state-encoding** cause | `classify_causes` (rule 5), `_state_encoding_evidence` | `test_state_encoding_and_gating_counter` | `eq-triage demo toy_counter` |
| Surfaces **config/constraint** deltas (never conceals) | `classify_causes` (rule 6), report field | `test_config_delta_surfaced_and_warned` | `eq-triage demo toy_alu` |
| Ranks source locations for review | `TriageEngine.rank_locations` | `test_ranked_locations_prioritize_compare_points` | `eq-triage demo toy_alu` |
| Builds a reproducible debug packet | `TriageEngine.build_debug_packet` | `test_debug_packet_built` | `eq-triage demo toy_alu` |
| Echoes tool status, never invents it | `TriageEngine._status_evidence`, `run` | `test_status_is_echoed_not_inferred` | `eq-triage demo toy_alu` |
| Non-conclusive status → advisory warning, no false claim | `TriageEngine.run` (warnings) | `test_inconclusive_status_warns_and_no_false_claim` | `pytest tests/test_triage.py -q` |
| Deterministic output (byte-stable) | stable sort keys throughout | `test_determinism_same_input_same_output`, golden tests | `pytest tests/test_golden.py -q` |
| Records run provenance (hashes, git SHA) | `provenance.build_provenance` | `test_cli_triage_json_out` | `eq-triage triage --log ... --out-json r.json` |
| CLI runs end-to-end on examples | `cli.py` | `test_cli_demo_toy_alu`, `test_cli_demo_toy_counter` | `eq-triage demo toy_alu` |

## Full verification

```bash
ruff check .     # clean
pytest           # 37 passed
```
