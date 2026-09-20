# Architecture

## Overview

`sva-intent-engine` is a deterministic pipeline that transforms a
natural-language requirement plus an RTL symbol manifest into traceable
candidate SVA. An LLM (mock only in this phase) may *propose* hypotheses; it
never resolves symbols, chooses clocks, or invents bounds — those are the job of
the deterministic engines.

```
requirement file ─▶ decompose ─▶ ground ─▶ build_intent ─▶ render ─▶ validate ─▶ review report
   (md/json/yaml)    (5.4)       (5.5)      (IR, 5.3)      (5.6)      (static)     (packet)
```

Emission stops at the first stage that lacks grounded evidence: unresolved
terms, missing clock, unknown bound, or unknown reset polarity all block output.

## Components and typed contracts

| Module | Responsibility | Input contract | Output contract |
| --- | --- | --- | --- |
| `io_utils.py` | Load requirements / manifests | file path | `Requirement`, `RTLManifest` |
| `decompose.py` | Split + classify + flag vague terms | `Requirement` | `DecompositionResult` (list of `AtomicClause`) |
| `grounding.py` | Rank term→symbol matches; select clock/reset | `AtomicClause`, `RTLManifest` | `GroundingResult` |
| `expr_normalize.py` | NL phrase → SV boolean expr (grounded signals only) | phrase, resolved set | `(expr, reason)` |
| `pipeline.py` | Choose form, build IR, orchestrate run | clause + grounding | `TemporalIntent`, `ReviewReport` |
| `renderer.py` | Safe template/AST render + static checks | `TemporalIntent` | `CandidateProperty`, `ValidationCheck[]` |
| `schema_export.py` | JSON Schema export | — | `schemas/*.schema.json` |
| `cli.py` | Typer CLI | files/flags | stdout / JSON |
| `llm_adapter.py` | Provider-neutral LLM stub (mock) | prompt | proposal string |

All contracts are Pydantic v2 models in `models.py` with `extra="forbid"`.

## Authority boundaries

- **Deterministic tools own** symbol grounding, clock/reset selection, bound
  extraction, property-form choice, expression normalization, rendering, and
  static validation.
- **The LLM may only** produce non-authoritative proposals. In this phase the
  only adapter is `MockLLMAdapter`, which is inert and offline. It cannot inject
  a signal name or bound into the deterministic path.
- **Humans own** ambiguity resolution, reset-semantics confirmation, and any
  decision to treat a candidate as verified. The `ReviewReport.checklist`
  encodes these gates.

## Property forms (renderer)

`invariant`, `implication` (`|->`), `bounded_response` (`|-> ##[N:M]`),
`next_cycle` (`|=>`), `no_overflow` / `no_underflow` (`|=>`), `one_hot`
(`$onehot`), `stable_while_stalled` (`$stable`), `reset_state`, and
`eventually_within_bound` (cover). Form selection is deterministic and driven by
clause structure and keywords (`pipeline._choose_form`).

## Determinism and provenance

Every stage attaches a `Provenance` record (tool version, stage, git SHA
placeholder, input hashes, command). Golden tests compare intent/SVA with
provenance stripped so output is byte-stable across runs. `scripts/gen_golden.py`
regenerates goldens and schemas.
