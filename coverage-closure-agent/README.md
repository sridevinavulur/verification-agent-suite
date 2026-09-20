# Coverage Closure Agent

Deterministic coverage-hole triage and **ranked next-action recommendations** for
public RTL verification projects.

Given a normalized coverage-DB export plus the surrounding verification context
(test manifest, RTL Intent Manifest, requirement-to-test matrix, and
failure/compile logs), the agent classifies every uncovered coverage point,
attaches evidence-backed root-cause hypotheses, and produces a **ranked list of
allowed next actions** for a human to review. It never modifies RTL, never
waives coverage, and never claims closure.

This repository implements the **deterministic baseline classifier** required by
section 6.1 of the prompt pack — the layer that must exist *before* any LLM
reasoning. No LLM is used; the engine is pure and reproducible.

## Scope (what this version does)

- Ingests a single JSON bundle in the **mock coverage format** (`mock-cov-1.0`)
  plus four companion manifests and a log bundle.
- Finds every uncovered coverage item (`hits < goal`) and classifies it into one
  of eight heuristic `HoleCategory` values using only cited evidence.
- Emits **root-cause hypotheses** and **evidence** for every hole.
- Produces **ranked next actions drawn exclusively from the allowed-recommendation
  list** (spec 6.1), each with a priority score, an *expected-impact hypothesis*,
  a concrete next step, and a `requires_human_approval` flag.
- Produces a **scope/provenance report** (tool version, input hashes, seed,
  coverage format, counts).
- Produces an **independent-measurement manifest** (how to re-measure coverage to
  confirm closure — the agent cannot).
- Produces a **human-review queue**.
- Computes **metrics** (valid proposal rate, provenance completeness) over the
  run, and sample-based metrics (accepted proposal rate, false-positive proposal
  rate, category precision) when a labelled sample is supplied.

## Install

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Run the full pipeline on the bundled public toy benchmark:

```bash
coverage-closure demo
```

Triage an arbitrary inputs bundle and write JSON + Markdown reports:

```bash
coverage-closure triage examples/toy_benchmark.json \
    --out report.json --markdown report.md
```

Score the classifier against a labelled sample:

```bash
coverage-closure metrics examples/toy_benchmark.json examples/toy_labels.json
```

Export JSON Schema for the input/output contracts:

```bash
coverage-closure schema --out-dir schemas
```

### Optional: ingest real Verilator/lcov coverage

The default pipeline consumes the hand-authored **mock coverage format** (below).
An **optional** ingester also normalizes *real* Verilator `coverage.dat` and lcov
`.info` files into the same normalized bundle, so `triage` can consume them
unchanged:

```bash
# Normalize real artifacts into a mock-cov inputs bundle
coverage-closure ingest-real --dat coverage.dat --lcov coverage.info --out real_bundle.json

# ...then triage it with the existing engine
coverage-closure triage real_bundle.json --out report.json

# Or do both in one step
coverage-closure ingest-real --dat coverage.dat --lcov coverage.info --triage
```

At least one of `--dat` / `--lcov` is required. Real artifacts carry no test
manifest or requirement matrix, so the bundle is emitted with empty-but-valid
companion manifests and an RTL module list derived from the observed coverage;
most holes then land in the honest `no_linked_test` / `no_requirement_mapping`
categories. Uncovered toggles are additionally passed through a **heuristic**
name-pattern unreachability classifier (`hardwired_constant`, `dead_code`,
`counter_ceiling`, `arch_limit`, `spec_gap`); points judged structurally
unreachable are flagged so triage routes them to `inspect_unreachable_code` /
`request_waiver_review`. This is a hint, **never** a formal proof and **never** a
closure claim. Sample fixtures live in `examples/real/`.

> **Provenance / attribution.** The `.dat`/`.info` parsing and the heuristic
> unreachability categories in `src/coverage_closure_agent/real_coverage.py` are a
> clean re-implementation adapted from an internal veri-forge reference
> (`sim/coverage.py`, `coverage/parser.py`). Only the algorithms were reused; the
> data model, normalized output shape, and CLI wiring are this repo's own, and
> there is no runtime dependency on that reference.

