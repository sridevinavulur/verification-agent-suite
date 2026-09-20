# Evidence

Each claim below is tied to source, a test, and a reproduce command. Run all
tests with `pytest` inside the venv. Distinguish **implementation evidence**
(the code does what is described) from **experimental-performance evidence**
(none is claimed here — the executor is a mock).

| ID | Claim | Source | Test | Reproduce |
|----|-------|--------|------|-----------|
| C1 | Real relational-operator flip that skips nonblocking `<=` | `operators.op_relational_flip`, `operators._is_nonblocking_assign` | `test_operators.py::test_relational_flip_*` | `pytest tests/test_operators.py -k relational` |
| C2 | Boolean condition negation wraps `if` condition | `operators.op_boolean_negation` | `test_operators.py::test_boolean_negation_wraps_condition` | `pytest -k boolean_negation` |
| C3 | Enable removal forces guard true only for enable-like names | `operators.op_enable_removal` | `test_operators.py::test_enable_removal_*` | `pytest -k enable_removal` |
| C4 | Reset polarity flip on reset nets | `operators.op_reset_polarity_flip` | `test_operators.py::test_reset_polarity_flip` | `pytest -k reset_polarity` |
| C5 | Reset value change perturbs constants | `operators.op_reset_value_change`, `operators._perturb_constant` | `test_operators.py::test_reset_value_change_*` | `pytest -k reset_value` |
| C6 | Counter inc/dec swap | `operators.op_counter_incdec_change` | `test_operators.py::test_counter_incdec_change` | `pytest -k incdec` |
| C7 | Assignment operand swap | `operators.op_assign_operand_swap` | `test_operators.py::test_assign_operand_swap` | `pytest -k operand_swap` |
| C8 | Valid/ready gating removal (handshake pairs only) | `operators.op_valid_ready_gating_removal` | `test_operators.py::test_valid_ready_gating_*` | `pytest -k gating` |
| C9 | Width truncation where syntactically safe | `operators.op_width_truncation` | `test_operators.py::test_width_truncation_adds_bit_select` | `pytest -k width_truncation` |
| C10 | Stable, reproducible mutant IDs | `models.Mutant.make_id` | `test_operators.py::test_generate_mutants_stable_ids` | `pytest -k stable_ids` |
| C11 | Every mutant records an exact source diff and changes the source | `models.SourceDiff`, `operators._build_mutant` | `test_operators.py::test_mutants_actually_change_source` | `pytest -k change_source` |
| C12 | Lexer tracks correct 1-based line/col and skips comments/strings | `lexer.tokenize` | `test_lexer.py` | `pytest tests/test_lexer.py` |
| C13 | SVA extraction of properties + referenced signals; comment-proof | `sva.parse_properties` | `test_sva.py` | `pytest tests/test_sva.py` |
| C14 | Mock executor classifies detected/survived/invalid/inconclusive | `executor.MockExecutor.classify` | `test_executor_and_score.py::test_*` | `pytest tests/test_executor_and_score.py` |
| C18 | Optional `verilator` executor selectable via same interface | `executor.get_executor`, `verilator_executor.VerilatorExecutor` | `test_verilator_executor.py::test_factory_returns_verilator_executor` | `pytest -k factory_returns_verilator` |
| C19 | Graceful degradation: no verilator binary -> ERROR, never a fake PASS | `verilator_executor.VerilatorExecutor.classify`, `verilator_available` | `test_verilator_executor.py::test_graceful_degradation_when_verilator_missing` | `pytest -k graceful_degradation` |
| C20 | Real-sim tests auto-skip when verilator absent (CI stays green) | `test_verilator_executor.requires_verilator` | `test_verilator_executor.py::test_real_*` | `pytest -k real_ -v` |
| C21 | Real run: original baseline passes; reset-value mutant DETECTED; overflow mutant SURVIVED; compile-fail INVALID (needs Verilator) | `verilator_executor.VerilatorExecutor` | `test_verilator_executor.py::test_real_baseline_passes / test_real_mutant_detected / test_real_mutant_survives_when_not_observed / test_real_compile_failure_is_invalid` | `pytest -k real_ ` |
| C15 | Score EXCLUDES invalid + inconclusive; timeout/error never a pass | `agent.compute_score` | `test_executor_and_score.py::test_score_*` | `pytest -k score` |
| C16 | End-to-end report is deterministic and matches a golden | `agent.run_mutation_analysis` | `test_golden.py` | `pytest tests/test_golden.py` |
| C17 | CLI runs end-to-end and writes JSON/Markdown | `cli.py` | `test_cli.py` | `pytest tests/test_cli.py` |

## Benchmark inputs

- `examples/counter.v` / `examples/counter.sva` — public toy 8-bit saturating
  counter and candidate SVA suite (MIT, authored for this repo).
- `examples/valid_ready.v` / `examples/valid_ready.sva` — public toy valid/ready
  handshake stage and candidate SVA suite (MIT, authored for this repo).

## Golden report

- `tests/golden/counter_mutation_report.json` — pinned deterministic output for
  the counter benchmark. Regenerate with:
  `ama run examples/counter.v examples/counter.sva --module counter --json-out tests/golden/counter_mutation_report.json`

## Reproduce everything

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
ama run examples/counter.v examples/counter.sva --module counter \
  --json-out reports/counter_mutation_report.json \
  --md-out reports/counter_mutation_report.md
```

## Optional real-simulator executor (attribution)

- `src/assertion_mutation_agent/verilator_executor.py` adds an OPTIONAL
  `VerilatorExecutor` behind the same `ExecutorAdapter` interface. It compiles
  the mutated RTL + an auto-generated self-contained SVA harness with
  `verilator --binary --assert` and classifies each mutant from the real run.
- The compile/run/subprocess-orchestration approach is cleanly re-implemented
  (self-contained, NO import) from the reference sim runner in the sibling
  `spec-to-cov-agent` project (`veri_forge/sim/{runner.py,verilator.py}`); the
  attribution is cited in the module docstring.
- Requires the Verilator binary. Tests that need it use a `shutil.which` guard
  (`requires_verilator`) so CI stays green without a simulator; the
  selection/graceful-degradation tests always run.

## Non-claims (no evidence, do not assert)

- The DEFAULT executor makes no claim of RTL compilation or simulation (mock).
- The optional `verilator` executor is a bounded directed simulation, NOT a
  formal proof, coverage closure, or verification signoff; a `survived` there is
  not a completeness or equivalence claim.
- No experimental-performance metrics (runtime/memory of a real solver).

Tool version: `0.1.0`. Git SHA: PLACEHOLDER (fill on tag).
