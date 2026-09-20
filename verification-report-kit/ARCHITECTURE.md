# Architecture

`verification-report-kit` is a thin, layered presentation library. There is no
network, no LLM, no execution engine — it transforms a typed data contract into
HTML/JSON.

```
   caller tool (any verification agent)
             │  builds
             ▼
   ┌─────────────────────┐
   │  ReportModel         │   models.py  — Pydantic v2 contract (validates)
   │  (title, provenance, │
   │   stats, sections,   │
   │   tables, findings,  │
   │   coverage_history)  │
   └─────────┬───────────┘
             │
      ┌──────┴───────┐
      ▼              ▼
 render_html     write_json / to_json / load_json
 html_renderer.py    json_writer.py
      │              │
      ▼              ▼
 self-contained    deterministic
 HTML string       JSON file
```

## Components

| Module              | Responsibility                                              |
|---------------------|------------------------------------------------------------|
| `models.py`         | The stable public contract. Pydantic v2 models with `extra="forbid"` so typos fail loudly. Defines `Status` (result vocabulary) and `SEVERITY_ORDER`. |
| `html_renderer.py`  | Pure function `render_html(ReportModel) -> str`. Inline-CSS only, all text escaped, deterministic. |
| `json_writer.py`    | `to_json` / `write_json` / `load_json`. Deterministic serialization + validated load. |
| `examples_data.py`  | Two canonical example reports; shared by CLI demos, `examples/`, and golden tests (single source of truth → determinism). |
| `cli.py`            | Typer CLI: `render`, `validate`, `schema`, `demo`, `version`. |
| `__init__.py`       | Public API surface (`__all__`).                            |

## Typed input/output contracts

**Input**: `ReportModel` (see README table and `schemas/report.schema.json`).
All fields optional except `title`. Nested models: `Provenance`, `Stat`,
`Section`, `Table`, `Finding`, `CoveragePoint`.

**Output**:
- `render_html` → `str`: a complete `<!DOCTYPE html>` document, inline `<style>`,
  no external references.
- `write_json` → `Path`: a JSON file, field-declaration key order, trailing
  newline.

## Authority boundaries

This library has **no authority** over verification conclusions.

- It never computes, judges, or reclassifies a result. A caller's `Status` is
  rendered verbatim (a TIMEOUT is shown as TIMEOUT).
- It does not read RTL, run tools, or touch proof scope/budgets/signoff.
- It performs exactly two deterministic transformations (model → HTML,
  model → JSON) and one validation (JSON → model).

The separation demanded by `BUILD_STANDARD.md` (LLM proposes, deterministic
tools validate) is respected trivially: this is entirely in the deterministic
layer and contains no LLM code.

## Determinism strategy

- No `datetime.now()`, no RNG, no environment reads in the render/serialize path.
- Timestamps are caller-supplied strings on `Provenance.timestamp`.
- JSON uses `sort_keys=False` (stable field order) + fixed indent + trailing `\n`.
- Coverage-history metric columns are derived in first-seen order (stable).

## Extensibility

Add new report content by adding **optional** fields to `models.py` (never
rename/remove — the schema is a compatibility surface) and a corresponding
fragment renderer in `html_renderer.py`. `Section` already allows arbitrary
prose/bullets/tables/stats without any schema change.
