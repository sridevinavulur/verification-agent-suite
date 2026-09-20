# Architecture

## Overview

The Coverage Closure Agent is a **deterministic triage pipeline**. It has no
network access and (in this version) no LLM. The design keeps two layers strictly
separated per the shared build standard:

- **Deterministic layer** (implemented here): ingest, classify, rank, measure
  metrics, enforce the authority boundary.
- **LLM layer** (not implemented; documented as future work): would only *explain*
  deterministic findings in natural language. It could never widen the action set
  or override a category.

```
                +---------------------------+
inputs bundle → |  io.load_inputs (Pydantic |  validates every contract
   (JSON)       |  validation, extra=forbid)|
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                |  TriageEngine.run         |
                |  1. build indexes         |
                |  2. find holes (hits<goal)|
                |  3. classify each hole    |  → HoleCategory + Evidence + hypotheses
                |  4. rank AllowedActions   |  → Recommendation[] (priority-sorted)
                |  5. independent-measure   |
                |  6. human-review queue    |
                |  7. scope/provenance      |
                |  8. metrics               |
                +-------------+-------------+
                              |
                 +------------+------------+
                 v                         v
        TriageReport (JSON)        report.render_markdown
        model_dump(mode=json)      (human-readable)
```

## Components

| Module | Responsibility |
| --- | --- |
| `models.py` | All typed contracts (Pydantic v2, `extra="forbid"`). Controlled vocabularies: `CoverageKind`, `HoleCategory`, `AllowedAction`, `ProhibitedAction`, `TestStatus`. |
| `io.py` | Load + validate the inputs bundle and sample labels from JSON. |
| `triage.py` | `TriageEngine` (deterministic classifier + ranker) and `compute_metrics`. |
| `report.py` | Markdown rendering of a `TriageReport`. |
| `cli.py` | Typer CLI: `triage`, `metrics`, `schema`, `demo`. |

## Typed input contract (`TriageInputs`)

- `coverage: CoverageDB` — the mock coverage export (`items: CoverageItem[]`).
- `tests: TestManifest` — `TestEntry[]` with `status`, `seed`, `config`, `covers`.
- `rtl: RTLIntentManifest` — `RTLModule[]` with `dead_code_hints`.
- `requirements: RequirementMatrix` — `RequirementLink[]` mapping reqs → tests/covers.
- `logs: LogBundle` — `LogEntry[]` failure/compile records keyed by `test_id`.

## Typed output contract (`TriageReport`)

- `classifications: HoleClassification[]` — per-hole category, evidence,
  hypotheses, ranked recommendations, provenance-complete flag.
- `independent_measurement: IndependentMeasurementStep[]` — how to confirm closure.
- `human_review_queue: HumanReviewItem[]`.
- `scope_provenance: ScopeProvenance` — tool version, input hashes, seed, counts.
- `metrics: TriageMetrics`.
- `prohibited_actions_enforced: ProhibitedAction[]` — the enforced deny-list.

JSON Schema for both contracts is exported to `schemas/` via
`coverage-closure schema`.

## Classification algorithm (deterministic decision tree)

For each hole (`hits < goal`), in this priority order:

1. **`likely_unreachable`** if the item has an `exclusion_pragma` or its
   `source_line` is in the module's `dead_code_hints`.
2. Otherwise, if **no test** lists the item in `covers` → **`no_linked_test`**.
3. Otherwise inspect the linked tests' statuses:
   - any FAIL/TIMEOUT/ERROR → **`test_ran_but_failed`** (log evidence attached);
   - all `not_run` → **`test_exists_not_run`**;
   - at least one PASS but still uncovered → **`test_ran_still_uncovered`**.
4. If still unclassified and no requirement maps the item →
   **`no_requirement_mapping`**; else **`unknown`**.

Requirement-mapping evidence is always attached regardless of branch. Every
branch cites concrete facts from the inputs as `Evidence`.

## Ranking

Each category maps to a fixed set of `AllowedAction`s. Actions carry a base
priority (`RUN_EXISTING_TEST` highest, `REQUEST_SPEC_CLARIFICATION` lowest —
cheapest/highest-certainty first). Recommendations are stably sorted by
`(-priority, action_name, detail)` so output is deterministic and golden-testable.

## Authority boundary

- The `action` field of `Recommendation` is typed as `AllowedAction`; a
  `field_validator` re-asserts membership so the boundary cannot be widened by a
  future refactor.
- Prohibited actions live in `ProhibitedAction` and are surfaced in every report
  (`prohibited_actions_enforced`) and asserted in tests.
- Every recommendation has `requires_human_approval = True`.
- The agent produces an independent-measurement manifest instead of ever setting
  a "closed" status.

## Determinism & provenance

- No randomness; `seed` is recorded for the ledger and forward-compatibility.
- Input sub-documents are content-hashed (`sha256:` prefix, 16 hex chars) into
  `ScopeProvenance.input_hashes`.
- Same inputs → byte-identical `model_dump(mode="json")` (asserted by
  `test_classifier.test_determinism` and the golden tests).
