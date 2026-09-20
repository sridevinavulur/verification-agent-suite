"""Golden / behavior tests for rendering (deterministic, self-contained)."""
from __future__ import annotations

from verification_report_kit import ReportModel, render_html, to_json
from verification_report_kit.examples_data import coverage_report, findings_report


def test_html_is_self_contained() -> None:
    html = render_html(coverage_report())
    # No external assets / CDN / remote resources.
    for banned in ("http://", "https://", "<script", "<link", "src=", "@import", "url("):
        assert banned not in html, f"self-contained violation: {banned!r} present"
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html


def test_html_deterministic() -> None:
    a = render_html(coverage_report())
    b = render_html(coverage_report())
    assert a == b  # identical input -> byte-identical output


def test_json_deterministic() -> None:
    a = to_json(findings_report())
    b = to_json(findings_report())
    assert a == b
    assert a.endswith("\n")


def test_coverage_report_key_content() -> None:
    html = render_html(coverage_report())
    assert "Coverage Closure Report" in html
    assert "Coverage History" in html
    assert "Toggle Unreachability Analysis" in html
    assert "92.4" in html  # a coverage bar value
    assert "COV-001" in html  # finding id
    assert "coverage-closure-agent" in html  # provenance


def test_findings_report_key_content() -> None:
    html = render_html(findings_report())
    assert "Counterexample Triage Report" in html
    assert "CRITICAL" in html.upper()
    assert "CEX-1" in html
    assert "HEURISTIC" in html  # heuristic finding flagged
    assert "Property Outcomes" in html


def test_html_escaping() -> None:
    r = ReportModel(title="A & <b> \"quote\"")
    html = render_html(r)
    assert "A &amp; &lt;b&gt;" in html
    assert "<b>" not in html.split("<style>")[0]  # no injected raw tag in header


def test_empty_report_renders() -> None:
    html = render_html(ReportModel(title="Empty"))
    assert "<!DOCTYPE html>" in html
    assert "No findings recorded." not in html  # findings section only when present
