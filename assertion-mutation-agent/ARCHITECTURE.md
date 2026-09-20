# Architecture

## Components and dataflow

```
RTL (.v/.sv) ──► lexer.tokenize ──► operators.generate_mutants ──► [Mutant]
                                                                      │
SVA (.sva)  ──► sva.parse_properties ──► [PropertyRef] ──┐            │
                                                          ▼            ▼
                                          executor.<Adapter>.classify(mutant, src, props)
                                                          │
                                                          ▼
                                                    [MutantResult]
                                                          │
                                          agent.compute_score  (excludes invalid + inconclusive)
                                                          │
                                                          ▼
                                                   MutationReport ──► JSON / Markdown
```

## Modules

- `lexer.py` — deterministic tokenizer for a constrained Verilog subset with
  1-based line/column tracking. Comments, strings, sized literals, multi-char
  operators, and compiler directives are tokenized so mutations never land
  inside them.
- `operators.py` — one function per mutation operator. Each scans code tokens,
  finds syntactically safe mutation points, and emits `Mutant` objects with an
  exact `SourceDiff` and a stable ID. `generate_mutants` de-duplicates and
  returns a stably sorted list.
- `sva.py` — lexical extraction of property names and referenced design signals.
  Strips comments first; de-duplicates labeled asserts that merely instance a
  named property.
- `executor.py` — `ExecutorAdapter` Protocol + `MockExecutor` + the
  `get_executor` factory. The deterministic classification layer, separate from
  mutation generation.
- `verilator_executor.py` — OPTIONAL `VerilatorExecutor` implementing the same
  `ExecutorAdapter` interface. Compiles the mutated RTL + an auto-generated
  self-contained SVA harness with `verilator --binary --assert` and classifies
  each mutant from the real run. Degrades gracefully (ERROR, never a fake pass)
  when the Verilator binary is absent. Cleanly re-implemented from the reference
  sim runner in `spec-to-cov-agent` (no import of it).
- `agent.py` — orchestration: run pipeline, compute score, build the report,
  render Markdown.
- `cli.py` — Typer CLI (`run`, `mutate`, `properties`, `demo`).
- `models.py` — Pydantic v2 typed contracts.

## Typed input/output contracts (see `models.py`, `schemas/`)

- **Input**: RTL text, SVA text, operator selection, executor name.
- `Mutant`: `{mutant_id, operator, description, diff, mutated_signals, mutated_source}`
- `SourceDiff`: `{location, original_text, mutated_text, original_line, mutated_line}`
- `MutantResult`: `{mutant_id, operator, status, detected_by, detail, executor}`
- `ScoreBreakdown`: counts by status + `scored` + `mutation_score`
- `MutationReport`: score, results, `surviving_by_property`,
  `surviving_by_operator`, `surviving_mutants`, provenance.

JSON Schemas are exported under `schemas/`.

## Authority boundaries

- The tool **reads** RTL and SVA; it **never** modifies the user's source files.
  Mutated sources exist only in memory / in mutant records.
- The **mutation layer** proposes candidate defects. The **executor layer**
  (adapter) is the only component that decides detected/survived. This mirrors
  the "LLM proposes, deterministic tools validate" separation, here realized as
  "mutator proposes, executor classifies".
- The mock executor is explicitly heuristic and labeled as such; it does not
  claim formal or simulation evidence. The optional `verilator` executor is the
  only component that produces real simulation evidence, and only when the
  Verilator binary is installed; otherwise it reports ERROR, never a fake pass.
- No component treats `timeout`/`error`/`inconclusive` as a pass.

## Determinism / reproducibility

- Mutant IDs are content-derived (SHA1 of module/operator/position/text).
- `generate_mutants` returns a stably sorted list.
- The report records provenance: tool version, executor, input SHA-256 (16 hex),
  operator set, and a `git_sha` placeholder.
- A golden report (`tests/golden/counter_mutation_report.json`) pins the
  deterministic outputs in CI.
