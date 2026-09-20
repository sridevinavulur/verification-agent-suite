# RTL Intent Ingestor

Deterministic extraction of a **normalized design-intelligence manifest** from a
constrained, synthesizable Verilog subset. The manifest (stable JSON + a
Markdown summary) is designed to feed downstream verification tooling: SVA
candidate generation, formal cone-of-influence / partitioning, and verification
planning.

**Version 0.1 — no LLM.** Every value in the manifest is produced by
deterministic parsing or an explicitly-labelled heuristic. Nothing is
interpreted by a language model.

---

## What it actually does

Given one or more Verilog/SystemVerilog files, `rtl-intent` produces:

- **Hierarchy graph** — parent→child instantiation edges, with each child flagged
  as defined-in-inputs or external/black-box.
- **Module & instance inventory** — every module, every instance.
- **Ports, parameters, nets, registers** — with widths (as source text) and
  source locations.
- **Clock & reset candidates** — with **heuristic confidence scores** and an
  explicit rationale for each, plus inferred reset polarity/sync (heuristic).
- **Procedure summaries** — `always_ff` / `always_comb` / `always` classification
  (structural, from the sensitivity list), plus continuous-assign counts.
- **Source locations for every extracted item** — `file:line:col`.
- **Explicit unresolved-construct list** — anything outside the supported subset
  is surfaced, never silently dropped.

## Supported Verilog subset

- `module` / `endmodule`, ANSI and non-ANSI port lists
- `parameter` / `localparam` (values kept as source text; not evaluated)
- `input` / `output` / `inout` ports with `wire`/`reg`/`logic` and widths
- `wire` / `reg` / `logic` net declarations (comma lists, ranges)
- continuous `assign`
- `always` / `always_ff` / `always_comb` blocks with sensitivity lists,
  `begin/end` bodies, blocking (`=`) and nonblocking (`<=`) assignments
- basic module instances (named `.p(a)` and positional connections)

## Non-claims / limitations (read this)

This is **not** a full SystemVerilog parser and makes **no** claim of full
SystemVerilog semantics. The following are **not** modeled (each occurrence is
recorded in the manifest's `unresolved` list):

- generate / for-generate blocks
- functions and tasks
- structs / unions / enums / typedefs / interfaces / packages
- SystemVerilog assertions (SVA)
- preprocessor macros beyond raw passthrough
- `case`/`casez`/`casex` statement bodies (recorded, body not modeled)
- parameter expression evaluation (ranges/values kept as text)

Clock/reset detection is a **heuristic** based on names and `always_ff`
sensitivity structure. Confidence scores are heuristic signals, **not** a formal
determination of clocking or reset intent. "Register" here means *a nonblocking
assignment target under an `always_ff`* — a structural definition, not a proven
state element.

## Install

```bash
python3.11 -m venv .venv        # 3.11+ required
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# JSON manifest to stdout
rtl-intent ingest examples/counter.sv

# JSON + Markdown to files, with an explicit top module
rtl-intent ingest examples/valid_ready.sv -o out.json -m out.md --top vr_top

# Human-readable Markdown summary to stdout
rtl-intent summary examples/fifo_queue.sv

# List parser adapters, or export the JSON Schema
rtl-intent adapters
rtl-intent schema -o schemas/manifest.schema.json
```

## Parser-adapter interface

Parsing is behind a pluggable adapter (`src/rtl_intent/adapters/base.py`) so a
Slang / tree-sitter / Surelog-UHDM frontend can be added later without changing
downstream code. v0.1 ships one working adapter: `builtin` (a real tokenizer +
recursive parser for the subset above).

```bash
rtl-intent ingest examples/counter.sv --adapter builtin
```

## Data policy

Public, non-proprietary content only. The bundled `examples/` are generic toy
RTL (counter, FIFO-like queue, valid/ready producer/consumer). Do not commit
proprietary RTL, customer/employer names, internal tool names, credentials, or
private paths. See `SECURITY.md` and `THREAT_MODEL.md`.

## Repository layout

```
src/rtl_intent/        package: models, lexer, parser adapters, manifest, CLI
  models.py            Pydantic v2 typed contracts
  lexer.py             deterministic tokenizer
  adapters/            parser-adapter interface + built-in Verilog parser
  heuristics.py        clock/reset candidate detection (heuristic)
  manifest.py          assemble manifest (parse + heuristics + hierarchy)
  report.py            Markdown summary renderer
  serialize.py         stable JSON serialization
  cli.py               Typer CLI (rtl-intent)
examples/              public toy RTL
tests/golden/          golden JSON manifests compared by the test suite
tests/                 pytest suite (parser, heuristics, golden, CLI)
schemas/               exported JSON Schema for the manifest contract
```

## Documentation

- `ARCHITECTURE.md` — components, contracts, authority boundaries
- `THREAT_MODEL.md` — hallucination, unsafe assumptions, leakage, reproducibility
- `EVIDENCE.md` — each claim tied to code, test, and reproduce command
- `LICENSE` — MIT

## License

MIT. See `LICENSE`.
