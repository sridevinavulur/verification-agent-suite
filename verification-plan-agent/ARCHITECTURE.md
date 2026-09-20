# Architecture

## Overview

The Verification Plan Agent is a deterministic pipeline. A **mock LLM** has a
narrow, advisory role (phrasing assertion rationale); every structural decision
is made by deterministic rules. This keeps the LLM (proposer) and the
deterministic layer (validator/decider) clearly separated, per `BUILD_STANDARD.md`.

```
spec.json ─┐
interface.json ─┤
manifest.json ─┼─► ingest.py ─► (SpecDocument, InterfaceGlossary,
existing.json ─┘                  ManifestView, ExistingTestplan)
                                        │
                                        ▼
                                   engine.build_plan
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼               ▼                ▼               ▼                ▼
   decompose      classify          risk score      scenarios/       ambiguity
  (features)   (8 categories)   (weighted rubric)  assertions/       detection
                                                    coverage
        └───────────────────────────────┬───────────────────────────────┘
                                         ▼
                              VerificationPlan (all items PROPOSED)
                                         │
                    approval.apply_decisions (human decisions.json)
                                         │
                                         ▼
                          report.render_markdown / serialize
```

## Components

| Module | Responsibility |
| --- | --- |
| `models.py` | Pydantic v2 contracts: inputs, plan content, approval workflow. All validate at construction (`extra="forbid"`). |
| `ingest.py` | Load spec/interface/testplan JSON; project the canonical RTL Intent Manifest into `ManifestView`. |
| `llm.py` | Deterministic, offline **mock** LLM adapter (`MockLLM`). No network. |
| `engine.py` | Deterministic rules: classify, decompose, score risk, generate scenarios/assertions/coverage, detect ambiguities, build traceability. |
| `approval.py` | Apply a human decisions file; promote `proposed → approved/rejected`. |
| `report.py` | Deterministic Markdown report generator. |
| `serialize.py` | Stable JSON (sorted keys) for golden comparison. |
| `cli.py` | Typer CLI: `plan`, `report`, `approve`, `schema`. |

## Typed input/output contracts

**Inputs**
- `SpecDocument` — design name + list of `Requirement`.
- `InterfaceGlossary` — list of `InterfaceSignal` (name/direction/width/role).
- RTL Intent Manifest — consumed via the **canonical external schema**
  (`rtl-intent-ingestor/schemas/manifest.schema.json`); projected to
  `ManifestView` reading only `modules[].ports`, `reset_candidates[].signal`,
  `clock_candidates[].signal`, `registers`, `nets[].is_memory`, `top`.
- `ExistingTestplan` — optional pre-agreed items.
- `list[ApprovalDecision]` — human decisions for the approval command.

**Output**
- `VerificationPlan` — features, risk-ranked plan items, scenarios, assertion
  candidates, coverage targets, ambiguities, traceability matrix, provenance.

## Authority boundaries

- The agent only ever emits `ApprovalState.PROPOSED`. It cannot self-approve.
- Promotion to `APPROVED`/`REJECTED` happens **only** through `apply_decisions`
  from a human-authored decisions file. Already-decided items are never silently
  overwritten (they are reported as unmatched).
- The tool never mutates RTL, the spec, assumptions, proof scope, or signoff
  conclusions — it only reads inputs and writes new plan artifacts.
- The LLM is offline and advisory; a rejected/unknown adapter name is a hard
  error (`get_adapter`).

## Determinism

Iteration follows input requirement order; the mock LLM is a pure hash-seeded
template pick; JSON is emitted with sorted keys. This makes the golden tests in
`tests/test_golden.py` byte-stable.