On the bundled 10-item toy benchmark (9 holes), the classifier reports
`category_precision = 1.00`, `valid_proposal_rate = 1.00`,
`provenance_completeness = 1.00`, `accepted_proposal_rate = 0.60`, and
`false_positive_proposal_rate = 0.05` against the hand-labelled sample.

## Mock coverage format (`mock-cov-1.0`)

A coverage DB export is a JSON object. Each item is one coverage point:

```json
{
  "coverage_id": "cov.fifo.branch.empty",
  "kind": "branch",
  "hits": 0,
  "goal": 1,
  "module": "fifo",
  "source_file": "rtl/fifo.sv",
  "source_line": 51,
  "description": "fifo empty branch taken",
  "exclusion_pragma": false
}
```

`kind` is one of `statement`, `branch`, `toggle`, `fsm_state`,
`fsm_transition`, `covergroup_bin`, `assertion`. An item is a **hole** when
`hits < goal`. See `schemas/triage_inputs.schema.json` for the full contract,
including the test manifest, RTL Intent Manifest, requirement matrix, and logs.

## Hole categories and how actions are chosen

| Category | Trigger (evidence) | Top ranked action(s) |
| --- | --- | --- |
| `likely_unreachable` | dead-code hint or exclusion pragma | `inspect_unreachable_code`, then `request_waiver_review` |
| `test_exists_not_run` | linked test with `status=not_run` | `run_existing_test` (with seed/config) |
| `test_ran_but_failed` | linked test FAIL/TIMEOUT/ERROR (+log) | `run_existing_test` (after human fix), `request_spec_clarification` |
| `test_ran_still_uncovered` | linked test PASS yet uncovered | `add_directed_test`, `add_constrained_random_scenario`, (`propose_assertion_candidate` for assertion cov) |
| `no_linked_test` | no test lists the point | `add_directed_test`, `add_cover_property`, (`request_spec_clarification` if no req) |
| `no_requirement_mapping` | no requirement maps the point | `request_spec_clarification`, `add_directed_test` |
| `unknown` | insufficient evidence | `request_spec_clarification` |

All actions come from the closed `AllowedAction` set; nothing outside it can be
emitted.

## Limitations

- The classifier is **heuristic**. Every `HoleCategory` is a *hypothesis*, flagged
  `is_heuristic = true`; the coverage tool remains authoritative.
- "Likely unreachable" is a **structural hint** from upstream tooling, not a
  formal unreachability proof.
- Expected-impact numbers are **hypotheses**, never guarantees, and are labelled
  as such (`expected_impact_note`).
- The mock coverage format is a teaching format, not a real vendor UCDB/UCIS
  export. The optional `ingest-real` path normalizes real Verilator `.dat` + lcov
  `.info` into the same `CoverageDB` contract, but is not a full UCDB/UCIS adapter.
- The heuristic unreachability classifier in the real-coverage path is a
  name-pattern match, **not** a formal unreachability proof.
- No LLM is integrated in this version (by design).

## Non-claims (this tool does NOT)

- It does **not** modify RTL.
- It does **not** waive coverage or mark anything waived.
- It does **not** change coverage scope.
- It does **not** claim coverage closure — closure requires **independent
  re-measurement** (see the independent-measurement manifest).
- It does **not** alter tests or constraints.
- It does **not** prove unreachability or correctness.

These prohibited actions are enumerated in `ProhibitedAction` and asserted in the
test suite (`tests/test_metrics_and_safety.py`).

## Documentation

- `ARCHITECTURE.md` — components, typed contracts, authority boundaries.
- `THREAT_MODEL.md` — hallucination, unsafe assumptions, leakage, reproducibility.
- `EVIDENCE.md` — each claim tied to source, test, and reproduce command.

## License

MIT — see `LICENSE`.
