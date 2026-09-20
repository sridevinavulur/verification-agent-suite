# Counterexample Triage Agent (`cx-triage`)

Deterministic, evidence-grounded triage of formal / simulation counterexamples.

Given a **waveform trace** (VCD or a simple JSON format), a structured
**assertion-failure record**, and an optional **RTL Intent Manifest**, `cx-triage`
produces a cycle-by-cycle, evidence-linked debug report:

- an **event timeline** anchored to clock cycles,
- the **antecedent-activation cycle** and the **first divergence cycle**,
- **property context** and **source location**,
- the **relevant RTL cone** (backward dependency reachability over the manifest),
- **source citations** for the property and every cone symbol,
- **ranked root-cause hypotheses** (design bug vs property vs environment vs
  reset vs modeling), each with a confidence and concrete, trace-grounded
  evidence,
- **unresolved questions**, and
- a **reproduction command** plus **artifact list**.

An optional LLM narrative is available behind an **offline mock adapter**; it is
clearly labeled as advisory and is never the source of any evidence.

This is a **heuristic triage** tool implementing the Counterexample Triage Agent
described in section 6.3 of the verification prompt pack. It follows the shared
BUILD_STANDARD.md.

## What actually works (scope)

- **Real VCD parser** for the common subset: `$timescale`, `$scope`/`$upscope`,
  `$var wire|reg`, `$enddefinitions`, `#<time>`, scalar changes (`0!`/`1!`/`x!`/
  `z!`) and vector changes (`b<bits> !`). Real-valued (`r...`) dumps are skipped
  (documented limitation), never crashing the run.
- **Simple JSON trace format** for easy CI fixtures. VCD and JSON traces of the
  same scenario produce **byte-identical** triage output (tested).
- **Deterministic evidence extraction**: clock-edge cycle indexing, antecedent
  activation (skipping reset), first-divergence detection for overlapping
  (`|->`) and non-overlapping (`|=>`) implications with `##[min:max]` windows,
  and plain invariants.
- **Cone of influence**: real backward graph traversal over the manifest's
  `drivers` edges (labeled heuristic/structural, not a sound formal reduction).
- **Ranked hypotheses** with a transparent scoring heuristic that always retains
  alternatives.
- **Markdown and JSON reports**, golden-tested.
- **Canonical RTL Intent Manifest interop**: the manifest input accepts both the
  repo's native fixture *and* the canonical schema emitted by the
  `rtl-intent-ingestor` tool (auto-detected; see below).
- **Optional real reproduction** behind the deterministic default: a clean
  executor adapter with an offline deterministic path and an optional
  Verilator/cocotb path that degrades gracefully (skips, never fails) when
  Verilator is absent.

## Manifest interop (canonical RTL Intent Manifest)

The `--manifest` input accepts two shapes, auto-detected:

1. the repo's **native** `RTLIntentManifest` fixture (a flat `symbols` map with
   `drivers` fan-in edges), and
2. the **canonical** manifest produced by the `rtl-intent-ingestor` tool
   (`rtl-intent-ingestor/schemas/manifest.schema.json`): a per-module structure
   with `ports`, `nets`, `registers`, `continuous_assigns`, and `procedures`.

`src/cx_triage/manifest_adapter.py` projects the canonical structure onto the
engine's flat symbol/driver model: it declares a symbol per port/net/register and
**reconstructs backward-dependency (fan-in) edges** structurally from continuous
assigns (`lhs <- rhs`) and procedures (`lhs <- rhs ∪ condition_signals`). This is
a structural projection, not RTL evaluation; self-loops (registered feedback) and
references outside the module are dropped so the cone traversal terminates. Names
are qualified as `<top>.<name>` by default. Both shapes are covered by tests.

## Optional real reproduction

Triage runs on an *already-captured* counterexample. The optional executor layer
(`src/cx_triage/executor.py`) answers a separate question — *can the failure be
re-run?* — behind a clean `ReproExecutor` interface:

- **`DeterministicExecutor` (default):** confirms the captured trace/failure
  artifacts are present and loadable, with no subprocess. Fully offline and
  CI-safe.
- **`VerilatorReproExecutor` (opt-in):** re-implements (self-contained, no import
  of `spec-to-cov-agent`) the reference sim runner's lint → compile → run → parse
  sequence over Verilator (+ optional cocotb). It **degrades gracefully**: if
  Verilator is absent it returns `SKIPPED`, never an error and never a pass.

