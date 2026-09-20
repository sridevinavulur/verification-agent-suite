"""Tests for model-level safety invariants."""

import pytest

from cx_triage.models import HypothesisCategory, RootCauseHypothesis


def test_design_bug_hypothesis_requires_evidence():
    """The model layer refuses an evidence-free design_bug hypothesis."""
    with pytest.raises(ValueError):
        RootCauseHypothesis(
            category=HypothesisCategory.DESIGN_BUG,
            statement="it's a bug",
            confidence=0.9,
            evidence=[],
        )


def test_non_bug_hypothesis_may_have_no_evidence():
    h = RootCauseHypothesis(
        category=HypothesisCategory.PROPERTY_ISSUE,
        statement="maybe the property",
        confidence=0.3,
        evidence=[],
    )
    assert h.category == HypothesisCategory.PROPERTY_ISSUE


def test_confidence_bounds_enforced():
    with pytest.raises(ValueError):
        RootCauseHypothesis(
            category=HypothesisCategory.PROPERTY_ISSUE,
            statement="x",
            confidence=1.5,
        )
