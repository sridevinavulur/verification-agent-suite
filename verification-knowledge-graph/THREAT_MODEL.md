# Threat Model

Scope: `verification-knowledge-graph` is a deterministic ingest/query/export
tool over JSON verification artifacts. It uses **no LLM** and makes **no
network calls**. The threats below are framed against the `BUILD_STANDARD.md`
integrity rules.

## 1. Hallucination / fabricated relationships

- **Risk:** presenting links that were never stated in an artifact.
- **Mitigation:** importers create edges **only** from fields explicitly present
  in the source JSON. There is no inference, no fuzzy matching that invents a
  link, and no LLM. A property with no `requirement_ids` produces no `ASSERTS`
  edge — the gap is reported, not filled. Covered by
  `tests/test_queries.py::test_requirements_without_assertions`.

## 2. Unsafe assumptions about verification results

- **Risk:** treating a `TIMEOUT`/`ERROR`/`UNKNOWN` run as a pass, or a failure
  as a proven design bug.
- **Mitigation:** the run-ledger importer stores the raw `status` on the failure
  node and never reinterprets it. `failures-affecting-interface` reports the
  status verbatim (e.g. `TIMEOUT`). The tool never emits a PASS/proven verdict.
  Covered by `test_importers.py::test_run_ledger_records_status_not_pass` and
  `test_queries.py::test_failures_affecting_interface`.

## 3. Silent authority overreach

- **Risk:** a tool "closing" gaps, waiving failures, or changing scope.
- **Mitigation:** the graph is read/record only. It has no write path back to
  RTL, assertions, coverage, or signoff artifacts. Waivers are represented as
  data (`waiver` nodes) that a human authored in the ledger; the tool does not
  create them on its own.

## 4. Data leakage

- **Risk:** committing proprietary RTL, customer names, internal tool names,
  credentials, or private paths.
- **Mitigation:** only public toy artifacts in `examples/`. Provenance stores
  the **path and hash** of inputs, not their contents beyond the node names an
  operator chose to import. Operators running on private artifacts control what
  paths/names enter the DB; the DB file itself is `.gitignore`d.

## 5. Reproducibility risks

- **Risk:** non-deterministic output, un-auditable imports.
- **Mitigation:** content-derived stable IDs, sorted export/query ordering,
  sha256 input hashes in provenance, idempotent upserts. Same inputs ⇒ byte-
  identical JSON export (`test_export.py::test_json_export_is_deterministic`).

## 6. Input integrity

- **Risk:** malformed artifacts corrupting the graph.
- **Mitigation:** strict JSON object validation on load; Pydantic models
  (`extra="forbid"`) validate every node/edge before it is stored. A malformed
  top-level shape raises rather than silently importing partial data.

## Residual limitations (documented, not mitigated in scope)

- Correctness of links depends entirely on the correctness of the upstream
  tools that produced the JSON artifacts. This tool cannot detect a wrong link
  that an artifact asserts confidently.
- The tool does not verify that referenced modules/interfaces/reset domains
  actually exist in RTL; it graphs what the artifacts claim. Dangling edge
  targets are permitted (and are themselves surfacable by inspecting the graph).
