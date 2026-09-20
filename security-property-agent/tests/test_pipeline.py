from __future__ import annotations

import json

from security_property_agent.io_utils import dump_report
from security_property_agent.models import PropertyKind, SecurityReviewReport
from security_property_agent.pipeline import run_pipeline


def test_pipeline_end_to_end(reqset, manifest):
    report = run_pipeline(reqset, manifest, run_id="t")
    assert isinstance(report, SecurityReviewReport)
    assert report.manifest_top == "secure_soc"
    # Every requirement produces an artifact.
    assert len(report.artifacts) == len(reqset.requirements)
    # At least the six guarantee-style requirements emit candidates.
    total_cands = sum(len(a.candidates) for a in report.artifacts)
    assert total_cands >= 6


def test_pipeline_emits_non_claims(reqset, manifest):
    report = run_pipeline(reqset, manifest, run_id="t")
    assert report.non_claims
    joined = " ".join(report.non_claims).lower()
    assert "does not prove" in joined
    assert "not verification" in joined


def test_pipeline_checklist_present(reqset, manifest):
    report = run_pipeline(reqset, manifest, run_id="t")
    assert report.checklist
    assert all(item.status == "pending" for item in report.checklist)


def test_no_candidate_reports_errors(reqset, manifest):
    report = run_pipeline(reqset, manifest, run_id="t")
    for a in report.artifacts:
        assert not a.has_errors, f"{a.requirement.requirement_id} has ERROR checks"


def test_report_is_json_serializable_and_deterministic(reqset, manifest):
    r1 = run_pipeline(reqset, manifest, run_id="t", git_sha="abc")
    r2 = run_pipeline(reqset, manifest, run_id="t", git_sha="abc")
    assert dump_report(r1) == dump_report(r2)
    # And it round-trips through JSON.
    json.loads(dump_report(r1))


def test_env_assumption_requirement_not_emitted_as_assert(reqset, manifest):
    report = run_pipeline(reqset, manifest, run_id="t")
    env = next(a for a in report.artifacts if a.requirement.requirement_id == "SEC-ENV-001")
    assert all(c.property_kind is not PropertyKind.ASSERT for c in env.candidates)
