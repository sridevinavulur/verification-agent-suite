from __future__ import annotations

from coverage_closure_agent.models import HoleCategory
from coverage_closure_agent.triage import TriageEngine


def _by_id(report):
    return {c.coverage_id: c for c in report.classifications}


def test_covered_items_are_not_holes(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    ids = {c.coverage_id for c in report.classifications}
    # The one covered item (hits=12) must be absent from the classification set.
    assert "cov.fifo.branch.full" not in ids
    assert report.scope_provenance.total_items == 10
    assert report.scope_provenance.total_holes == 9


def test_expected_categories(toy_inputs):
    c = _by_id(TriageEngine().run(toy_inputs))
    assert c["cov.arb.fsm.error"].category == HoleCategory.NO_LINKED_TEST
    assert c["cov.misc.bin.orphan"].category == HoleCategory.NO_LINKED_TEST
    assert c["cov.arb.fsm.grant2"].category == HoleCategory.TEST_RAN_BUT_FAILED
    assert c["cov.cnt.stmt.dead"].category == HoleCategory.LIKELY_UNREACHABLE
    assert c["cov.dbg.stmt.excluded"].category == HoleCategory.LIKELY_UNREACHABLE
    assert c["cov.cnt.toggle.msb"].category == HoleCategory.TEST_RAN_STILL_UNCOVERED
    assert c["cov.fifo.branch.empty"].category == HoleCategory.TEST_RAN_STILL_UNCOVERED
    assert c["cov.hs.assert.req_grant"].category == HoleCategory.TEST_RAN_STILL_UNCOVERED
    assert c["cov.fifo.branch.overflow_guard"].category == HoleCategory.TEST_EXISTS_NOT_RUN


def test_failed_test_evidence_cites_log(toy_inputs):
    c = _by_id(TriageEngine().run(toy_inputs))["cov.arb.fsm.grant2"]
    sources = {e.source for e in c.evidence}
    assert "failure_log" in sources
    assert any("arb_grant_within_3" in e.detail for e in c.evidence)


def test_every_hole_has_hypothesis_and_evidence(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    for c in report.classifications:
        assert c.root_cause_hypotheses, c.coverage_id
        assert len(c.evidence) >= 2, c.coverage_id
        assert c.is_heuristic is True


def test_determinism(toy_inputs):
    r1 = TriageEngine(seed=0).run(toy_inputs)
    r2 = TriageEngine(seed=0).run(toy_inputs)
    assert r1.model_dump(mode="json") == r2.model_dump(mode="json")


def test_assertion_kind_proposes_assertion_candidate(toy_inputs):
    c = _by_id(TriageEngine().run(toy_inputs))["cov.hs.assert.req_grant"]
    actions = {r.action.value for r in c.recommendations}
    assert "propose_assertion_candidate" in actions
