# Architecture

## Purpose & authority boundary

The CDC/RDC Triage Agent is a **deterministic structural triage** tool. It reads
an RTL Intent Manifest and produces a *prioritized, heuristic* inventory of
candidate clock- and reset-domain crossings for a human reviewer.

It has **no authority** to declare a design safe. It never emits a PASS/clean
verdict and never modifies RTL, constraints, or signoff conclusions. The
`TriageReport` output carries a machine-readable `disclaimer` and `non_claims`
list encoding this boundary.

## Layers

```
manifest.json ──▶ manifest_models.Manifest (validate/parse, extra="ignore")
                        │
glossary.json ──▶ glossary.Glossary (optional, user-declared)
                        │
                        ▼
             analyze._ModuleAnalyzer  (deterministic structural core)
               1. domain assignment (proc → clock/reset)
               2. reg→reg data-flow edges (rhs.referenced_identifiers)
               3. synchronizer chain detection (forward fan-out)
               4. multi-bit + combinational-path flags
               5. risk ranking
                        │
                        ▼
             report_models.TriageReport (extra="forbid" output contract)
                        │
             ┌──────────┴───────────┐
             ▼                      ▼
     serialize.report_to_json   report.render_markdown
```

### Typed contracts

- **Input:** `manifest_models.Manifest` — a Pydantic mirror of the *subset* of
  the canonical `rtl-intent-ingestor` manifest schema this tool reads. Uses
  `extra="ignore"` so richer/newer manifests still load. Fields are *validated*,
  not merely annotated.
- **Optional input:** `glossary.Glossary` — user-declared synchronizer cells.
  This is trusted human assertion, not inference.
- **Output:** `report_models.TriageReport` — `extra="forbid"`, byte-stable JSON
  via `serialize.report_to_json`. Exported schema in `schemas/report.schema.json`
  (`cdc-rdc-triage schema`).

## The deterministic core (`analyze.py`)

1. **Domain assignment.** For each `always_ff` procedure, the clock is the
   edge-sensitive signal that matches a clock candidate (else the first edge
   signal); the reset is a reset candidate appearing as an edge (→ async) or in
   the control/condition signals (→ sync). Every register driven in that
   procedure inherits `(clock, reset)`.

2. **Data-flow edges.** For each register's nonblocking assignments, the set of
   referenced identifiers is extracted from the RHS *text* (`rhs.py`). A
   reference to another register in a different clock domain is a **CDC**
   candidate; same clock but different asynchronous reset is an **RDC**
   candidate.

3. **Synchronizer detection.** From the flop that *samples* the cross-domain
   source, the tool walks forward through same-clock-domain, single-fan-in,
   clean-forwarding flops (`_sync_chain_depth`). Depth ≥ 2 ⇒ 2-FF (or deeper)
   synchronizer **candidate** — structural evidence only. A glossary sync-cell
   instance on the path is honored as declared evidence.

4. **Multi-bit / combinational flags.** Width comes from the source signal's
   packed range when numeric (parameter expressions ⇒ width unknown). Multiple
   or mixed reg/non-reg sources ⇒ combinational path flag.

5. **Risk ranking.** A deterministic score combines kind (CDC/RDC), presence of
   sync evidence, multi-bit-ness, combinational reconvergence, and unknown
   width, mapped to HIGH/MEDIUM/LOW/INFO.

All steps are pure functions of the input — the same manifest always yields the
same report (asserted by `test_determinism`).

## Roadmap (explicitly deferred, not stubbed as fake)

- Cross-module / hierarchical crossing tracing through port connections.
- Gray-code / handshake / async-FIFO structural recognition for multi-bit
  transfers.
- Parameter arithmetic evaluation for width resolution.
- Integration with a real CDC engine to *prove* selected candidates (which
  would flip `heuristic`/`proven` on a `Crossing`).
