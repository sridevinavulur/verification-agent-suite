# reset-intent-agent

Deterministic extraction of **reset topology** from public RTL, plus generation
of **reviewable candidate reset-behavior SVA**. Part of a family of
verification-integrated agent prototypes.

This tool performs **STRUCTURAL detection**. It is *not* a reset-signoff tool and
does not verify reset intent. Every inferred reset-domain relationship is
labelled **HEURISTIC** until reviewed, and reset polarity is **never inferred
silently** — when evidence is ambiguous the polarity is reported as `unknown`
with an explicit ambiguity record.

## What it does

Given a constrained Verilog/SystemVerilog file **or** a canonical
[RTL Intent Manifest](../rtl-intent-ingestor/schemas/manifest.schema.json), it
deterministically analyzes:

- reset **candidates** and **polarity** (with per-evidence voting)
- **synchronous vs asynchronous** reset usage (structural)
- reset **fanout** and **domain membership** (heuristic grouping)
- reset **assertion / deassertion** behavior (via candidate SVA + covers)
- **interface quiescence** during reset (directed-test recommendation)
- **state initialization** (reset values per register)
- **reset recovery** (cover recommendations)
- possible **reset-domain crossings** (structural, heuristic)

### Outputs

- **Reset intent manifest** (JSON, validated by a Pydantic v2 schema)
- **Reset graph** (JSON in the manifest + Graphviz **DOT**)
- **Candidate SVA** properties (sva-intent-engine style: `status = candidate`)
- **Risks & ambiguities** with severities
- **Source-location evidence** for extracted items
- **Test / cover recommendations**
- **Markdown report**

## Install

```bash
python3.13 -m venv .venv          # 3.11+ works; 3.13 tested
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Analyze RTL -> reset intent manifest (JSON)
reset-intent analyze examples/rtl/counter_async_low.sv

# Emit the reset graph as Graphviz DOT
reset-intent graph examples/rtl/dual_reset_domains.sv -o reset.dot
dot -Tsvg reset.dot -o reset.svg          # optional, needs graphviz

# Human-readable Markdown report
reset-intent report examples/rtl/dual_reset_domains.sv

# Candidate reset-behavior SVA
reset-intent sva examples/rtl/counter_async_low.sv

# Consume an upstream RTL Intent Manifest instead of raw RTL (INTEROP)
reset-intent analyze examples/manifests/counter_manifest.json

# Inject reset-defect mutants (polarity flip, reset-value change, reset removal)
reset-intent mutate examples/rtl/counter_async_low.sv --output-dir /tmp/mutants

# Export the manifest JSON Schema
reset-intent schema -o schemas/reset_intent_manifest.schema.json
```

### Example: ambiguous polarity is never guessed

`examples/rtl/ambiguous_polarity.sv` names its reset `rst_n` (suggesting
active-low) but uses it in a bare positive guard `if (rst_n)` (suggesting
active-high). The tool refuses to pick:

```
$ reset-intent sva examples/rtl/ambiguous_polarity.sv
// P001 status=candidate polarity=unknown
p_reset_state_q: assert property (
  @(posedge clk) (/* REVIEW: polarity of rst_n unknown */ rst_n) |-> (q == 4'h0)
);
```

## Interop

- **Input**: consumes the canonical RTL Intent Manifest schema
  (`rtl-intent-ingestor/schemas/manifest.schema.json`) via
  `manifest_adapter.py`, or raw RTL via the built-in subset parser.
- **Output**: candidate SVA is emitted in **sva-intent-engine** style —
  `status: candidate`, never `verified`.

## Scope (v0.1) — narrow but real

Supported RTL subset:

- `module` / `endmodule`, ANSI and non-ANSI port declarations
- `always @(...)`, `always_ff`, `always_comb` with sensitivity lists
- `posedge` / `negedge` edges
- the first `if (...) ... else ...` reset guard in an edge-sensitive block
- nonblocking (`<=`) assignments and constant reset values
- comment/string stripping (offsets preserved)

Anything not understood is surfaced (never silently dropped) as an
`UnresolvedConstruct` / ambiguity.

## Non-claims (read this)

- This is **not** a CDC/RDC signoff tool. Reset-domain crossings are
  **structural heuristics** flagged for review, not proven hazards.
- Candidate SVA is **candidate only**. The tool does **not** compile, simulate,
  run formal, or check semantics. "Property emitted" ≠ "property correct".
- Reset polarity marked `active_high`/`active_low` reflects **structural
  evidence**, not verified design intent — confirm before use.
- Reset-domain membership is a **heuristic grouping** by shared reset signal.
- No LLM is used in the analysis path; outputs are deterministic structural
  facts and clearly labelled heuristics.

## Data policy

Public, non-proprietary toy RTL only. No secrets, employer/customer names,
internal tool names, or proprietary paths.

## Development

```bash
ruff check .
pytest
```

See `ARCHITECTURE.md`, `THREAT_MODEL.md`, and `EVIDENCE.md` for details.
License: MIT (placeholder).
