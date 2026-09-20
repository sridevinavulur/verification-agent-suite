# Evidence

Each claim is tied to source code, a test, and a reproduce command. Claims are
scoped to the v0.1 constrained-Verilog subset. Release tag / commit: `PLACEHOLDER`.

Setup for all reproduce commands:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

### C1 — Parses the constrained Verilog subset into a typed manifest

- **Claim:** the built-in parser extracts modules, ports (with width and
  direction), parameters, nets, continuous assigns, procedures, and instances
  from the supported subset.
- **Code:** `src/rtl_intent/adapters/builtin.py`, `src/rtl_intent/models.py`
- **Tests:** `tests/test_parser.py` (`test_module_and_ansi_ports`,
  `test_non_ansi_ports`, `test_parameters_and_localparams`,
  `test_instances_named_and_positional`, `test_memory_array_net`)
- **Reproduce:** `pytest tests/test_parser.py -q`

### C2 — Correct manifests on public examples (golden outputs)

- **Claim:** the tool produces byte-stable, correct JSON manifests for the
  bundled counter, FIFO-like queue, and valid/ready producer/consumer.
- **Code:** `src/rtl_intent/manifest.py`, `src/rtl_intent/serialize.py`
- **Tests:** `tests/test_golden.py` vs `tests/golden/*.json`
- **Reproduce:** `pytest tests/test_golden.py -q`
- **Artifacts:** `tests/golden/{counter,fifo_queue,valid_ready}.json`,
  human-readable copies in `examples/expected/`

### C3 — Deterministic hierarchy graph with external-module flagging

- **Claim:** parent→child instantiation edges are extracted; children not
  defined in the inputs are flagged as external/black-box; top is inferred when
  unambiguous.
- **Code:** `manifest.py` (`build_manifest_from_texts`, `_infer_top`)
- **Tests:** `tests/test_parser.py::test_hierarchy_and_external_module`
- **Reproduce:** `pytest tests/test_parser.py::test_hierarchy_and_external_module -q`

### C4 — Heuristic clock/reset candidates with confidence + rationale

- **Claim:** clock and reset candidates are detected from names and `always_ff`
  structure, each with a bounded confidence and an explicit rationale; reset
  polarity/sync are inferred heuristically. Labelled heuristic, not formal.
- **Code:** `src/rtl_intent/heuristics.py`
- **Tests:** `tests/test_heuristics.py` (async active-low, sync active-high,
  bounds, absence)
- **Reproduce:** `pytest tests/test_heuristics.py -q`

### C5 — Source locations for every extracted item

- **Claim:** every module, port, net, parameter, assignment, procedure, and
  instance carries a `file:line:col` location.
- **Code:** `lexer.py` (token positions), `builtin.py` (`_loc`)
- **Tests:** `tests/test_parser.py::test_source_locations_present`
- **Reproduce:** `pytest tests/test_parser.py::test_source_locations_present -q`

### C6 — Unsupported constructs are always visible

- **Claim:** constructs outside the subset are recorded in `Manifest.unresolved`
  rather than dropped.
- **Code:** `builtin.py` (`_record_unsupported_block`, `_record_unknown_stmt`)
- **Tests:** `tests/test_parser.py::test_unsupported_construct_is_visible`
- **Reproduce:** `pytest tests/test_parser.py::test_unsupported_construct_is_visible -q`

### C7 — Strict, validating typed contracts (Pydantic v2)

- **Claim:** the manifest is a strict contract: unknown keys rejected,
  confidence bounded to `[0,1]`, positive line/col enforced; JSON round-trips.
- **Code:** `models.py` (`_Strict` with `extra="forbid"`, `Field` constraints)
- **Tests:** `tests/test_models.py`, `tests/test_golden.py::test_golden_roundtrips_through_model`
- **Reproduce:** `pytest tests/test_models.py -q`

### C8 — Working CLI end-to-end

- **Claim:** `rtl-intent` ingests files to JSON/Markdown, prints a summary,
  lists adapters, and exports the JSON Schema.
- **Code:** `src/rtl_intent/cli.py`
- **Tests:** `tests/test_cli.py`
- **Reproduce:** `pytest tests/test_cli.py -q` and
  `rtl-intent ingest examples/counter.sv`

---

## Benchmark inputs and licenses

The bundled `examples/*.sv` are original, generic toy RTL written for this
repository (counter, FIFO-like queue, valid/ready producer/consumer). They
contain no proprietary content and are released under the repository's MIT
license.

## Explicitly NOT claimed

Full SystemVerilog parsing; semantic correctness of extracted logic; formal
determination of clock/reset roles; that a listed "register" is a proven state
element; any LLM-based interpretation (none exists in v0.1).
