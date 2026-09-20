# assertion-review-agent

Deterministic static review of **SystemVerilog Assertions (SVA)** *before* they
are handed to a formal or simulation engine. It parses a constrained SVA subset,
grounds identifiers against an **RTL Intent Manifest** fixture, and emits an
issue list with **severity + source locations**, a **review-quality score**, and
a **reviewer checklist**.

This is the implementation of section 5.7 ("Assertion Review and Vacuity Agent")
of the verification agent prompt pack. It follows the shared `BUILD_STANDARD.md`.

## What it actually does (implemented, tested)

Deterministic checks, each with a stable `CheckId`, severity, and source location:

| Check | ID | Severity |
| --- | --- | --- |
| Missing explicit clock | `MISSING_CLOCK` | ERROR |
| Missing / incorrect `disable iff` reset guard | `MISSING_DISABLE_IFF` | WARN/INFO (heuristic) |
| Reset polarity risk (vs manifest polarity) | `RESET_POLARITY_RISK` | ERROR |
| `\|->` vs `\|=>` mismatch risk | `IMPLICATION_STYLE_RISK` | WARN (heuristic) |
| Unbounded / ambiguous temporal operators (`##[n:$]`, `eventually`, `until`) | `UNBOUNDED_TEMPORAL` | WARN/INFO |
| Weak / constant-true consequent | `WEAK_CONSEQUENT` | ERROR/INFO |
| Antecedent duplicated in / identical to consequent | `ANTECEDENT_IN_CONSEQUENT` | ERROR/WARN |
| Trivially-passing / vacuous-by-construction assertion | `TRIVIALLY_PASSING` | ERROR |
| Assumption constraining a design output / internal state | `ASSUME_CONSTRAINS_OUTPUT` | ERROR |
| Undeclared signal (not in manifest) | `UNDECLARED_SIGNAL` | ERROR |
| Mismatched literal width vs manifest signal width | `WIDTH_MISMATCH` | WARN |
| Property name does not reflect semantics | `NAME_SEMANTICS` | INFO (heuristic) |
| Requirement-traceability status (`// @requirement:` tags) | `REQ_TRACEABILITY` | INFO/WARN |
| Vacuity **RISK** heuristic (see non-claims) | `VACUITY_RISK` | INFO (heuristic) |

Plus:

* a **review-quality score** (0–100 + letter grade) — see `docs/SCORING_RUBRIC.md`;
* a **reviewer checklist** with `[x]` / `[!]` markers;
* an **optional LLM explanation layer** behind a deterministic **mock adapter**
  (`--explain`). The LLM layer *only annotates* deterministic findings; it never
  creates, deletes, or reclassifies them.

## Non-claims (read this)

* **This is NOT complete vacuity detection.** `VACUITY_RISK` is a *structural
  heuristic* only. Sound vacuity/reachability requires formal coverage analysis,
  which this tool does not run. All heuristic findings are labelled `[heuristic]`.
* This is **not** a full SystemVerilog parser. It handles a constrained SVA
  subset (see *Parser limitations*). Anything it cannot classify is still
  captured with a raw body, never silently dropped.
* A clean report does **not** mean an assertion is correct — only that these
  static checks found nothing. Compiling / passing static review ≠ verified.
* The RTL Intent Manifest here is a **fixture format** for grounding; it is not a
  real RTL front-end. It also ingests the **canonical** manifest produced by
  `rtl-intent-ingestor` (see *Canonical manifest interop* below), so the reviewer
  composes with the real producer rather than a bespoke shape.

## Canonical manifest interop (rtl-intent-ingestor)

`rtl-intent-ingestor` is the canonical **producer** of the RTL Intent Manifest
(schema `rtl-intent`, `schema_version` 0.1.0). This reviewer can consume that
manifest directly:

* `src/assertion_review/rtl_intent_adapter.py` maps the canonical manifest
  (`modules[].ports/nets/clock_candidates/reset_candidates`) down to the reviewer's
  `RtlIntentManifest` (name, role, width, reset polarity, clock/reset candidates).
* `--manifest-format auto|canonical|fixture` (default `auto`) auto-detects the
  format, so both the canonical manifest and the reviewer's own hand-written
  fixtures keep working (back-compat).
* `examples/manifests/fifo_queue.canonical.json` is a verbatim copy of
  `rtl-intent-ingestor/examples/expected/fifo_queue.json`.

Port ranges kept by the producer as unevaluated parameter text (e.g. `WIDTH - 1`)
are **not** guessed into a width — such signals default to width 1. Only integer
ranges yield a concrete width.

```bash
# Review against the CANONICAL rtl-intent-ingestor manifest:
assertion-review review examples/good/fifo_good.sv \
  -m examples/manifests/fifo_queue.canonical.json --fail-on none
```

## Install

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Review the bad corpus against its manifest (prints findings, score, checklist):
assertion-review review examples/bad/handshake_bad.sv \
  -m examples/manifests/handshake.manifest.json --fail-on none

# Clean example -> grade A, exit 0:
assertion-review review examples/good/fifo_good.sv \
  -m examples/manifests/fifo.manifest.json

# JSON output for tooling:
assertion-review review examples/bad/fifo_bad.sv \
  -m examples/manifests/fifo.manifest.json -f json --fail-on none

# With mock-LLM explanations:
assertion-review review examples/bad/handshake_bad.sv \
  -m examples/manifests/handshake.manifest.json --explain --fail-on none

# Self-contained smoke test:
assertion-review demo

# Export JSON Schema for the contracts:
assertion-review schema --out schemas
```

`--fail-on {error|warning|none}` controls the exit code (useful in CI gates).

## Example corpus

* `examples/good/` — curated *clean* assertions (handshake, FIFO). Grade A.
* `examples/bad/` — curated *defective* assertions, each line tripping specific
  checks (reset polarity, missing guard, assume-on-output, tautology, undeclared
  signal, width mismatch, constant consequent, unbounded delay, missing clock,
  trivially-passing, implication-style risk).
* `examples/manifests/` — RTL Intent Manifest fixtures.
* `examples/golden/` — **golden expected findings** used as test fixtures. Regenerate
  intentionally with `python scripts/regen_golden.py`.

## Parser limitations (constrained SVA subset)

Supported: `@(posedge/negedge clk)` clocking, `disable iff (...)`, top-level
`|->` / `|=>`, `##N` / `##[m:n]` / `##[n:$]` delays, `assert|assume|cover
property`, named `property ... endproperty` blocks, inline assertions, and
`// @requirement:` traceability tags. **Not** supported: sequence composition
beyond simple delays, `matched`/`triggered`, local variables, `let`, parameterised
properties, macros, multi-clock properties, and full expression typing. Width
checking is limited to `signal <op> N'bxxx` literal comparisons. Unsupported
constructs are captured as raw text, not misparsed into false structure.

## Repo docs

`ARCHITECTURE.md`, `THREAT_MODEL.md`, `EVIDENCE.md`, `docs/SCORING_RUBRIC.md`.

## License

MIT (placeholder) — see `LICENSE`. Public, non-proprietary content only.
