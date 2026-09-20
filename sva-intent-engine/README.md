# sva-intent-engine

Evidence-grounded **candidate** SystemVerilog Assertion (SVA) generation and
review. This tool turns simple natural-language hardware requirements plus a
public RTL symbol manifest into traceable candidate SVA properties, with a
deterministic core that runs entirely offline.

> Positioning: this is a candidate-property generation and review system. It
> does **not** claim that generated properties are semantically correct,
> formally proven, complete, or signoff-ready. Every property is a candidate
> until independently validated and human-reviewed.

## What actually works (this phase)

Phase 0 (schemas, examples, golden outputs, schema tests) **plus** a working
deterministic core that generates SVA end to end:

- **Typed schemas** (Pydantic v2) for requirement, decomposition, RTL manifest,
  grounding, temporal-intent IR, candidate property, validation report, review
  report, and provenance — with JSON Schema export (`schemas/`).
- **Requirement decomposition** (`decompose.py`): deterministic rules split a
  requirement into atomic clauses, classify each
  (`design_guarantee`/`environment_assumption`/`cover_objective`/`ambiguity`/`unsupported`),
  extract triggers/consequents/guards, and flag vague terms
  (`soon`, `eventually`, `properly`, ...). It never infers a signal name, clock,
  or cycle bound.
- **RTL symbol grounding** (`grounding.py`): deterministic ranked mapping of
  requirement terms to manifest symbols (exact > case-insensitive > alias).
  Multiple matches are kept; unresolved terms **stop** SVA emission.
- **Safe SVA renderer** (`renderer.py`): deterministic template/AST renderer for
  invariant, implication (`|->`), bounded response (`|-> ##[N:M]`), next-cycle
  (`|=>`), no-overflow / no-underflow, one-hot, stable-while-stalled,
  reset-state, and eventually-within-bound cover forms. All expressions pass a
  whitelist (`safe_expr`); the renderer rejects an absent clock, unresolved
  symbols, invalid timing ranges, unknown reset polarity for reset properties,
  and unsupported/unsafe expressions.
- **CLI** `sva-intent` with `ingest`, `ground`, `generate`, `validate`,
  `review-report`, `export-schemas`, and `demo`.
- **Five public examples** with requirement text, an RTL symbol manifest
  fixture, a golden temporal-intent JSON, and golden rendered SVA.
- **62 unit tests** (schema validation, decomposition heuristics, grounding
  ranking, renderer safety, golden outputs, and CLI).

The LLM path is a **mock adapter only** (`llm_adapter.py`); the deterministic
pipeline requires no LLM and no network.

## Install

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Run all bundled examples end to end:

```bash
sva-intent demo
```

A single full flow (ingest -> ground -> generate -> validate) on one example:

```bash
sva-intent ingest   examples/requirements/ready_valid.md --no-json-out
sva-intent ground   examples/requirements/ready_valid.md examples/rtl_manifests/ready_valid.json
sva-intent generate examples/requirements/ready_valid.md examples/rtl_manifests/ready_valid.json
sva-intent validate examples/requirements/ready_valid.md examples/rtl_manifests/ready_valid.json
```

### Canonical manifest interop (rtl-intent-ingestor)

`rtl-intent-ingestor` is the canonical **producer** of the RTL Intent Manifest
(schema `rtl-intent`, `schema_version` 0.1.0). This engine consumes that manifest
directly, so the two tools compose:

- `src/sva_intent_engine/rtl_intent_adapter.py` maps the canonical manifest
  (`modules[].ports/nets/registers/clock_candidates/reset_candidates`, with source
  locations and heuristic reset polarity) down to the engine's `RTLManifest`.
- Every manifest-consuming command takes `--manifest-format auto|canonical|fixture`
  (default `auto`), which auto-detects the format so the engine's own fixtures keep
  working (back-compat). `io_utils.load_manifest` does the same detection.
- `examples/rtl_manifests/valid_ready.canonical.json` is a verbatim copy of
  `rtl-intent-ingestor/examples/expected/valid_ready.json`.

Widths kept by the producer as unevaluated parameter text (e.g. `WIDTH - 1`) are
**not** guessed — such signals get `width: null`. Only integer ranges yield a
concrete width.

```bash
# Ground a requirement against the CANONICAL rtl-intent-ingestor manifest:
sva-intent ground examples/requirements/ready_valid.md \
  examples/rtl_manifests/valid_ready.canonical.json
```

Example generated candidate (from `ready_valid`):

```systemverilog
p_ready_valid_c0_bounded_response: assert property (
  @(posedge clk) disable iff (!rst_n) (valid && ready) |-> ##[1:3] (grant)
);
```

Export JSON Schemas:

```bash
sva-intent export-schemas schemas
```

Regenerate golden outputs after intentional changes:

```bash
python scripts/gen_golden.py
```

## Example set

| Example | Requirement gist | Property form |
| --- | --- | --- |
| `ready_valid` | valid&ready -> grant within 1..3 cycles | bounded_response |
| `fifo_overflow` | full -> !overflow next cycle | no_overflow |
| `fifo_underflow` | empty -> !underflow next cycle | no_underflow |
| `reset_state` | count == 0 during reset | reset_state |
| `counter_saturate` | sat -> !wrap next cycle | next_cycle |

## Safety rules enforced in code

1. Never invent a signal, clock, reset, or timing bound. Missing detail blocks
   emission rather than being guessed.
2. Every identifier in a generated property maps to a symbol in the supplied RTL
   manifest (`grounding.py`, `pipeline._build_expressions`).
3. Every temporal property has an explicit clock or is rejected
   (`renderer._clocking`).
4. Reset polarity for a reset-state property must be known or the property is
   rejected (`renderer.render`, `RESET_STATE` branch).
5. A compiled/rendered property is **not** a verified property
   (`CandidateProperty.status = "candidate_compiled_offline"`).

## Non-claims

- No claim of semantic correctness, completeness, vacuity-freedom, or formal
  proof. No mutation testing or formal/simulation execution is performed in this
  phase.
- Grounding is lexical and deterministic; it does not understand design intent.
- The natural-language front end is intentionally narrow. Requirements outside
  the supported phrase shapes are flagged, not force-fit.

## Roadmap (stubbed / not in this phase)

- `sva-intent mutate` (assertion mutation scoring) — see prompt-pack 5.8.
- `sva-intent export <run-id>` ledger export.
- Real LLM extractor behind the adapter (proposals only; deterministic tools
  still validate).
- Compile/lint via an open-source SVA front end; bounded formal/sim adapters.

## Documentation

- `ARCHITECTURE.md` — components and typed contracts.
- `THREAT_MODEL.md` — hallucination, unsafe assumptions, reproducibility risks.
- `EVIDENCE.md` — each claim tied to code, test, and reproduce command.
- `RELEASE_CHECKLIST.md` — public-disclosure audit.

## License

MIT (placeholder). Public, non-proprietary example content only.
