# Architecture

## Overview

```
 artifacts (JSON)                importers            storage            queries / export
 ----------------                ---------            -------            ----------------
 rtl_intent_manifest.json  ─┐    import_rtl_*    ─┐                   ┌─ requirements_without_assertions
 sva_intent.json           ─┤    import_sva_*    ─┤                   ├─ coverage_holes_without_test
 test_plan.json            ─┼──▶ import_test_*   ─┼──▶  Graph  ──────▶├─ properties_depending_on_reset
 coverage_summary.json     ─┤    import_coverage ─┤   (SQLite:        ├─ failures_affecting_interface
 run_ledger.json           ─┤    import_run_*    ─┤    nodes,edges)   └─ evidence_claims_without_benchmark
 evidence_claims.json      ─┘    import_evidence ─┘                   ┌─ to_json  (GraphExport)
                                                                      └─ to_dot   (Graphviz DOT)
```

## Components

| Module | Responsibility |
| --- | --- |
| `vkg/models.py` | Typed Pydantic v2 contracts: `NodeType`, `EdgeType`, `Node`, `Edge`, `SourceProvenance`, `GraphExport`, `QueryResult`. All models forbid extra keys. |
| `vkg/ids.py` | Deterministic stable ID derivation (`node_id`, `edge_id`) and file hashing. Same natural key ⇒ same ID ⇒ idempotent imports and cross-importer references. |
| `vkg/graph.py` | `Graph`: SQLite persistence (two tables), idempotent upserts, typed reads, adjacency (`in_edges`/`out_edges`), `stats`, `to_export`. |
| `vkg/importers.py` | Five artifact importers + evidence importer. Each records provenance with the source file's sha256. |
| `vkg/queries.py` | Five deterministic gap queries returning `QueryResult`. |
| `vkg/export.py` | `to_json` (export contract) and `to_dot` (Graphviz), both deterministic. |
| `vkg/cli.py` | Typer CLI: `import`, `build-demo`, `query`, `export`, `stats`. |

## Typed input/output contracts

- **Input**: JSON artifacts (shapes in `README.md` / importer docstrings).
- **Internal**: `Node` / `Edge` rows in SQLite (`attrs` and `provenance` as
  JSON TEXT columns).
- **Output**: `GraphExport` JSON (`schemas/graph_export.schema.json`),
  Graphviz DOT, and `QueryResult` JSON (`schemas/query_result.schema.json`).

## Node and edge schema

- **Node types (14):** requirement, module, interface, signal, reset_domain,
  assertion, test, coverage_bin, regression, failure, waiver, bug,
  evidence_claim, benchmark.
- **Edge types (16):** asserts, tests, covers, coverage_of, in_module, exposes,
  on_interface, depends_on_reset, reset_of, produced, failure_of,
  affects_interface, waives, filed_as, supported_by.
- **Stable IDs:** `<prefix>:<normalized-key>:<sha1[:8]>`. The SVA importer and
  RTL importer independently compute the same module ID for `fifo`, so edges
  connect across artifacts without coordination.

## Storage design rationale

SQLite with two tables + Python adjacency was chosen per spec 6.12 ("lightweight
local storage first ... avoid a complex graph database until justified"). This
is sufficient for verification-artifact scale, keeps the dependency surface
tiny, gives durable/queryable persistence, and keeps golden tests trivial via
`:memory:` databases.

## Authority boundary

- The graph is a **record and query layer**. It has **no authority** to decide
  correctness, prove properties, waive failures, or declare signoff.
- Importers create edges **only** from links explicitly stated in artifacts.
  No heuristic or inferred edges. Missing links become visible gaps, not
  guesses.
- Result-status honesty: `TIMEOUT`/`ERROR`/`UNKNOWN` are preserved verbatim and
  never counted as passes (per `BUILD_STANDARD.md`).
- No LLM is invoked; there is no non-deterministic component.

## Determinism / reproducibility

- IDs are content-derived; row order in exports and query results is sorted.
- Every node/edge carries the source file's sha256 (`SourceProvenance.input_hash`).
- Re-importing the same artifact is a no-op on graph contents.
