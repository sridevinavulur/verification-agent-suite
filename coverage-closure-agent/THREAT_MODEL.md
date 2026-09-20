# Threat Model

This is a triage and prioritization tool for public RTL verification data. It is
**not** a signoff tool. This document enumerates the risks and the concrete
mitigations in the code.

## 1. Hallucination / unsupported claims

**Risk:** presenting a heuristic guess as a verified fact, or inventing evidence.

**Mitigations**
- Every `HoleClassification.is_heuristic` is `True`; every `Recommendation`
  carries an `expected_impact_note` labelled as a hypothesis.
- Every classification branch attaches `Evidence` objects that quote a concrete
  fact from a named input source (`coverage_db`, `test_manifest`,
  `requirement_matrix`, `failure_log`, `rtl_intent_manifest`). No claim is emitted
  without a citation. (`tests/test_classifier.py::test_every_hole_has_hypothesis_and_evidence`)
- There is no free-text generation layer in this version; text is templated from
  validated fields.

## 2. Unsafe assumptions / scope creep

**Risk:** an agent silently taking a prohibited action (editing RTL, waiving
coverage, changing scope, altering tests) or claiming closure.

**Mitigations**
- Recommendations are typed to the closed `AllowedAction` enum and re-validated.
  (`tests/test_ranker.py::test_all_recommendations_are_allowed_actions`,
  `tests/test_metrics_and_safety.py::test_no_recommendation_is_a_prohibited_action`)
- Prohibited actions are an explicit registry (`ProhibitedAction`), surfaced in
  every report and asserted.
  (`tests/test_metrics_and_safety.py::test_prohibited_actions_enforced_registry`)
- The tool never emits a "closed"/"waived" status. Instead it emits an
  independent-measurement manifest describing how a human re-measures coverage.
  (`tests/test_metrics_and_safety.py::test_independent_measurement_covers_every_hole`)
- Waivers appear only as `request_waiver_review` (a human task), never as an
  applied waiver.
- The scope note explicitly records "did not modify RTL, tests, constraints,
  scope, or waivers." (`tests/test_metrics_and_safety.py::test_scope_note_disclaims_closure_and_modification`)

## 3. Never treat a non-pass as a pass

**Risk:** classifying a TIMEOUT/ERROR/UNKNOWN test result as coverage success.

**Mitigations**
- `TestStatus` distinguishes PASS from FAIL/TIMEOUT/ERROR/UNKNOWN/NOT_RUN.
- FAIL/TIMEOUT/ERROR all route to `test_ran_but_failed`, never to a
  "covered/closed" state. (`tests/test_classifier.py::test_expected_categories`)

## 4. Data leakage

**Risk:** committing proprietary RTL, customer names, internal tool names, logs
with proprietary paths, or credentials.

**Mitigations**
- The only bundled data is a small synthetic public toy benchmark
  (`examples/toy_benchmark.json`) using generic module names (fifo, arbiter,
  counter, handshake, misc) and fabricated paths (`rtl/*.sv`).
- The coverage tool field is literally `"mock"` and the format is `mock-cov-1.0`.
- No credentials, hostnames, or real filesystem paths are stored or required.
- `.gitignore` excludes venvs and caches.

## 5. Reproducibility risks

**Risk:** non-deterministic output, unlogged provenance, hidden negative results.

**Mitigations**
- The engine is pure and deterministic; outputs are stably sorted and
  golden-tested. (`tests/test_golden.py`, `tests/test_classifier.py::test_determinism`)
- `ScopeProvenance` records tool version, per-input content hashes, seed, coverage
  format, and item/hole counts. (`tests/test_metrics_and_safety.py::test_input_hashes_present_and_stable`)
- All holes appear in the report; none are dropped or hidden. Metrics count every
  recommendation.

## 6. Metric gaming / over-reporting

**Risk:** reporting inflated success metrics.

**Mitigations**
- `valid_proposal_rate` and `provenance_completeness` are *measured* over actual
  output, not assumed.
- Sample-based `accepted_proposal_rate`, `false_positive_proposal_rate`, and
  `category_precision` require an externally supplied labelled sample; the toy
  labels deliberately include a rejected proposal so the false-positive rate is
  nonzero. (`tests/test_metrics_and_safety.py::test_sample_metrics_computed`)

## Residual risks (accepted / future work)

- The mock coverage format is not a real UCDB/UCIS export; a real adapter is
  future work.
- Structural "likely unreachable" hints are not formal proofs.
- An LLM explanation layer, if added, must remain read-only over deterministic
  findings and be tested with a mock adapter (per the build standard).
