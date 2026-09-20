# Assertion Mutation Agent

A **property-quality evaluation tool**. It estimates whether an SVA property
suite can detect intentionally introduced RTL defects by performing **real
source mutation** on a constrained synthesizable Verilog subset, classifying
each mutant with a configured executor adapter, and computing a mutation score.

This is **not** proof of complete verification, and a surviving mutant is **not**
proof that an assertion is wrong. A surviving mutant is an *undetected mutation
requiring investigation*.

## What actually works (v0.1)

- **Real source-mutation operators** that transform actual RTL text into
  compilable-looking mutants (single-token / small-span splices):
  - `relational_flip` — `<` `>` `<=` `>=` `==` `!=` `===` `!==` (correctly
    skips `<=` when it is a nonblocking assignment, not a comparison)
  - `boolean_negation` — negate an `if` condition: `cond` -> `!(cond)`
  - `enable_removal` — force an enable/valid guard true: `if (en)` -> `if (1'b1)`
  - `reset_polarity_flip` — flip `posedge`/`negedge` on a reset net
  - `reset_value_change` — perturb a reset/assign constant (bit flip / toggle)
  - `counter_incdec_change` — `x + 1` <-> `x - 1`
  - `assign_operand_swap` — `a - b` -> `b - a`
  - `valid_ready_gating_removal` — drop the ready term: `valid && ready` -> `valid`
  - `width_truncation` — narrow an RHS identifier to its LSB: `d` -> `d[0]`
    (only where syntactically safe)
- **Stable mutant IDs** (`module.operator.line.hash8`) reproducible across runs
  and machines, plus an **exact source diff** per mutant.
- A **constrained Verilog lexer** with correct 1-based line/column tracking that
  never mutates inside comments or strings.
- A **lexical SVA property extractor** that lists each property and the design
  signals it references.
- An **executor adapter interface** and a shipped **deterministic mock executor**
  (no real simulator) that classifies each mutant as
  `detected` / `survived` / `invalid` / `timeout` / `error` / `inconclusive`.
- An **OPTIONAL real-simulator executor** (`verilator`) behind the *same* adapter
  interface: it compiles the mutated RTL plus an auto-generated self-contained
  SVA harness under Verilator (`--binary --assert`) and classifies each mutant
  from the actual run. It **degrades gracefully** — with no `verilator` binary
  installed it reports `error` per mutant (never a fake pass) and the CLI prints
  a clear warning.
- **Mutation score computed EXCLUDING `invalid` and `inconclusive` mutants**;
  `timeout`/`error` are never counted as detected.
- Reports of **surviving mutants by property and by operator**, in JSON and
  Markdown.
- A **public toy RTL benchmark** (`counter`, `valid_ready`) + SVA suites +
  a **golden mutation report** used as a regression test.

## Install

```bash
python3.11 -m venv .venv         # or python3.13
. .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Run mutation analysis on the bundled toy benchmark:

```bash
ama run examples/counter.v examples/counter.sva --module counter \
    --json-out reports/counter_mutation_report.json \
    --md-out  reports/counter_mutation_report.md
```

Expected summary (deterministic):

```
Module: counter   Executor: mock
Mutation score: 63.64%  (7 detected / 11 scored)
total=11 detected=7 survived=4 invalid=0 timeout=0 error=0 inconclusive=0
Surviving by operator:
  boolean_negation: 2
  enable_removal: 1
  relational_flip: 1
```

The four survivors touch `load`, `en`, and `MAX_COUNT` — signals no property in
`counter.sva` references. They are exactly the gaps a reviewer should examine.

Other commands:

```bash
ama mutate examples/counter.v            # list the mutants (no execution)
ama properties examples/counter.sva      # show properties + referenced signals
ama demo                                 # print the bundled counter report
```

### Optional: run mutants through a real simulator (Verilator)

The `verilator` executor actually compiles and simulates each mutant. It requires
the [Verilator](https://verilator.org) binary on `PATH` (`brew install verilator`
or `apt install verilator`). It needs no cocotb — a self-contained SystemVerilog
harness is generated per run.

```bash
ama run examples/counter.v examples/counter.sva --module counter --executor verilator
```

Classification is derived from the real run:

- The **original** design must first pass the SVA harness (baseline). If it does
  not, mutants are `inconclusive` — we refuse to guess without a trustworthy
  baseline.
- A mutant whose assertion(s) fire is `detected`; one that runs clean is
  `survived`; one that fails to elaborate is `invalid`; a run over the timeout
  budget is `timeout`; any tool failure is `error`.
- `timeout` / `error` / `inconclusive` / `invalid` are **never** a pass and match
  the scoring rule (invalid + inconclusive excluded; timeout/error never counted
  as detected).

If Verilator is not installed the executor reports `error` for every mutant
(never a fake pass) and the CLI prints a warning. Attribution: the compile/run
subprocess orchestration is cleanly re-implemented from the reference sim runner
in the sibling `spec-to-cov-agent` project (no code is imported from it).

## The mock executor's detection model (heuristic, documented)

A mutant is `detected` iff **at least one property references a signal that the
mutation touches**. The intuition: a property that never observes the mutated
logic cannot catch its defect, so such a mutant `survives`. This is deliberately
conservative and is *good enough to demonstrate real mutation scoring* on the
toy benchmark. It is **not** a semantic/formal check. Swap in a real
compile+formal/simulation adapter behind the same `ExecutorAdapter` interface to
get sound detection evidence.

## Limitations and explicit non-claims

- **Constrained subset only.** The lexer/operators target a synthesizable
  Verilog subset (module/port/decl, `assign`, `always @(...)`, blocking and
  nonblocking assignment, `if/else`, sized literals). Unsupported constructs are
  simply not mutated; nothing is silently guessed.
- **The DEFAULT executor does NOT compile or simulate RTL.** The mock executor
  is heuristic; "compilable-looking" refers to structural splicing, not a
  compiler check. Only the optional `verilator` executor actually compiles and
  simulates, and only when the Verilator binary is installed.
- **The `verilator` executor is a bounded directed simulation, not a proof.** A
  `survived` result there means "not detected by this short deterministic
  stimulus of this suite", not that the assertion is complete or the mutant is
  equivalent.
- **A surviving mutant is not proof an assertion is wrong** — it is an
  undetected mutation requiring investigation.
- **The mutation score is a heuristic property-quality signal, not formal
  signoff**, coverage closure, or a completeness guarantee.
- `timeout` / `error` / `inconclusive` results are **never** treated as passes.
- Public, non-proprietary example RTL only.

## Roadmap (future phases, stubbed intent)

- More real executor adapters behind the same interface: a bounded *formal*
  (model-checking) classifier alongside the existing `verilator` simulation one,
  and richer, coverage-directed stimulus generation.
- Additional operators noted in the spec that need real elaboration to apply
  safely: `state-transition edge removal`, `FIFO pointer update omission`.
- Equivalent-mutant detection to reduce noise in the score.

See `ARCHITECTURE.md`, `THREAT_MODEL.md`, and `EVIDENCE.md` for details.
