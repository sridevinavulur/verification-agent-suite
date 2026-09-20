from __future__ import annotations

from coverage_closure_agent.models import ProhibitedAction
from coverage_closure_agent.triage import TriageEngine, compute_metrics


def test_valid_and_provenance_rates(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    m = report.metrics
    # All emitted actions are in the allowed set -> valid rate is exactly 1.0.
    assert m.valid_proposal_rate == 1.0
    assert m.provenance_completeness == 1.0
    assert m.total_recommendations > 0


def test_sample_metrics_computed(toy_inputs, toy_labels):
    report = TriageEngine().run(toy_inputs)
    scored = compute_metrics(report.classifications, sample=toy_labels)
    assert scored.sample_size == 9
    # Golden benchmark is hand-labelled so category precision is perfect.
    assert scored.category_precision == 1.0
    assert scored.accepted_proposal_rate is not None
    assert 0.0 <= scored.accepted_proposal_rate <= 1.0
    assert scored.false_positive_proposal_rate is not None
    # cov.cnt.toggle.msb rejects add_constrained_random_scenario -> nonzero FP.
    assert scored.false_positive_proposal_rate > 0.0


def test_prohibited_actions_enforced_registry(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    enforced = set(report.prohibited_actions_enforced)
    assert enforced == set(ProhibitedAction)


def test_no_recommendation_is_a_prohibited_action(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    prohibited_values = {p.value for p in ProhibitedAction}
    for c in report.classifications:
        for r in c.recommendations:
            assert r.action.value not in prohibited_values


def test_independent_measurement_covers_every_hole(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    hole_ids = {c.coverage_id for c in report.classifications}
    measured_ids = {s.coverage_id for s in report.independent_measurement}
    assert hole_ids == measured_ids


def test_human_review_queue_covers_every_hole(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    hole_ids = {c.coverage_id for c in report.classifications}
    review_ids = {i.coverage_id for i in report.human_review_queue}
    assert hole_ids == review_ids


def test_scope_note_disclaims_closure_and_modification(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    note = report.scope_provenance.scope_note.lower()
    assert "did not modify" in note
    assert "authoritative" in note


def test_input_hashes_present_and_stable(toy_inputs):
    r1 = TriageEngine().run(toy_inputs)
    r2 = TriageEngine().run(toy_inputs)
    assert set(r1.scope_provenance.input_hashes) == {
        "coverage",
        "tests",
        "rtl",
        "requirements",
        "logs",
    }
    assert r1.scope_provenance.input_hashes == r2.scope_provenance.input_hashes
    assert all(v.startswith("sha256:") for v in r1.scope_provenance.input_hashes.values())