Reproduction is **advisory context only** — it is attached to the report as a
clearly-labeled `reproduction_attempt` and it **never** re-ranks the hypotheses,
never adds evidence, and never turns a `SKIPPED`/`TIMEOUT`/`ERROR` into a pass.
The deterministic hypothesis ranking stays authoritative (see
`src/cx_triage/compose.py`, which adopts the reference CRAVS "try structured,
fall back to deterministic" pattern but inverts the authority: structured/external
paths are advisory, deterministic decides).

```bash
cx-triage triage --trace ... --failure ... --manifest ... --reproduce
```

## Install

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Run the bundled toy benchmark end-to-end (a 4-bit counter with a known bug):

```bash
cx-triage demo
```

Triage your own inputs:

```bash
cx-triage triage \
  --trace examples/toy_counter/counter_fail.vcd \
  --failure examples/toy_counter/failure.json \
  --manifest examples/toy_counter/manifest.json \
  --out-md report.md --out-json report.json
```

Inspect a trace:

```bash
cx-triage parse --trace examples/toy_counter/counter_fail.vcd
```

Export a data-contract schema:

```bash
cx-triage schema report   # or: failure | manifest
```

## The bundled benchmark

`examples/toy_counter/` is a public toy 4-bit up-counter with an **intentional,
documented bug**: the increment is gated by `en & ~stall` instead of `en`
(`counter.v`, line 21). The property `p_inc` (`en |=> count_advanced`,
`counter.sva`) therefore fails when `stall` is high while `en` is high.

`counter_fail.vcd` is a real VCD counterexample of that failure. `cx-triage`
locates the antecedent activation (cycle 2), the first divergence (cycle 6),
includes `tb.stall` in the RTL cone, and ranks `design_bug` first **with
evidence** — while still retaining property/reset/environment/modeling
alternatives.

`examples/env_gap/` is a contrasting case: a failing `req |=> gnt` property whose
counterexample is actually an **environment gap** (the stimulus never asserts
`req`). Here `cx-triage` ranks `environment_issue` first and emits **no**
design-bug hypothesis — demonstrating that a failing property is not treated as
necessarily a design bug.

## Authority boundary and non-claims

The agent **may**: extract signals/events, identify divergence/antecedent
cycles, summarize the timeline, cite the property and cone locations, propose
ranked hypotheses, and recommend next debug queries.

The agent **must not** (enforced in code + tests):

- **declare a design bug without evidence** — the model layer rejects an
  evidence-free `design_bug` hypothesis;
- **modify RTL or assertions** — the tool only reads them;
- **hide alternative hypotheses** — alternatives are always retained;
- **treat a failing property as necessarily a design bug** — it may be a
  property, environment, reset, or modeling issue.

**Non-claims.** This tool does **not** perform formal proof, semantic SVA
evaluation, full SystemVerilog parsing, or signoff. The cone is a structural
heuristic, not a sound reduction. Hypothesis confidences are heuristic scores,
not probabilities. A produced report requires human review before any
conclusion.

## Result vocabulary

This tool triages a **FAIL** (a counterexample was produced). It never
reclassifies a TIMEOUT, ERROR, or INCONCLUSIVE result as a pass; those states
are outside its input scope and must be handled upstream.

## Repository layout

```
src/cx_triage/     models.py, parser.py, triage.py, report.py, llm.py, cli.py
examples/          toy_counter/ (RTL+bug+VCD+JSON+manifest+failure), env_gap/
schemas/           exported JSON Schema for the data contracts
tests/             pytest suite incl. golden report tests (tests/golden/)
docs/, *.md        ARCHITECTURE, THREAT_MODEL, EVIDENCE, this README
```

## Roadmap (out of scope for v0.1)

- FST parsing (currently VCD + JSON only).
- Multi-bit / concatenated antecedent & consequent expressions.
- Real (non-mock) LLM provider adapter behind an env var (still advisory-only).
- Deeper Verilator/cocotb reproduction wiring (regenerating a stimulus from the
  captured trace); today the optional executor re-runs supplied RTL/TB only.

## Attribution

The optional Verilator/cocotb reproduction path (`src/cx_triage/executor.py`) and
the advisory "try structured, fall back to deterministic" composition pattern
(`src/cx_triage/compose.py`) are **re-implemented, self-contained** adaptations of
patterns in the `spec-to-cov-agent` reference project
(`veri_forge/sim/{runner.py,verilator.py}` and `veri_forge/cravs/integration.py`).
No reference code is imported and there is no dependency on that project; the
authority boundary is inverted so the deterministic layer remains authoritative.
The canonical manifest interop reads
`rtl-intent-ingestor/schemas/manifest.schema.json`.

## License

MIT (placeholder). Public, non-proprietary example content only.
