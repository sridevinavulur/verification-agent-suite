# Mock coverage format (`mock-cov-1.0`)

A teaching-oriented normalized coverage export. A real adapter (e.g. for a vendor
UCDB/UCIS) would normalize into the same Pydantic `CoverageDB` contract, so the
downstream triage engine is format-agnostic.

## Top-level bundle

The CLI ingests one JSON object validated as `TriageInputs`:

```json
{
  "coverage":     { "...": "CoverageDB" },
  "tests":        { "...": "TestManifest" },
  "rtl":          { "...": "RTLIntentManifest" },
  "requirements": { "...": "RequirementMatrix" },
  "logs":         { "...": "LogBundle" }
}
```

## CoverageDB

```json
{
  "format_version": "mock-cov-1.0",
  "tool": "mock",
  "items": [ { "...": "CoverageItem" } ]
}
```

### CoverageItem

| Field | Type | Notes |
| --- | --- | --- |
| `coverage_id` | string | Stable unique id. |
| `kind` | enum | statement/branch/toggle/fsm_state/fsm_transition/covergroup_bin/assertion |
| `hits` | int >= 0 | Observed hit count. `hits < goal` ⇒ hole. |
| `goal` | int >= 1 | Required hits (default 1). |
| `module` | string | Owning RTL module. |
| `source_file` | string? | Toy source path. |
| `source_line` | int? | Source line. |
| `description` | string | Human-readable point name. |
| `exclusion_pragma` | bool | True ⇒ treated as likely-unreachable. |

## TestManifest / TestEntry

`status` uses the result vocabulary: `pass`, `fail`, `timeout`, `error`,
`unknown`, `not_run`. `covers` lists the coverage ids the test is *intended* to
hit (from the testplan). `seed`/`config` feed runnable `run_existing_test`
recommendations.

## RTLIntentManifest / RTLModule

`dead_code_hints` is a list of source lines flagged upstream as likely
unreachable. A hole whose `source_line` is in that set is classified
`likely_unreachable` (structural hint, not a proof).

## RequirementMatrix / RequirementLink

Maps `requirement_id` → `tests` and → `covers`. A hole with no requirement
mapping is flagged and may be classified `no_requirement_mapping`.

## LogBundle / LogEntry

Failure/compile records keyed by `test_id`. For a `test_ran_but_failed` hole, the
matching log lines are attached as `failure_log` evidence.

See `schemas/triage_inputs.schema.json` for the machine-readable schema.
