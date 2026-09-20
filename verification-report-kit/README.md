# verification-report-kit (`vrk`)

A small, **reusable, dependency-free reporting library** for the verification
agent repos. Any bounded tool (coverage-closure, formal-run-orchestrator,
mutation, triage, supervisor, the section-6 agents, ...) can build a single
typed report object and get:

- `render_html(report) -> str` — one **self-contained HTML file** (inline CSS
  only; no external stylesheets, CDN scripts, remote fonts, or images), and
- `write_json(report, path)` — a deterministic structured JSON report.

It is deliberately **generic and uncoupled**: it depends on nothing from
`spec-to-cov-agent` (or any other repo). The only compatibility surface is the
Pydantic v2 `ReportModel` contract.

> The inline-CSS dashboard style and the JSON writer are adapted from the
> read-only reference `spec-to-cov-agent/veri_forge/dashboard.py` and
> `.../veri_forge/utils/report.py`, re-implemented here against a generic
> contract. See the citations in `html_renderer.py` / `json_writer.py`.

## Install

```bash
python3.13 -m venv .venv && source .venv/bin/activate   # python 3.11+
pip install -e ".[dev]"
```

## Quickstart — Python API

```python
from verification_report_kit import ReportModel, Stat, Finding, Status, render_html, write_json

report = ReportModel(
    title="My Tool — dut_top",
    stats=[Stat(label="Line", value=92.4, unit="%", status=Status.PASS)],
    findings=[Finding(id="F1", title="Branch gap", severity="medium", status=Status.FAIL)],
)

open("report.html", "w").write(render_html(report))   # self-contained HTML
write_json(report, "report.json")                     # structured JSON
```

## Quickstart — CLI

```bash
vrk demo --kind coverage --out demo.html          # built-in coverage demo
vrk demo --kind findings --out demo.html          # built-in findings demo
vrk render --in report.json --out report.html     # render your JSON to HTML
vrk validate --in report.json                     # validate against the contract
vrk schema  --out report.schema.json              # export the JSON Schema
```

## The contract (`ReportModel`)

| Field              | Purpose                                                        |
|--------------------|---------------------------------------------------------------|
| `title` (required) | Report heading                                                |
| `subtitle`         | Sub-heading line                                              |
| `provenance`       | Run ledger: tool, version, git SHA, command, seed, input hashes, runtime, memory, status, timestamp |
| `stats`            | Headline key/value tiles (with optional status accent)        |
| `sections`         | Free-form content blocks: prose, bullets, stats, tables       |
| `tables`           | Top-level tables (columns + rows)                             |
| `findings`         | Severity-classified issues (critical→info), heuristic flag    |
| `coverage_history` | Coverage-over-time points (metric name → percent)             |

Everything except `title` is optional; renderers tolerate empty collections.
See `schemas/report.schema.json` for the exported JSON Schema.

## Examples

`examples/generate_examples.py` produces two full reports (checked in):

- `examples/coverage_report.{json,html}` — coverage-closure style (metrics,
  coverage history bars, unreachability table, one finding).
- `examples/findings_report.{json,html}` — triage style (severity-classified
  findings, heuristic flag, property-outcomes table using the result vocabulary).

Open either `.html` directly in a browser — no assets needed.

## Design guarantees

- **Self-contained HTML**: enforced by a test that greps the output for
  `http`, `<script`, `<link`, `src=`, `@import`, `url(`.
- **Deterministic**: no `datetime.now()` in the renderer; any timestamp comes
  from `provenance.timestamp` supplied by the caller. Identical input → identical
  output (JSON has stable key order + trailing newline). Golden-tested.
- **Safe escaping**: all caller-supplied text is HTML-escaped, so report content
  cannot inject markup/script.
- **Result vocabulary** matches `BUILD_STANDARD.md`: PASS / FAIL / TIMEOUT /
  ERROR / UNKNOWN / INCONCLUSIVE / COMPILED ("property compiled" = syntax only).
  Heuristic findings carry a `heuristic` flag and render a HEURISTIC badge.

## Runtime dependencies

`pydantic>=2.5` and `typer>=0.9`. Nothing else at runtime — no charting
library, no template engine, no web framework.

## Limitations / non-claims

- This is a **presentation** library. It does **not** verify anything, judge
  correctness, or interpret results. It renders whatever a tool feeds it.
- It does **not** upgrade or reclassify results; if a caller passes a TIMEOUT it
  is shown as TIMEOUT, never as PASS.
- No charts beyond simple inline coverage bars (no JS, by design).
- No theming/plugin system yet (single built-in visual style).

## Roadmap (later phases, not built)

- Optional dark theme variant.
- Markdown-in-section rendering (currently plain, escaped text).
- Multi-report index / diff view.

MIT licensed. Public toy data only in `examples/`.
