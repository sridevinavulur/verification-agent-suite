# Evidence

Each resume-safe claim is tied to source code, a test, and a reproduce command.
Distinguishes **implementation evidence** (the code does X on the examples) from
**experimental-performance evidence** (none is claimed here).

Environment: Python 3.13 in a fresh venv; `pip install -e ".[dev]"`.
Tool version: `vkg` 0.1.0. Commit/tag: `PLACEHOLDER`.

---

### C-IMPORT — Five real importers ingest the artifact shapes into a typed graph

- **Source:** `src/vkg/importers.py` (`import_rtl_intent_manifest`,
  `import_sva_intent`, `import_test_plan`, `import_coverage_summary`,
  `import_run_ledger`, `import_evidence`); `src/vkg/graph.py`.
- **Tests:** `tests/test_importers.py` (6 tests, incl. idempotency and
  provenance-hash checks).
- **Benchmark inputs:** `examples/*.json` (public toy artifacts, MIT/this repo).
- **Reproduce:** `vkg build-demo --db kg.db && vkg stats --db kg.db`
- **Expected:** 44 nodes / 65 edges across all 14 node types and 16 edge types.

### C-QUERIES — All five spec 6.12 queries return correct results

- **Source:** `src/vkg/queries.py`.
- **Tests:** `tests/test_queries.py` (7 tests with golden expected outputs).
- **Reproduce:**
  - `vkg query requirements-without-assertions --db kg.db` ⇒ `REQ-ARB-002`, `REQ-FIFO-003`
  - `vkg query coverage-holes-without-test --db kg.db` ⇒ `arb_fairness`, `fifo_reset_hit`
  - `vkg query properties-depending-on-reset por_rst --db kg.db` ⇒ `fifo_no_overflow`, `fifo_no_underflow`
  - `vkg query failures-affecting-interface fifo.rd --db kg.db` ⇒ `fifo_no_underflow_cex` (FAIL)
  - `vkg query evidence-claims-without-benchmark --db kg.db` ⇒ `C-SCALE`

### C-DOT — Graph exports valid Graphviz DOT and a JSON contract

- **Source:** `src/vkg/export.py` (`to_dot`, `to_json`); schema
  `schemas/graph_export.schema.json`.
- **Tests:** `tests/test_export.py` (4 tests: JSON round-trip, determinism,
  DOT well-formedness, hole/failure highlighting).
- **Reproduce:** `vkg export dot --db kg.db --out kg.dot`; optionally
  `dot -Tsvg kg.dot -o kg.svg` if Graphviz is installed.

### C-IDS — Node/edge IDs are stable, deterministic, and idempotent

- **Source:** `src/vkg/ids.py`.
- **Tests:** `tests/test_ids.py` (5 tests);
  `tests/test_importers.py::test_import_is_idempotent`.
- **Reproduce:** run `vkg build-demo` twice into the same DB; `vkg stats` is
  unchanged.

### C-CLI — CLI runs import/build-demo/query/export end-to-end

- **Source:** `src/vkg/cli.py`.
- **Tests:** `tests/test_cli.py` (3 tests via Typer `CliRunner`).
- **Reproduce:** the Quickstart in `README.md`.

---

## Claims explicitly NOT made (no reproducible artifact)

- **C-SCALE — "Graph scales to million-node designs."** No benchmark exists;
  this is deliberately listed with an empty `benchmarks` list in
  `examples/evidence_claims.json` and is flagged by the tool's own
  `evidence-claims-without-benchmark` query. This tool targets
  verification-artifact scale (thousands of nodes), not large-graph performance.
- No claim of RTL/SVA/coverage-database parsing (the tool consumes upstream JSON
  outputs, not source files).
- No claim of correctness/proof/signoff judgment.
