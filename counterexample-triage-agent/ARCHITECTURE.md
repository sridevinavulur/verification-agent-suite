# Architecture

`cx-triage` is a deterministic pipeline with an optional, clearly-isolated LLM
narrative layer. The deterministic layer is authoritative; the LLM layer only
rephrases already-extracted evidence.

## Components

| Module | Responsibility |
| --- | --- |
| `models.py` | Pydantic v2 data contracts (validate at runtime). |
| `parser.py` | VCD (common subset) parser + JSON trace loader → `WaveTrace`. |
| `triage.py` | `TriageEngine`: deterministic evidence extraction + hypothesis ranking. |
| `report.py` | Pure Markdown renderer for a `TriageReport`. |
| `llm.py` | `LLMAdapter` protocol + offline `MockLLMAdapter` (advisory narrative). |
| `cli.py` | Typer CLI: `triage`, `parse`, `demo`, `schema`. |

## Dataflow

```
trace file (.vcd/.json) ─┐
assertion-failure (.json)─┼─► TriageEngine.run() ─► TriageReport ─► render_markdown()
RTL manifest (.json, opt)─┘                                     └─► model_dump_json()
                                                    (optional) └─► MockLLMAdapter.narrate()
```

## Typed input/output contracts

**Inputs**

- `WaveTrace` — `{timescale, signals: {name: {width, samples: [WaveValue...]}}, end_time}`.
- `AssertionFailure` — property name/text, source file+line, clock (+edge),
  reset (+polarity), antecedent/consequent signal names, implication style,
  `[delay_min, delay_max]`, optional tool `failure_time`. Delay range and clock
  edge are validated.
- `RTLIntentManifest` (optional) — `{design_top, symbols: {name: RTLSymbol}}`
  where `RTLSymbol` has kind, width, `SourceLocation`, and `drivers` (fan-in
  edge list) used for cone traversal + citations.

**Output**

- `TriageReport` — property context, `antecedent_cycle`/`first_divergence_cycle`
  (and times), `timeline`, `rtl_cone`, `citations`, ranked `hypotheses`,
  `unresolved_questions`, `reproduction`, and optional `llm_narrative`.

Exported JSON Schemas live in `schemas/`.

## Deterministic algorithms

1. **Clock-edge cycle indexing** (`_clock_edge_times`): walk the clock signal's
   samples and record posedge/negedge times; cycle *i* = *i*-th such edge.
2. **Antecedent activation** (`find_antecedent_cycle`): first cycle where the
   antecedent signal is `1` and reset is inactive.
3. **First divergence** (`find_first_divergence`): for each activating
   antecedent cycle, check whether the consequent holds within the effective
   `[min,max]` window (shifted by 1 for `|=>`); the first activation whose window
   contains no holding consequent is the divergence. Windows running off the end
   of the trace are treated as *unresolved*, not failures. Invariants (no
   antecedent) diverge at the first cycle the consequent is not `1`.
4. **Cone of influence** (`compute_cone`): backward reachability from
   consequent/antecedent seeds through `RTLSymbol.drivers`; output is sorted for
   determinism. Labeled structural/heuristic, not a sound reduction.
5. **Hypothesis ranking** (`build_hypotheses`): transparent additive scoring per
   category; sorted by confidence then category name. A `design_bug` hypothesis
   is emitted only when there is a real divergence, outside reset, with a
   defined (non-x/z) consequent and a located antecedent — otherwise it is not
   proposed at all.

## Authority boundaries

- The engine holds parsed copies of inputs and **never writes back** to RTL,
  assertions, or trace files.
- `RootCauseHypothesis` **rejects** an evidence-free `design_bug` at the model
  layer, independent of engine logic.
- The engine **always** appends the `property_issue` hypothesis, so alternatives
  are never hidden.
- The LLM adapter receives a finished `TriageReport` and returns prose only; it
  cannot mutate evidence fields.
- The optional reproduction executor (`executor.py`) and its composition
  (`compose.py`) are **advisory only**: they attach a labeled
  `reproduction_attempt` and may add unresolved-question notes, but never
  re-rank/add/remove hypotheses, never add evidence, and never turn a
  `SKIPPED`/`TIMEOUT`/`ERROR` reproduction into a pass. A missing Verilator is a
  `SKIPPED`, not a failure.
- The manifest adapter (`manifest_adapter.py`) projects the canonical
  `rtl-intent-ingestor` manifest onto the flat symbol/driver model (self-loops
  and out-of-module references dropped); it is a pure text->model transform and
  keeps back-compat with the native fixture.

## Determinism guarantees

- No wall-clock, RNG, or network usage anywhere in the deterministic path.
- Cone ordering and hypothesis ordering are explicitly sorted.
- VCD- and JSON-sourced traces yield identical `TriageReport`s
  (`test_vcd_and_json_traces_equivalent`, `test_golden_*`).
