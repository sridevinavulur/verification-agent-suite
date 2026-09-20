# CDC/RDC Triage Agent

**Deterministic, structural, HEURISTIC triage of clock- and reset-domain
crossings from an [RTL Intent Manifest](../rtl-intent-ingestor).**

> ⚠️ **This is NOT a CDC/RDC signoff tool.** It performs a structural triage to
> help a human reviewer *prioritize* where to look. It never claims a design is
> "CDC clean" or "RDC clean", and it never proves any synchronizer correct. Use
> a commercial CDC/RDC signoff flow for verification-quality results.

## What it does

Given a manifest (hierarchy + clock/reset candidates + registers/procedures +
data-flow) and an optional synchronizer-cell glossary, it deterministically
produces:

- **Candidate crossing inventory** — every register-to-register data path that
  crosses a clock domain (CDC) or an asynchronous reset domain (RDC).
- **Source/destination domains** per crossing (`clk=…;rst=…`).
- **Synchronizer-pattern evidence** — structural **2-FF (and deeper) detection**:
  back-to-back single-fan-in flops in the destination clock domain.
- **Multi-bit crossing warnings** — wide crossings a plain FF sync cannot make safe.
- **Reset-domain crossing warnings** — same clock, different async reset.
- **Risk ranking** — deterministic severity/score for review order.
- **Source locations** — file:line:col for source and destination.
- **Reviewer checklist** and **explicit limitations**.

Every finding is tagged `HEURISTIC` (`heuristic: true`) and every synchronizer
claim is a *candidate*, backed only by structural clock/domain evidence.

## Scope (v0.1)

- **In scope:** per-module structural CDC/RDC triage, 2-FF synchronizer
  detection, multi-bit warnings, glossary-declared sync cells, risk ranking,
  JSON + Markdown reports, golden tests.
- **Out of scope (documented, not stubbed as fake):** cross-module/hierarchical
  crossing tracing through port connections, metastability/functional analysis,
  parameter arithmetic evaluation, generate/functions/tasks (invisible to the
  upstream parser). See `ARCHITECTURE.md` roadmap and `analyze.LIMITATIONS`.

## Install

```bash
python3.13 -m venv .venv          # 3.11+ required
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

The tool consumes a **manifest JSON**, not RTL directly. Generate one with the
`rtl-intent-ingestor`, then triage it:

```bash
# 1. produce a manifest from RTL (uses the sibling ingestor tool)
rtl-intent ingest examples/cdc_sync.sv -o /tmp/cdc_sync.json

# 2. triage the manifest -> JSON report (+ optional Markdown)
cdc-rdc-triage triage /tmp/cdc_sync.json -m /tmp/cdc_sync.report.md

# or a human-readable report straight to stdout
cdc-rdc-triage report /tmp/cdc_sync.json

# with an optional synchronizer-cell glossary
cdc-rdc-triage triage /tmp/cdc_sync.json -g examples/glossary.json
```

Pre-generated manifests and expected reports live in `examples/expected/`.

Example finding for `examples/cdc_sync.sv`:

- `bus_a -> bus_b` — **HIGH**, CDC, 8-bit, `no_synchronizer_evidence`,
  multi-bit hazard.
- `flag_a -> sync_ff1` — lower priority, CDC, 1-bit, **2-FF synchronizer
  candidate** (structural evidence only).

## Output contract

`TriageReport` (see `schemas/report.schema.json`, exported via
`cdc-rdc-triage schema`). Key fields per `Crossing`: `kind` (CDC/RDC),
`src/dst_signal`, `src/dst_domain`, `width_bits`, `multi_bit`, `sync_evidence`,
`sync_depth`, `severity`, `risk_score`, `heuristic`, `rationale`,
`src/dst_location`.

## Explicit non-claims

- Does **not** claim the design is CDC clean.
- Does **not** claim the design is RDC clean.
- Does **not** claim any synchronizer is correct.
- Does **not** prove metastability is handled.
- Findings are heuristic; expect false positives and false negatives.
- Absence of detected crossings is **not** a clean result.

## Development

```bash
ruff check .
pytest
python tests/regenerate_golden.py   # refresh golden reports after intended changes
```

## License

MIT (placeholder) — see `LICENSE`.
