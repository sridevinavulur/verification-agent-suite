# verification-knowledge-graph (`vkg`)

A lightweight, **SQLite-backed knowledge graph** over public verification
artifacts. It ingests the outputs of sibling verification tools (RTL intent
manifest, SVA intent output, test plan, coverage summary, run ledger) plus
`EVIDENCE.md`-style claims, links them with a typed node/edge schema, and
answers traceability-gap queries such as *"which requirements lack
assertions?"*.

This is spec section **6.12** of the verification agent prompt pack, built to
the shared `BUILD_STANDARD.md`.

## Scope (what this actually does)

- **Typed graph schema** (`src/vkg/models.py`): 14 node types and 16 edge
  types, every node with a **stable ID** and **source provenance** (artifact
  name, source file, locator, sha256 input hash).
- **Lightweight local storage** (`src/vkg/graph.py`): two plain SQLite tables
  (`nodes`, `edges`) with JSON attr/provenance columns. **No graph-DB
  dependency.** Traversal is Python over indexed adjacency. Upserts by stable
  ID make imports idempotent.
- **Five real importers** (`src/vkg/importers.py`) for the artifact shapes
  documented below (plus an EVIDENCE importer).
- **Five working queries** (`src/vkg/queries.py`), each a deterministic
  traversal returning structured, sorted results.
- **Exporters** (`src/vkg/export.py`): full-graph **JSON** and **Graphviz DOT**
  (deterministic ordering; coverage holes and failures highlighted in red).
- **Typer CLI** (`src/vkg/cli.py`): `import`, `build-demo`, `query`, `export`,
  `stats`.

## Install

```bash
python3.11 -m venv .venv && . .venv/bin/activate    # 3.11+ required (uses StrEnum)
pip install -e ".[dev]"
```

## Quickstart

```bash
# Build the whole demo graph from bundled examples/ into kg.db
vkg build-demo --db kg.db

# Run each working query
vkg query requirements-without-assertions        --db kg.db
vkg query coverage-holes-without-test            --db kg.db
vkg query properties-depending-on-reset por_rst  --db kg.db
vkg query failures-affecting-interface fifo.rd   --db kg.db
vkg query evidence-claims-without-benchmark      --db kg.db

# Export
vkg export json --db kg.db --out kg.json
vkg export dot  --db kg.db --out kg.dot
# dot -Tsvg kg.dot -o kg.svg   # if Graphviz is installed
```

Import a single artifact:

```bash
vkg import rtl      examples/rtl_intent_manifest.json --db kg.db
vkg import sva      examples/sva_intent.json          --db kg.db
vkg import testplan examples/test_plan.json           --db kg.db
vkg import coverage examples/coverage_summary.json    --db kg.db
vkg import runledger examples/run_ledger.json         --db kg.db
vkg import evidence examples/evidence_claims.json     --db kg.db
```

## The five queries (spec 6.12)

| Query | Meaning | Demo result |
| --- | --- | --- |
| `requirements-without-assertions` | Requirements with no `ASSERTS` edge from any assertion | `REQ-ARB-002`, `REQ-FIFO-003` |
| `coverage-holes-without-test` | Bins with `hits < goal` and no `COVERS` edge from any test | `arb_fairness`, `fifo_reset_hit` |
| `properties-depending-on-reset <name>` | Assertions with `DEPENDS_ON_RESET` to the named domain | `por_rst` -> `fifo_no_overflow`, `fifo_no_underflow` |
| `failures-affecting-interface <name>` | Failures with `AFFECTS_INTERFACE` to the matching interface | `fifo.rd` -> `fifo_no_underflow_cex` |
| `evidence-claims-without-benchmark` | Claims with no `SUPPORTED_BY` edge to a benchmark | `C-SCALE` |

## Compatible JSON artifact shapes

Shapes are simple, `schema_version`-tagged, snake_case, and align with the
sibling tools where reasonable. Importers consume only the fields the graph
needs and ignore extra fields, so they tolerate richer sibling outputs. See
`examples/` for a complete, coherent set and the docstrings in
`src/vkg/importers.py` for each field. Summary:

- **RTL intent manifest** — `modules[]` with `interfaces`, `signals`,
  `reset_domains`, and `signal_reset_domain`.
- **SVA intent** — `properties[]` with `module`, `requirement_ids`,
  `reset_domains`, `interfaces`.
- **Test plan** — `requirements[]` and `tests[]` (with `requirement_ids`,
  `coverage_bins`).
- **Coverage summary** — `bins[]` with `hits`/`goal` (`hits<goal` => hole),
  `module`, `interface`.
- **Run ledger** — `runs[]` with `failures[]` (`status`, `target_assertion`,
  `target_test`, `interfaces`, `waiver`, `bug`).
- **Evidence** — `claims[]` with `benchmarks[]`.

## Limitations and explicit non-claims

- This tool **records and queries relationships**. It does **not** decide
  correctness, prove properties, or make signoff judgments.
- Following `BUILD_STANDARD.md`: a failure `status` of `TIMEOUT`, `ERROR`, or
  `UNKNOWN` is stored **as-is** and is **never** treated as a pass. Only
  `FAIL`-status entries are treated as failures for triage.
- It does **not** parse RTL, SVA, or coverage databases directly — it consumes
  the **JSON outputs** of tools that do. Grounding correctness is only as good
  as those inputs.
- The graph does **not** infer edges heuristically. If an artifact does not
  state a link (e.g. a property lists no `requirement_ids`), no edge is created
  — which is exactly what the gap queries surface.
- **Not** a scalable/distributed graph database. SQLite + in-Python traversal
  targets verification-artifact scale (thousands of nodes), not "million-node"
  designs (see the honest `C-SCALE` claim in `examples/evidence_claims.json`,
  which the tool itself flags as unsupported).
- No LLM is used anywhere. Everything is deterministic.

## Data policy

Public, non-proprietary toy artifacts only (`examples/`). No employer/customer
names, credentials, internal tool names, or proprietary paths.

## Tests

```bash
ruff check .
pytest
```

See `EVIDENCE.md` for each claim tied to a source function, test, and reproduce
command.
