from __future__ import annotations

from coverage_closure_agent.models import AllowedAction, HoleCategory
from coverage_closure_agent.triage import TriageEngine


def test_all_recommendations_are_allowed_actions(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    allowed = set(AllowedAction)
    for c in report.classifications:
        for r in c.recommendations:
            assert r.action in allowed


def test_recommendations_are_priority_sorted(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    for c in report.classifications:
        scores = [r.priority_score for r in c.recommendations]
        assert scores == sorted(scores, reverse=True), c.coverage_id


def test_not_run_hole_recommends_running_existing_test(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    c = next(x for x in report.classifications if x.coverage_id == "cov.fifo.branch.overflow_guard")
    assert c.recommendations[0].action == AllowedAction.RUN_EXISTING_TEST
    # Detail should carry a runnable seed/config from the manifest.
    assert "seed=7" in c.recommendations[0].detail


def test_unreachable_hole_top_action_is_inspect(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    c = next(x for x in report.classifications if x.coverage_id == "cov.cnt.stmt.dead")
    assert c.category == HoleCategory.LIKELY_UNREACHABLE
    assert c.recommendations[0].action == AllowedAction.INSPECT_UNREACHABLE_CODE
    # Waiver is only *requested for review*, never auto-applied.
    waiver = next(r for r in c.recommendations if r.action == AllowedAction.REQUEST_WAIVER_REVIEW)
    assert waiver.requires_human_approval is True


def test_every_recommendation_requires_human_approval(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    for c in report.classifications:
        for r in c.recommendations:
            assert r.requires_human_approval is True


def test_expected_impact_is_labelled_hypothesis(toy_inputs):
    report = TriageEngine().run(toy_inputs)
    for c in report.classifications:
        for r in c.recommendations:
            assert "hypothesis" in r.expected_impact_note.lower()
