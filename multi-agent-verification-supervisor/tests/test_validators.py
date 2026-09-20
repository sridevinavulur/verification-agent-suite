from __future__ import annotations

from mav_supervisor.backends import MockRtlIngestor, MockSvaAgent
from mav_supervisor.models import ReviewState, RtlIngestRequest, SvaProposalRequest
from mav_supervisor.validators import (
    check_clock_reset,
    check_grounding,
    check_syntax,
    validate_property,
)


def _manifest():
    return MockRtlIngestor().ingest(
        RtlIngestRequest(task_id="t", repo_revision="r", rtl_files=[])
    )


def _prop(defect=None):
    return MockSvaAgent(defect=defect).propose(
        SvaProposalRequest(task_id="t", requirement_text="req", manifest_hash="h")
    )


def test_clean_property_passes_all_gates_after_review() -> None:
    m = _manifest()
    p = _prop()
    p.review_state = ReviewState.REVIEWED_OK
    assert validate_property(p, m) == []


def test_unreviewed_property_is_flagged() -> None:
    m = _manifest()
    p = _prop()  # UNREVIEWED
    findings = validate_property(p, m)
    assert any("REVIEW:" in f for f in findings)


def test_ungrounded_property_is_rejected() -> None:
    m = _manifest()
    p = _prop(defect="ungrounded")
    findings = check_grounding(p, m)
    assert any("GROUNDING:" in f for f in findings)


def test_missing_clock_is_rejected() -> None:
    m = _manifest()
    p = _prop(defect="no_clock")
    findings = check_clock_reset(p, m)
    assert any("CLOCK:" in f for f in findings)


def test_syntax_failure_is_detected() -> None:
    m = _manifest()
    p = _prop(defect="syntax")  # unbalanced paren
    findings = check_syntax(p)
    assert any("SYNTAX:" in f for f in findings)
    # And full validation also rejects it.
    p.review_state = ReviewState.REVIEWED_OK
    assert validate_property(p, m) != []


def test_ambiguous_reset_polarity_is_rejected() -> None:
    m = _manifest()
    p = _prop(defect="ambiguous_reset")
    findings = check_clock_reset(p, m)
    assert any("polarity" in f.lower() for f in findings)


def test_grounding_to_symbol_not_in_manifest_is_rejected() -> None:
    m = _manifest()
    p = _prop()
    p.groundings[0].symbol = "does_not_exist"
    findings = check_grounding(p, m)
    assert any("not present in the RTL manifest" in f for f in findings)
