from __future__ import annotations

import pytest
from pydantic import ValidationError

from coverage_closure_agent.models import (
    AllowedAction,
    CoverageDB,
    CoverageItem,
    CoverageKind,
    Recommendation,
)


def test_coverage_item_is_covered():
    item = CoverageItem(coverage_id="c1", kind=CoverageKind.BRANCH, hits=0, module="m")
    assert not item.is_covered
    assert CoverageItem(coverage_id="c2", kind=CoverageKind.BRANCH, hits=1, module="m").is_covered
    assert not CoverageItem(
        coverage_id="c3", kind=CoverageKind.BRANCH, hits=1, goal=2, module="m"
    ).is_covered


def test_coverage_db_forbids_extra_fields():
    with pytest.raises(ValidationError):
        CoverageDB.model_validate({"items": [], "bogus": 1})


def test_negative_hits_rejected():
    with pytest.raises(ValidationError):
        CoverageItem(coverage_id="c", kind=CoverageKind.BRANCH, hits=-1, module="m")


def test_recommendation_priority_bounds():
    with pytest.raises(ValidationError):
        Recommendation(
            action=AllowedAction.RUN_EXISTING_TEST,
            rationale="x",
            priority_score=1.5,
            expected_impact_items=1,
        )


def test_recommendation_only_allowed_actions():
    # Every AllowedAction value must construct a valid recommendation.
    for a in AllowedAction:
        r = Recommendation(action=a, rationale="r", priority_score=0.5, expected_impact_items=0)
        assert r.action in AllowedAction
        assert r.requires_human_approval is True
