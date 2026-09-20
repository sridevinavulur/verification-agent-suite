# Verification Plan Agent

Deterministic tool that turns a **structured spec + interface glossary + RTL
Intent Manifest** into a **reviewable verification-plan draft** with full
traceability and an explicit human-approval workflow.

Implements pack section **6.2 (Verification Plan Agent)** and follows the shared
`BUILD_STANDARD.md`. **Mock LLM only — no network calls.**

## What it does (v0.1)

- **Decomposes** requirements into verifiable features.
- **Classifies** each into: functional / performance / reset / error_handling /
  security / low_power / cdc_rdc / integration (deterministic keyword rules).
- **Proposes verification techniques** per category: directed sim,
  constrained-random, SVA, formal, cover, emulation/FPGA, post-silicon.
- **Risk-ranks** plan items with a transparent weighted rubric (each score
  carries its rationale) and assigns P0–P3 priority.
- **Generates** proposed test scenarios, assertion candidate *sketches* (rationale
  phrased by the mock LLM), and coverage targets.
- **Flags** missing requirements, unverifiable requirements, and assumptions by
  cross-checking spec vs. interface glossary vs. RTL Intent Manifest.
- **Builds** a requirements → tests → coverage **traceability matrix**, marking
  uncovered requirements.
- **Distinguishes proposed vs. approved** items: everything is `proposed` until a
  human `decisions.json` promotes it via the `approve` command.

## Install

Requires Python ≥ 3.11.

```bash
python3.13 -m venv .venv        # any python >=3.11
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
vplan plan \
  --spec examples/fifo_spec.json \
  --interface examples/fifo_interface.json \
  --manifest examples/fifo_manifest.json \
  --existing examples/fifo_existing_testplan.json \
  --out plan.json --markdown plan.md

# Apply a human approval decision file (proposed -> approved/rejected)
vplan approve plan.json --decisions examples/fifo_decisions.json \
  --out plan.approved.json --markdown plan.approved.md

# Re-render a report from an existing plan JSON
vplan report plan.json

# Export the JSON Schema for the plan contract
vplan schema
```

The bundled golden outputs live in `examples/expected/`.

## Inputs

| Input | Flag | Schema |
| --- | --- | --- |
| Structured spec | `--spec` | `SpecDocument` (see `schemas/`) |
| Interface glossary | `--interface` | `InterfaceGlossary` |
| RTL Intent Manifest | `--manifest` | **canonical** `rtl-intent-ingestor/schemas/manifest.schema.json` |
| Existing testplan | `--existing` | `ExistingTestplan` |
| Human decisions | `--decisions` | list of `ApprovalDecision` |

The manifest is consumed via the canonical external schema; `ingest.py` projects
only the fields it needs (`modules[].ports`, `reset_candidates[].signal`,
`clock_candidates[].signal`, `registers`, `nets[].is_memory`, `top`).

## Non-claims (read this)

- The output is a **draft**, not an approved verification plan. No item is
  authoritative until a human approves it.
- Assertion candidates are **sketches** produced by templates + a mock LLM. They
  **may not compile** and may be incomplete or wrong.
- Classification / techniques / risk are **heuristics**, not a completeness or
  coverage guarantee.
- The tool **never** modifies RTL, spec, assumptions, proof scope, or signoff
  conclusions.
- No real LLM is used; the mock adapter is offline and deterministic.

## Roadmap (out of scope for v0.1)

- Richer requirement parsing (NLP beyond keyword rules).
- SVA candidate elaboration/lint (syntax checking of sketches).
- Coverage-model export to a vendor format.
- Bidirectional sync with an external requirement-management tool.

## License

MIT (placeholder) — see `LICENSE`.
