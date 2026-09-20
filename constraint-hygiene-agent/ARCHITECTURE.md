# Architecture

## Overview

The Constraint Hygiene Agent is a **two-layer** pipeline, matching the
BUILD_STANDARD separation:

1. **Deterministic parsing layer** (`parsers/`) — turns text inputs into typed
   facts. No inference beyond structure.
2. **Deterministic analysis layer** (`analysis/`) — applies hygiene checks over
   those facts and emits `Finding` objects, all labelled as *static suspicion*.

There is **no LLM layer** in v0.1: every output is a reproducible function of the
inputs. (A future LLM layer would only *propose hypotheses* for a human to
review; the deterministic checks would remain the authority. This boundary is
noted so it is never blurred.)

```
 SVA file ─▶ parsers/sva.py ─────┐
                                 ├─▶ engine.analyze() ─▶ HygieneReport ─▶ report.py (md)
 manifest.json ─▶ parsers/manifest.py ─┘                       │
                                                               └─▶ model_dump_json (json)
```

## Components

| Module | Responsibility |
|---|---|
| `parsers/sva.py` | Constrained SVA directive parser; extracts signals, constant-equality facts, boolean-literal facts (top-level conjuncts only). |
| `parsers/manifest.py` | Reads the canonical RTL Intent Manifest; projects top-module port directions + internal register/net names into a `ManifestView`. |
| `analysis/ownership.py` | Classifies each signal: `environment_input` / `dut_output` / `internal_state` / `unknown`, grounded in manifest port directions. |
| `analysis/contradictions.py` | Pairwise contradiction + constant-conflict detection over assumptions. |
| `analysis/usage.py` | Unused-assumption detection; output/internal-state/unknown constraint warnings. |
| `analysis/dependency.py` | Property dependency map; vacuity/reachability recommendations. |
| `analysis/review.py` | Prioritized human-review queue (P1–P3). |
| `engine.py` | Orchestrates all passes; assembles `HygieneReport` with provenance. |
| `report.py` | Renders Markdown. |
| `cli.py` | Typer CLI (`review`, `schema`, `version`). |

## Typed contracts (`models.py`)

- **Input-derived:** `Property` (a parsed directive).
- **Manifest projection:** `ManifestView` (dataclass, in `parsers/manifest.py`).
- **Output:** `HygieneReport` — the single top-level Pydantic contract, exported
  as JSON Schema to `schemas/hygiene_report.schema.json`. Sub-contracts:
  `SignalClassification`, `Finding`, `DependencyEdge`, `ReviewItem`,
  `Provenance`.

Vocabulary enums (`SvaKind`, `Ownership`, `Severity`, `Confidence`,
`FindingCode`) keep result language consistent and machine-checkable.

## Authority boundaries

- The tool is **read-only** with respect to design artifacts. It never edits
  SVA, RTL, manifest, proof scope, or budgets.
- Every actionable `Finding` carries `needs_human_review=True` and is surfaced in
  the human-review queue. The queue *is* the human-approval gate: acting on a
  finding (e.g. deleting an assumption) is a human decision made outside this
  tool.
- `Confidence` is only ever `static_suspicion` (for heuristic findings) or
  `static_fact` (reserved for manifest-grounded classifications). The tool has
  no vocabulary for "proven" — by design.

## Determinism

- All collection outputs are sorted by stable keys before serialization.
- Provenance records input SHA-256 hashes and the command, so a report can be
  reproduced and diffed. Golden tests compare the analysis payload with
  provenance excluded.
