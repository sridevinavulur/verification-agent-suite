# Architecture

FormalFlow-Scout is a deterministic RTL preprocessing tool. There is **no LLM in
the analysis path** — every result is produced by deterministic graph
algorithms. (An optional LLM explanation layer for *why* a partition was
suggested is out of scope for v0.1 and, per the spec, would be layer C only,
strictly separated from the deterministic layers A/B below.)

## Layered design (spec layers A / B / C)

- **A. Deterministic graph algorithms (SOUND over-approximation).**
  `graph_core.PackedGraph`: CSR adjacency, backward COI, sequential expansion,
  Tarjan SCC. `analyzer.Analyzer` steps 1–5.
- **B. Heuristic partition ranking (labelled HEURISTIC).**
  `analyzer.Analyzer._candidate_partitions` and cut/assumption emission.
- **C. Optional LLM explanations.** Not implemented in v0.1 (documented roadmap).

The two implemented layers are separated in code: nothing in layer B mutates the
COI computed in layer A, and every layer-B output object carries a `soundness`
field (`HEURISTIC`/`UNPROVEN`).

## Component / dataflow

```
 RTL (.v)  ─┐                     ┌─ verilog_parser.parse_verilog ─┐
            ├─ graph_builder ─────┤                                 ├─► DependencyGraph
 Manifest ──┘                     └─ build_from_manifest ──────────┘        │
 (rtl-intent JSON)                                                          ▼
 PropertySet (JSON) ───────────────────────────────► analyzer.Analyzer ──► CoiReport
                                                        │  (PackedGraph)      │
                                                        │                     ├─► JSON  (models.CoiReport)
                                                        └─ cpp_bridge (opt) ──┘   └─► DOT   (reporting.to_dot)
```

## Typed input/output contracts (Pydantic v2, `extra="forbid"`)

- **Inputs:** `DependencyGraph`, `PropertySet` (+ the RTL Intent Manifest dict,
  a superset we read defensively). See `schemas/*.schema.json`.
- **Output:** `CoiReport` — `coi_node_ids`, `excluded_logic` (with reasons),
  `sccs`, `domains`, `candidate_partitions` (each with `cut_signals`,
  `environment_assumptions`, `soundness_risks`), global `soundness_risks`,
  `stats`, `provenance`.

## Authority boundary

FormalFlow-Scout **reads** RTL/manifest/properties and **writes** an analysis
report. It never modifies RTL, assumptions, proof scope, budgets, or signoff
conclusions. It never declares a property proven. Cut assumptions are emitted as
`UNPROVEN` obligations requiring human/formal discharge.

## Graph core: data layout & cache rationale (C++ section)

The graph uses a **CSR (compressed sparse row)** layout in both the Python core
(`array('i', ...)`) and the C++ core:

- `offsets[i]..offsets[i+1]` index a single flat `adj` array grouped by source.
- Each node's fan-in is a **contiguous** slice → one sequential memory scan per
  node during traversal (cache-line friendly, prefetcher-friendly).
- **No per-node heap object** for adjacency (avoids pointer-chasing and
  allocator pressure); node metadata lives in a parallel array indexed by id.
- Edge kinds are packed as small ints (`array('B')` / `int8_t`) alongside `adj`.

**Tradeoff:** CSR is immutable — adding an edge means a rebuild. That is
acceptable here because the graph is built once and then queried many times
(incremental *property* queries reuse the immutable adjacency). A mutable graph
(adjacency lists) would trade locality for update speed we do not need.

**Memory estimate:** for `N` nodes and `E` edges, adjacency is
`4·E` (dst) `+ 1·E` (kind) `+ 4·(N+1)` (offsets) bytes ≈ **5·E + 4·N** bytes,
plus Python `GraphNode` objects for metadata. A 1M-node / 4M-edge graph → ~24 MB
of packed arrays (C++), well within memory for a preprocessing pass.

**Determinism:** node ids are dense `0..N-1` in first-seen order; each node's
neighbour slice is sorted by `(dst, kind)`; all emitted lists are in ascending
id order; Tarjan visits nodes in id order. Runs are bit-for-bit reproducible
(`test_analyzer.test_deterministic_output`).

**Concurrency (not used in v0.1):** COI queries are read-only over immutable
adjacency, so multiple property queries could run in parallel with no locks. The
determinism risk is result *ordering*; we would keep per-query result sorting to
preserve deterministic output. Tarjan is inherently sequential in this
implementation.

## The soundness argument for the COI (and its assumptions)

Edges point **from a signal to its drivers** (fan-in). The backward COI is the
set of nodes reachable from the property seeds over `COMB`, `HIER`, and (in the
sequential phase) `SEQ` edges. This is a **sound over-approximation** *provided*:

1. **No dependency is dropped by the parser.** RHS identifiers are extracted
   *lexically* (a superset of real identifiers) and **branch-guard** signals
   from `if/case` conditions are added to every assignment in the block. Both
   over-approximate, so the graph has **≥** the true edges. Any construct the
   parser cannot handle is recorded in `unresolved` — those must be reviewed,
   because a silently dropped construct *could* break this assumption.
2. **Black-box instance outputs are treated as free inputs.** Their internals
   are unknown; treating their outputs as unconstrained is the conservative
   (sound) choice, and it is flagged as a `blackbox_in_coi` risk.
3. **Manifest fidelity.** The manifest path can only see what the manifest
   encodes; e.g. it may miss branch-guard signals that the direct RTL parser
   recovers. This is a *fidelity* difference, documented and tested
   (`test_manifest_and_rtl_agree_on_data_coi`), not an unsound drop of a known
   dependency.

If assumption (1) is violated by an unhandled construct, the tool surfaces it in
`unresolved`/`notes` rather than pretending soundness — consistent with the rule
"never claim an unsound slice is a valid formal reduction."

## Why partitions are heuristic

A partition removes logic outside its boundary and replaces severed drivers with
free inputs. That only preserves the property if each free input is constrained
to over-approximate its real behaviour (assume-guarantee). We *emit* those
constraints as `UNPROVEN` `EnvironmentAssumption`s and flag
`unproven_cut_assumptions`, `multi_clock_coi`, and feedback-cycle risks — but we
do not and cannot discharge them, so partitions stay `HEURISTIC`.

## Roadmap (later phases, stubbed/documented only)

- pybind11 in-process C++ binding (v0.1 ships the subprocess JSON interface).
- LLM explanation layer C for partition rationale.
- Richer parser (parameters, generate blocks) — currently `unresolved`.
- Assume-guarantee obligation templates per protocol.
