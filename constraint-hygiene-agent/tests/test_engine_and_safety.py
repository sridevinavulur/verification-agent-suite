"""End-to-end engine tests + safety-rule enforcement.

These tests encode the non-negotiable rules from the spec / BUILD_STANDARD:
never claim soundness from absence of contradictions; always route to human
review; always label findings as static suspicion.
"""

from constraint_hygiene.engine import analyze_files
from constraint_hygiene.models import Confidence, FindingCode, Severity


def test_bad_corpus_flags_all_anti_patterns(bad_sva, manifest_path):
    report = analyze_files(bad_sva, manifest_path)

    contra_codes = {f.code for f in report.contradiction_candidates}
    assert FindingCode.CONTRADICTION in contra_codes
    assert FindingCode.CONSTANT_CONFLICT in contra_codes

    out_codes = {f.code for f in report.output_constraint_warnings}
    assert FindingCode.OUTPUT_CONSTRAINT in out_codes
    assert FindingCode.INTERNAL_STATE_CONSTRAINT in out_codes
    assert FindingCode.UNKNOWN_SIGNAL in out_codes

    assert report.unused_assumption_candidates  # at least one

    # A vacuity risk must be raised because contradictions exist.
    vac_error = [
        f
        for f in report.vacuity_recommendations
        if f.code is FindingCode.VACUITY_RISK and f.severity is Severity.ERROR
    ]
    assert vac_error


def test_good_corpus_is_clean(good_sva, manifest_path):
    report = analyze_files(good_sva, manifest_path)
    assert report.contradiction_candidates == []
    assert report.unused_assumption_candidates == []
    assert report.output_constraint_warnings == []
    # No high/medium-priority human-review items.
    assert all(i.priority == 3 for i in report.human_review_queue) or not report.human_review_queue


def test_every_actionable_finding_is_static_suspicion(bad_sva, manifest_path):
    report = analyze_files(bad_sva, manifest_path)
    actionable = (
        report.contradiction_candidates
        + report.unused_assumption_candidates
        + report.output_constraint_warnings
    )
    assert actionable
    for f in actionable:
        assert f.confidence is Confidence.STATIC_SUSPICION
        assert f.needs_human_review is True


def test_disclaimer_never_claims_soundness(good_sva, manifest_path):
    report = analyze_files(good_sva, manifest_path)
    d = report.disclaimer.lower()
    assert "does not mean" in d or "does not" in d
    assert "static" in d
    # Standing vacuity reminder present even when clean.
    reminders = [
        f for f in report.vacuity_recommendations if "not a soundness" in f.message.lower()
    ]
    assert reminders


def test_review_queue_prioritized(bad_sva, manifest_path):
    report = analyze_files(bad_sva, manifest_path)
    priorities = [i.priority for i in report.human_review_queue]
    assert priorities == sorted(priorities)  # ascending, P1 first
    assert 1 in priorities  # contradictions/output-constraints -> P1


def test_no_manifest_degrades_to_unknown(bad_sva):
    report = analyze_files(bad_sva, None)
    assert all(c.ownership.value == "unknown" for c in report.signal_ownership)
    # Without ownership grounding, output-constraint warnings become UNKNOWN_SIGNAL.
    assert all(
        f.code is FindingCode.UNKNOWN_SIGNAL for f in report.output_constraint_warnings
    )
