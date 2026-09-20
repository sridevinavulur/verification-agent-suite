# Evidence

Every claim about this tool is tied to a source location, a test, and a command
you can run. Reproduce environment first:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Claims → evidence

| # | Claim | Source | Test | Reproduce |
|---|-------|--------|------|-----------|
| 1 | Stable typed contract; unknown fields rejected | `src/verification_report_kit/models.py` (`ReportModel`, `extra="forbid"`) | `tests/test_models.py::test_extra_fields_forbidden`, `::test_minimal_report_valid` | `pytest tests/test_models.py` |
| 2 | `render_html` output is self-contained (no external assets) | `html_renderer.py::render_html` (`_STYLE` inline, no `<script>/<link>`) | `tests/test_render.py::test_html_is_self_contained` | `pytest -k self_contained` |
| 3 | Rendering is deterministic (byte-identical for same input) | `html_renderer.py` (no `now()`/RNG); `json_writer.py::to_json` (`sort_keys=False`, trailing `\n`) | `test_render.py::test_html_deterministic`, `::test_json_deterministic` | `pytest -k deterministic` |
| 4 | All caller text is HTML-escaped (no injection) | `html_renderer.py::_esc` (`html.escape(..., quote=True)`) | `test_render.py::test_html_escaping` | `pytest -k escaping` |
| 5 | Coverage-style report renders (metrics, history, unreachability, finding, provenance) | `examples_data.py::coverage_report` | `test_render.py::test_coverage_report_key_content` | `pytest -k coverage_report_key` |
| 6 | Findings-style report renders (severity pills, heuristic badge, result vocabulary) | `examples_data.py::findings_report` | `test_render.py::test_findings_report_key_content` | `pytest -k findings_report_key` |
| 7 | JSON round-trips through `write_json`/`load_json` losslessly | `json_writer.py` | `tests/test_roundtrip.py::test_json_roundtrip` | `pytest -k json_roundtrip` |
| 8 | CLI `render`/`validate`/`demo` work end-to-end | `cli.py` | `tests/test_roundtrip.py::test_cli_render`, `::test_cli_validate`, `::test_cli_demo` | `pytest tests/test_roundtrip.py` |
| 9 | Findings sort by severity (critical→info) | `models.py::ReportModel.sorted_findings` | `test_models.py::test_sorted_findings_by_severity` | `pytest -k sorted_findings` |
| 10 | JSON Schema exportable for the contract | `models.py` / `cli.py::schema` | `test_models.py::test_json_schema_exportable` | `vrk schema --out /tmp/s.json` |
| 11 | Result vocabulary matches BUILD_STANDARD.md | `models.py::Status` (PASS/FAIL/TIMEOUT/ERROR/UNKNOWN/INCONCLUSIVE/COMPILED) | covered by #6 | — |

## Full verification run

```bash
ruff check .                 # -> All checks passed!
pytest                       # -> 16 passed
python examples/generate_examples.py   # writes examples/*.{json,html}
vrk render --in examples/coverage_report.json --out /tmp/cov.html
vrk render --in examples/findings_report.json --out /tmp/find.html
open examples/coverage_report.html      # opens in a browser, no assets needed
```

## Reference attribution

The self-contained HTML approach (inline CSS, stat tiles, status badges,
coverage bars) and the JSON writer are adapted from the read-only reference:
- `spec-to-cov-agent/veri_forge/dashboard.py`
- `spec-to-cov-agent/veri_forge/utils/report.py`

Re-implemented against the generic `ReportModel` contract (no code copied
verbatim, no dependency on that package). Citations are in the module docstrings
of `html_renderer.py` and `json_writer.py`.
