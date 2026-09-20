"""Tests for the typed Pydantic contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vplan_agent.models import (
    ApprovalState,
    Category,
    Feature,
    PlanItem,
    Priority,
    Provenance,
    Requirement,
    SpecDocument,
    VerificationPlan,
)


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Requirement(id="R1", text="x", bogus=1)  # type: ignore[call-arg]


def test_risk_score_bounds_enforced():
    with pytest.raises(ValidationError):
        PlanItem(
            id="P1",
            feature_id="F1",
            category=Category.FUNCTIONAL,
            priority=Priority.P0,
            risk_score=101,
        )


def test_default_approval_is_proposed():
    f = Feature(id="F1", name="n", category=Category.RESET, description="d")
    assert f.approval is ApprovalState.PROPOSED


def test_counts_by_approval():
    plan = VerificationPlan(
        design_name="d",
        provenance=Provenance(),
        features=[
            Feature(id="F1", name="a", category=Category.FUNCTIONAL, description="d"),
            Feature(
                id="F2",
                name="b",
                category=Category.RESET,
                description="d",
                approval=ApprovalState.APPROVED,
            ),
        ],
    )
    counts = plan.counts_by_approval()
    assert counts["proposed"] == 1
    assert counts["approved"] == 1
    assert counts["rejected"] == 0


def test_spec_roundtrips():
    spec = SpecDocument(
        design_name="d",
        requirements=[Requirement(id="R1", text="shall do x")],
    )
    dumped = spec.model_dump_json()
    assert SpecDocument.model_validate_json(dumped) == spec
