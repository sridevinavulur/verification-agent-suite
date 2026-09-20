# Architecture

## Overview

```
SVA file ──▶ parser.py ──▶ [ParsedProperty]
                                   │
RTL Intent Manifest (JSON) ────────┤
requirement IDs (optional) ────────┤
                                   ▼
                          checks/ (deterministic)
                                   │  -> [Finding]
                                   ▼
                          review.py (orchestrate + checklist)
                                   │  -> ReviewReport
                     ┌─────────────┼───────────────┐
                     ▼             ▼                ▼
              scoring.py      cli.py (text/json)  llm.py (optional mock)
              ReviewScore                          annotate only
```

## Authority boundaries (from BUILD_STANDARD)

1. **Deterministic layer** (`parser.py`, `checks/`, `review.py`, `scoring.py`)
   is the sole authority for *what the findings are*. Every `Finding` has a
   stable `CheckId`, a `Severity`, and a `SourceLocation`.
2. **LLM layer** (`llm.py`) may only attach a plain-language `explanation` to an
   existing finding. It **cannot** create, delete, reclassify, or re-severity a
   finding. Enforced structurally: `annotate_report` copies findings and sets
   only the `explanation` field. The default adapter is a deterministic,
   offline `MockLLMAdapter` — no network, no API key (test/CI safe).
3. The tool **never** modifies SVA, RTL, or manifests. It is read-only and
   advisory. It never declares an assertion correct or a property proven.

## Typed contracts (`models.py`, Pydantic v2)

* `RtlIntentManifest` / `ManifestSignal` — grounding fixture (`extra="forbid"`).
* `ParsedProperty` — parser output; unknown fields are `None`, never guessed.
* `Finding` (frozen) — one static finding.
* `ReviewReport` — full output; `counts()`, `score()`, `checklist`.
* `ReviewScore` — weighted score + grade.
* Enums: `Severity`, `SignalRole`, `ResetPolarity`, `PropertyKind`,
  `ImplicationStyle`, `CheckId`.

JSON Schema is exported via `assertion-review schema` into `schemas/`.

## Checks

Each check is a pure function `(CheckContext) -> list[Finding]` registered in
`checks/__init__.py::REGISTRY`. Adding a check = add a `CheckId`, write the
function, register it. Findings are sorted by `(line, severity, check_id)` for
stable, diff-friendly output.

## Result vocabulary

This tool operates before any solver runs, so it uses: `ERROR`, `WARNING`,
`INFO`, and "property compiled/parsed" (front-end acceptance only). It never
emits PASS/proven — that authority belongs to a formal/simulation backend.
