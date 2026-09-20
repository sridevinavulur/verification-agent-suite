"""Tests for scoring, the mock LLM layer, models, and the CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from assertion_review.cli import app
from assertion_review.llm import MockLLMAdapter, annotate_report
from assertion_review.models import RtlIntentManifest, Severity
from assertion_review.review import review_text

REPO = Path(__file__).resolve().parent.parent
runner = CliRunner()

_BAD = REPO / "examples" / "bad" / "handshake_bad.sv"
_MAN = REPO / "examples" / "manifests" / "handshake.manifest.json"
_GOOD = REPO / "examples" / "good" / "fifo_good.sv"
_FIFO_MAN = REPO / "examples" / "manifests" / "fifo.manifest.json"


def test_score_monotonic_good_beats_bad():
    good = review_text((_GOOD).read_text()).score()
    man = RtlIntentManifest.model_validate_json(_MAN.read_text())
    bad = review_text(_BAD.read_text(), manifest=man).score()
    assert good.score > bad.score


def test_score_bounds():
    man = RtlIntentManifest.model_validate_json(_MAN.read_text())
    s = review_text(_BAD.read_text(), manifest=man).score()
    assert 0.0 <= s.score <= 100.0


def test_mock_llm_only_annotates_never_changes_findings():
    man = RtlIntentManifest.model_validate_json(_MAN.read_text())
    report = review_text(_BAD.read_text(), manifest=man)
    annotated = annotate_report(report, MockLLMAdapter())
    # Same number, same check_ids, same severities -- only explanations added.
    assert len(annotated.findings) == len(report.findings)
    for a, b in zip(annotated.findings, report.findings, strict=True):
        assert a.check_id == b.check_id
        assert a.severity == b.severity
        assert a.location == b.location
        assert a.explanation is not None
        assert b.explanation is None


def test_checklist_marks_attention_items():
    man = RtlIntentManifest.model_validate_json(_MAN.read_text())
    report = review_text(_BAD.read_text(), manifest=man)
    assert any(item.startswith("[!]") for item in report.checklist)


def test_manifest_rejects_unknown_field():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RtlIntentManifest.model_validate({"top": "m", "bogus": 1})


def test_cli_review_text_output_and_exit_code():
    result = runner.invoke(
        app, ["review", str(_BAD), "-m", str(_MAN), "--fail-on", "error"]
    )
    assert result.exit_code == 1  # bad file has errors
    assert "Assertion Review" in result.stdout
    assert "review score" in result.stdout


def test_cli_review_good_exit_zero():
    result = runner.invoke(
        app, ["review", str(_GOOD), "-m", str(_FIFO_MAN), "--fail-on", "error"]
    )
    assert result.exit_code == 0


def test_cli_json_format():
    result = runner.invoke(app, ["review", str(_GOOD), "-m", str(_FIFO_MAN), "-f", "json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert data["source_file"].endswith("fifo_good.sv")
    assert "findings" in data


def test_cli_explain_flag():
    result = runner.invoke(
        app, ["review", str(_BAD), "-m", str(_MAN), "--explain", "--fail-on", "none"]
    )
    assert result.exit_code == 0
    assert "(why)" in result.stdout


def test_severity_enum_values():
    assert {s.value for s in Severity} == {"ERROR", "WARNING", "INFO"}
