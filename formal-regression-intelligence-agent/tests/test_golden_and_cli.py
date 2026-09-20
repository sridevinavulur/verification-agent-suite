"""Golden-output test + CLI end-to-end + interop + LLM adapter tests."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from formal_regression_intelligence.analysis import Thresholds, analyze
from formal_regression_intelligence.cli import app
from formal_regression_intelligence.explain import MockLLM, explain_findings
from formal_regression_intelligence.ledger import load_ledger
from formal_regression_intelligence.models import FindingKind, RegressionReport

runner = CliRunner()


def test_golden_report_matches(sample_ledger_path, golden_report_path):
    """The analysis on the bundled ledger must reproduce the checked-in golden."""
    ledger = load_ledger(sample_ledger_path)
    report = analyze(ledger.records, Thresholds())
    produced = json.loads(report.model_dump_json())
    golden = json.loads(golden_report_path.read_text())
    assert produced == golden


def test_golden_covers_every_finding_kind(golden_report_path):
    golden = RegressionReport.model_validate_json(golden_report_path.read_text())
    kinds = {f["kind"] for f in json.loads(golden_report_path.read_text())["findings"]}
    for kind in FindingKind:
        assert kind.value in kinds, f"golden ledger should exercise {kind.value}"
    assert golden.n_records == 20


def test_load_json_array(tmp_path, sample_ledger_path):
    # Convert the bundled JSONL to a JSON array and confirm both parse identically.
    records = [json.loads(line) for line in sample_ledger_path.read_text().splitlines() if line]
    arr_path = tmp_path / "ledger.json"
    arr_path.write_text(json.dumps(records))
    from_array = load_ledger(arr_path)
    from_lines = load_ledger(sample_ledger_path)
    assert len(from_array.records) == len(from_lines.records) == 20


def test_bad_record_is_reported_not_dropped(tmp_path):
    bad = tmp_path / "bad.jsonl"
    # A PASS with return_code != 0 must be rejected loudly.
    bad.write_text(json.dumps({
        "run_id": "x", "benchmark_id": "b", "design_sha": "d", "property_sha": "p",
        "input_hash": "h", "tool_name": "t", "tool_version": "v", "config_id": "c",
        "catalog_version": "cat", "seed": 1, "cpu_time_s": 1.0, "wall_time_s": 1.0,
        "peak_memory_mb": 1.0, "return_code": 5, "status": "PASS",
    }) + "\n")
    try:
        load_ledger(bad)
        raise AssertionError("expected a validation error")
    except ValueError as e:
        assert "failed validation" in str(e)


def test_cli_analyze_json(sample_ledger_path):
    result = runner.invoke(app, ["analyze", str(sample_ledger_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["n_records"] == 20
    assert len(payload["findings"]) == 11


def test_cli_queue(sample_ledger_path):
    result = runner.invoke(app, ["queue", str(sample_ledger_path)])
    assert result.exit_code == 0
    assert "runtime_regression" in result.output
    assert "#1" in result.output


def test_cli_report_markdown_and_explain(sample_ledger_path):
    result = runner.invoke(app, ["report", str(sample_ledger_path), "--explain"])
    assert result.exit_code == 0
    assert "# Formal Regression Intelligence Report" in result.output
    assert "HEURISTIC" in result.output
    assert "mock-llm" in result.output


def test_cli_schema_export():
    result = runner.invoke(app, ["schema", "run-record"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["title"] == "RunRecord"


def test_mock_llm_is_deterministic_and_grounded(sample_ledger_path):
    ledger = load_ledger(sample_ledger_path)
    report = analyze(ledger.records, Thresholds())
    once = explain_findings(report.findings, MockLLM())
    twice = explain_findings(report.findings, MockLLM())
    assert once == twice  # deterministic
    for f in report.findings:
        text = once[f.finding_id]
        # Explanation only cites run IDs that are actually in the finding.
        for rid in f.member_run_ids[:5]:
            assert rid in text
        assert "HEURISTIC" in text
        assert "correlation is not causation" in text
