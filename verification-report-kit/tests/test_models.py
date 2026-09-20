"""Contract / validation tests for the ReportModel."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from verification_report_kit import Finding, ReportModel, Status
from verification_report_kit.models import SCHEMA_VERSION


def test_minimal_report_valid() -> None:
    r = ReportModel(title="Hello")
    assert r.title == "Hello"
    assert r.schema_version == SCHEMA_VERSION
    assert r.findings == []


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ReportModel(title="x", bogus_field=1)  # type: ignore[call-arg]


def test_status_enum_roundtrip() -> None:
    r = ReportModel(
        title="x",
        findings=[Finding(id="F1", title="t", severity="high", status=Status.FAIL)],
    )
    dumped = r.model_dump(mode="json")
    assert dumped["findings"][0]["status"] == "FAIL"


def test_sorted_findings_by_severity() -> None:
    r = ReportModel(
        title="x",
        findings=[
            Finding(id="a", title="a", severity="low"),
            Finding(id="b", title="b", severity="critical"),
            Finding(id="c", title="c", severity="medium"),
        ],
    )
    order = [f.severity for f in r.sorted_findings()]
    assert order == ["critical", "medium", "low"]


def test_json_schema_exportable() -> None:
    schema = ReportModel.model_json_schema()
    assert schema["title"] == "ReportModel"
    assert "findings" in schema["properties"]
