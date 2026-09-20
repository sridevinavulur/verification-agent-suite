# Evidence

Each resume-safe claim below is tied to source code, a test, the benchmark, and a
reproduce command. Implementation evidence is distinguished from
experimental-metric evidence. Commit hash placeholder: `<COMMIT_SHA>`.

Reproduce environment:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## CLAIM-1 — Deterministic coverage-hole classifier (baseline, no LLM)

**Claim:** "A deterministic baseline classifier assigns an evidence-backed
category to every uncovered coverage point, before any LLM reasoning."

- Source: `src/coverage_closure_agent/triage.py` — `TriageEngine._classify_hole`,
  `TriageEngine.run`.
- Tests: `tests/test_classifier.py::test_expected_categories`,
  `::test_every_hole_has_hypothesis_and_evidence`,
  `::test_covered_items_are_not_holes`.
- Benchmark: `examples/toy_benchmark.json` (synthetic public, MIT).
- Reproduce: `pytest tests/test_classifier.py`
- Expected: 9 holes classified into the 6 exercised categories; every hole has
  >=1 hypothesis and >=2 cited evidence items.

## CLAIM-2 — Ranked next actions restricted to the allowed set

**Claim:** "Recommendations are ranked and drawn exclusively from the spec-6.1
allowed-recommendation list."

- Source: `triage.py` — `TriageEngine._rank_actions`, `_ACTION_BASE_PRIORITY`;
  `models.py` — `AllowedAction`, `Recommendation` (typed + `field_validator`).
- Tests: `tests/test_ranker.py::test_all_recommendations_are_allowed_actions`,
  `::test_recommendations_are_priority_sorted`,
  `::test_not_run_hole_recommends_running_existing_test`,
  `::test_unreachable_hole_top_action_is_inspect`.
- Reproduce: `pytest tests/test_ranker.py`
- Expected: all recommendations are `AllowedAction` members, priority-sorted.

## CLAIM-3 — Root-cause hypotheses with cited evidence

**Claim:** "Each hole carries root-cause hypotheses supported by evidence citing a
named input source, including failure-log lines for failed tests."

- Source: `triage.py` — evidence assembly in `_classify_hole`.
- Tests: `tests/test_classifier.py::test_failed_test_evidence_cites_log`.
- Reproduce: `pytest tests/test_classifier.py::test_failed_test_evidence_cites_log`
- Expected: `cov.arb.fsm.grant2` evidence includes a `failure_log` source quoting
  the failing assertion.

## CLAIM-4 — Prohibited actions enforced; no closure claim

**Claim:** "The agent never emits a prohibited action and never claims closure; it
emits an independent-measurement manifest and a human-review queue instead."

- Source: `models.py` — `ProhibitedAction`, `IndependentMeasurementStep`,
  `HumanReviewItem`; `triage.py` — `run` (manifest + queue + scope note).
- Tests: `tests/test_metrics_and_safety.py::test_prohibited_actions_enforced_registry`,
  `::test_no_recommendation_is_a_prohibited_action`,
  `::test_independent_measurement_covers_every_hole`,
  `::test_human_review_queue_covers_every_hole`,
  `::test_scope_note_disclaims_closure_and_modification`.
- Reproduce: `pytest tests/test_metrics_and_safety.py`
- Expected: enforced deny-list equals `ProhibitedAction`; every hole has a
  measurement step and a review-queue entry.

## CLAIM-5 — Computed metrics over the run and a labelled sample

**Claim:** "The tool computes valid-proposal rate and provenance completeness over
the run, and accepted-proposal rate, false-positive rate, and category precision
over a labelled sample."

- Source: `triage.py` — `compute_metrics`; `models.py` — `TriageMetrics`,
  `SampleLabels`, `HoleLabel`.
- Tests: `tests/test_metrics_and_safety.py::test_valid_and_provenance_rates`,
  `::test_sample_metrics_computed`.
- Benchmark: `examples/toy_benchmark.json` + `examples/toy_labels.json`.
- Reproduce: `coverage-closure metrics examples/toy_benchmark.json examples/toy_labels.json`
- Expected (experimental, this benchmark): `valid_proposal_rate = 1.00`,
  `provenance_completeness = 1.00`, `category_precision = 1.00`,
  `accepted_proposal_rate = 0.60`, `false_positive_proposal_rate = 0.05`,
  `sample_size = 9`.

## CLAIM-6 — Deterministic, reproducible, provenance-logged output

**Claim:** "Identical inputs produce byte-identical reports; each run records tool
version, per-input content hashes, and seed."

- Source: `triage.py` — `_hash_inputs`, `ScopeProvenance`.
- Tests: `tests/test_classifier.py::test_determinism`,
  `tests/test_golden.py::test_golden_json_report`,
  `::test_golden_markdown_report`,
  `tests/test_metrics_and_safety.py::test_input_hashes_present_and_stable`.
- Golden artifacts: `examples/toy_report.golden.json`,
  `examples/toy_report.golden.md`.
- Reproduce: `pytest tests/test_golden.py`

## CLAIM-7 — Runnable CLI on a public toy benchmark

**Claim:** "The CLI runs end-to-end on the bundled public toy benchmark."

- Source: `src/coverage_closure_agent/cli.py`.
- Tests: `tests/test_cli.py` (all four commands).
- Reproduce: `coverage-closure demo`
- Expected: a full Markdown triage report plus sample-scored metrics, exit code 0.

## CLAIM-8 — Optional real Verilator/lcov coverage ingestion

**Claim:** "An optional ingester normalizes real Verilator `coverage.dat` and lcov
`.info` files into the same normalized `CoverageDB`/`TriageInputs` contract the
deterministic triage engine consumes, with a heuristic unreachability classifier,
without affecting the default mock pipeline."

- Source: `src/coverage_closure_agent/real_coverage.py` — `parse_coverage_dat`,
  `extract_toggle_coverage`, `parse_lcov`, `classify_unreachable`,
  `ingest_real_coverage`, `ingest_real_inputs`; `cli.py` — `ingest-real` command.
- Adapted from (read-only, not a dependency): veri-forge `sim/coverage.py` and
  `coverage/parser.py` — algorithms only; models/output-shape/CLI are this repo's.
- Tests: `tests/test_real_coverage.py` (15 tests) —
  `::test_parse_coverage_dat_counts`, `::test_extract_toggle_coverage`,
  `::test_parse_lcov_lines_and_branches`,
  `::test_classify_unreachable_categories`,
  `::test_ingest_marks_structural_unreachable_as_exclusion`,
  `::test_normalized_output_flows_into_triage`,
  `::test_cli_ingest_real_then_triage`.
- Fixtures: `examples/real/sample_coverage.dat`, `examples/real/sample.info`
  (tiny public toy artifacts).
- Reproduce:
  `coverage-closure ingest-real --dat examples/real/sample_coverage.dat --lcov examples/real/sample.info --triage`
- Expected: normalized bundle re-validates as `TriageInputs`; hardwired/dead-code
  toggles are flagged and triage classifies them `likely_unreachable`; every hole
  remains heuristic and human-gated (no closure claim).

---

## Not claimed

- No claim of formal unreachability, semantic correctness, or coverage signoff.
  The optional real-coverage unreachability classifier is **heuristic** (name
  patterns), not a proof.
- No claim of full vendor UCDB/UCIS ingestion. The optional `ingest-real` path
  handles Verilator `.dat` + lcov `.info` into the same `CoverageDB` contract.
- No claim of LLM-based reasoning (deterministic baseline only in this version).
