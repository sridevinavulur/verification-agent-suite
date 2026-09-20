# Evidence

Each claim in the README/spec is tied to the source that implements it, the test
that exercises it, and a command to reproduce it. Run from the repo root inside
the venv (`pip install -e ".[dev]"`).

| # | Claim | Source | Test | Reproduce |
|---|---|---|---|---|
| 1 | Parses SVA assume/assert/cover (concurrent, named property, immediate) | `parsers/sva.py::parse_sva` | `test_sva_parser.py` | `pytest tests/test_sva_parser.py` |
| 2 | Clock/`disable iff` prefix stripped; clk/rst_n not leaked as body signals | `parsers/sva.py::_clock_and_body` | `test_clock_and_disable_iff_stripped_from_body` | `pytest -k disable_iff` |
| 3 | Signal ownership from manifest port directions | `analysis/ownership.py` | `test_ownership.py` | `pytest tests/test_ownership.py` |
| 4 | Boundary output beats registered-signal classification | `parsers/manifest.py`, `analysis/ownership.py` | `test_boundary_output_takes_precedence_over_register` | `pytest -k precedence` |
| 5 | Boolean contradiction (`assume x` vs `assume !x`) flagged | `analysis/contradictions.py` | `test_boolean_contradiction_detected` | `pytest -k boolean_contradiction` |
| 6 | Constant conflict (`mode==1` vs `mode==2`) flagged | `analysis/contradictions.py` | `test_constant_conflict_detected` | `pytest -k constant_conflict` |
| 7 | Consistent assumptions NOT falsely flagged | `analysis/contradictions.py` | `test_no_false_contradiction_when_consistent` | `pytest -k false_contradiction` |
| 8 | x/z values not reported as contradictions | `analysis/contradictions.py` | `test_xz_values_not_reported_as_contradiction` | `pytest -k xz` |
| 9 | Unused assumptions flagged; used ones not | `analysis/usage.py::find_unused_assumptions` | `test_unused_assumption_flagged`, `test_used_assumption_not_flagged` | `pytest -k unused` |
| 10 | Assuming on DUT output / internal state / unknown flagged | `analysis/usage.py::find_output_constraints` | `test_output_and_internal_constraints_flagged` | `pytest -k output_and_internal` |
| 11 | Legal input assumption NOT flagged | `analysis/usage.py` | `test_legal_input_assumption_not_flagged` | `pytest -k legal_input` |
| 12 | Property dependency map built | `analysis/dependency.py::build_dependency_map` | golden `test_bad_golden_json` | `pytest -k golden` |
| 13 | Vacuity risk raised when contradictions exist | `analysis/dependency.py::vacuity_recommendations` | `test_bad_corpus_flags_all_anti_patterns` | `pytest -k anti_patterns` |
| 14 | Reachability recommendation for assertion without paired cover | `analysis/dependency.py` | golden `bad.json` (`REACHABILITY_RISK`) | `pytest -k golden` |
| 15 | Prioritized human-review queue (P1 first) | `analysis/review.py` | `test_review_queue_prioritized` | `pytest -k prioritized` |
| 16 | Every actionable finding = static suspicion + needs review | `models.py`, all analysis | `test_every_actionable_finding_is_static_suspicion` | `pytest -k static_suspicion` |
| 17 | Never claims soundness; standing reminder on clean runs | `analysis/dependency.py`, `models.py::disclaimer` | `test_disclaimer_never_claims_soundness` | `pytest -k disclaimer` |
| 18 | No-manifest run degrades to `unknown`, not false-clean | `analysis/ownership.py`, `analysis/usage.py` | `test_no_manifest_degrades_to_unknown` | `pytest -k no_manifest` |
| 19 | GOOD corpus passes cleanly | `examples/good/`, engine | `test_good_corpus_is_clean`, `test_good_golden_json` | `pytest -k "clean or good_golden"` |
| 20 | BAD corpus flags every anti-pattern | `examples/bad/`, engine | `test_bad_corpus_flags_all_anti_patterns`, `test_bad_golden_json` | `pytest -k "anti_patterns or bad_golden"` |
| 21 | CLI runs end-to-end; `--fail-on` gate works | `cli.py` | `test_cli.py` | `pytest tests/test_cli.py` |
| 22 | Report contract exported as JSON Schema | `cli.py::schema`, `models.py` | `test_cli_schema` | `constraint-hygiene schema` |

## Golden artifacts

- `examples/expected/good.json`, `good.md` — clean report.
- `examples/expected/bad.json`, `bad.md` — every anti-pattern flagged.

Regenerate:

```bash
for n in good bad; do
  constraint-hygiene review examples/$n/${n}_constraints.sva -m examples/dut_manifest.json -f json -o examples/expected/$n.json
  constraint-hygiene review examples/$n/${n}_constraints.sva -m examples/dut_manifest.json -f md   -o examples/expected/$n.md
done
```
