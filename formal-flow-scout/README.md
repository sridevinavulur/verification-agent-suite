# FormalFlow-Scout

RTL **cone-of-influence (COI)** and **partition** analysis for formal-verification
preprocessing. Given a synthesizable-Verilog subset (or an RTL Intent Manifest)
and a property signal set, FormalFlow-Scout builds a dependency graph and
computes:

- backward **combinational COI** from the property seed signals,
- **sequential expansion** through state elements (registers),
- **clock / reset domain** annotation,
- **strongly-connected components** (iterative Tarjan),
- **candidate proof partitions** from hierarchy / SCC / interface cuts.

It emits: a COI graph JSON, selected vs excluded logic with reasons, candidate
partitions, cut signals, **environment assumptions required at cuts (as explicit
`UNPROVEN` obligations)**, soundness-risk flags, a statistics report, and
**Graphviz DOT** output.

## What is sound vs heuristic (read this first)

| Result | Label | Meaning |
| --- | --- | --- |
| Cone of influence | **SOUND** over-approximation | For the supported Verilog subset, the COI includes *every* signal that can structurally affect a property seed. It never drops a real dependency (see `ARCHITECTURE.md` for the argument and its assumptions). |
| Candidate partitions, cut placement, ranking | **HEURISTIC** | Structural grouping only. There is **no** preservation argument. |
| Environment assumptions at cuts | **UNPROVEN** obligations | What a human/formal tool must discharge for a cut to become a valid reduction. |

**Non-claims (things this tool does NOT do):**

- It does **not** prove any property, and does **not** claim any partition is a
  valid formal reduction. A cut is only valid once every emitted `UNPROVEN`
  environment assumption is discharged — this tool cannot discharge them.
- It does **not** perform full SystemVerilog semantic analysis. It parses a
  constrained subset and records everything it cannot parse.
- It does **not** do CDC/RDC signoff. Multi-clock cones are *flagged* as a
  soundness risk, not cleared.
- A cyclic SCC in the COI is *flagged*; cutting inside a feedback loop is
  labelled UNSOUND-without-assume-guarantee.

## Install

```bash
python3.11 -m venv .venv          # 3.10+ required
source .venv/bin/activate
pip install -e ".[dev]"
```

No compiler is needed — the pure-Python graph core is authoritative. The
optional C++17 core is only for large-graph performance (see below).

## Quickstart

```bash
# Analyse a Verilog file against a property seed set:
formal-flow-scout analyze examples/fifo_property.json \
    --rtl examples/fifo_ctrl.v \
    -o report.json --dot coi.dot

# Or consume an RTL Intent Manifest (from rtl-intent-ingestor):
formal-flow-scout analyze examples/counter_property.json \
    --manifest examples/counter_manifest.json -o report.json

# Just dump the dependency graph:
formal-flow-scout build-graph --rtl examples/counter.v -o graph.json

# Export the report JSON Schema:
formal-flow-scout schema -o schema.json

# Bundled end-to-end demo:
formal-flow-scout demo

# Render DOT (if graphviz installed):
dot -Tsvg coi.dot -o coi.svg
```

Example text summary (`demo`):

```
FormalFlow-Scout COI report: property 'no_overflow'
  top module          : fifo_ctrl
  COI nodes           : 11 (reg=1, comb=4)
  excluded nodes      : 3
  SCCs (cyclic)       : 7 (1), largest=5
  candidate partitions: 2 (ALL HEURISTIC)
  SOUNDNESS RISKS:
    [MEDIUM] combinational_or_sequential_cycle: 1 cyclic SCC(s) in the COI ...
```

In the FIFO example the property `{full, push, occ}` correctly **excludes**
`wr_ptr` and `rd_ptr` (they do not drive occupancy/full) — a real, checkable COI
reduction — and **flags** the genuine `occ ↔ do_push ↔ full` feedback cycle.

## Optional C++17 core

```bash
cd cpp && make          # builds ./coi_core (needs a C++17 compiler)
cd ..
formal-flow-scout analyze ... --use-cpp
```

The C++ core computes the same COI over a CSR graph via a subprocess JSON
interface. The CLI **cross-checks** its output against the Python core and falls
back to Python on any disagreement or if the binary is missing. Tests pass with
or without it.

## Supported Verilog subset

`module`/`endmodule`, ANSI & non-ANSI ports, `input/output/inout`,
`wire/reg/logic`, continuous `assign`, `always @(...)` (edge → sequential,
`*`/`always_comb` → combinational), blocking/nonblocking assignments,
`if/else`/`case` **branch-guard dependencies** (captured, not dropped), simple
named-connection instances (flattened; undefined children → black boxes).

Anything else is recorded in the manifest/parse `unresolved` list rather than
silently ignored — silent drops would make the COI unsound.

## Documentation

- `ARCHITECTURE.md` — components, contracts, data-layout/cache rationale, the
  soundness argument for the COI.
- `THREAT_MODEL.md` — hallucination, unsafe assumptions, leakage, reproducibility.
- `EVIDENCE.md` — every claim tied to code, test, and a reproduce command.

## License

MIT (placeholder) — see `LICENSE`. Public toy RTL only; no proprietary content.
