"""Tests for the human-approval workflow."""

from __future__ import annotations

from vplan_agent.approval import apply_decisions
from vplan_agent.engine import build_plan
from vplan_agent.models import (
    ApprovalDecision,
    ApprovalState,
    InterfaceGlossary,
    Requirement,
    SpecDocument,
)


def _plan():
    spec = SpecDocument(
        design_name="d",
        requirements=[
            Requirement(id="R1", text="on reset clear data"),
            Requirement(id="R2", text="the block is nice"),
        ],
    )
    return build_plan(spec, InterfaceGlossary(design_name="d", signals=[]))


def test_agent_never_emits_approved():
    plan = _plan()
    counts = plan.counts_by_approval()
    assert counts["approved"] == 0
    assert counts["rejected"] == 0
    assert counts["proposed"] > 0


def test_apply_decisions_promotes_and_rejects():
    plan = _plan()
    decisions = [
        ApprovalDecision(item_id="FEAT-001", decision=ApprovalState.APPROVED),
        ApprovalDecision(item_id="FEAT-002", decision=ApprovalState.REJECTED),
    ]
    updated, applied, unmatched = apply_decisions(plan, decisions)
    assert set(applied) == {"FEAT-001", "FEAT-002"}
    assert unmatched == []
    states = {f.id: f.approval for f in updated.features}
    assert states["FEAT-001"] is ApprovalState.APPROVED
    assert states["FEAT-002"] is ApprovalState.REJECTED
    # Original plan is untouched (deep copy).
    assert all(f.approval is ApprovalState.PROPOSED for f in plan.features)


def test_unmatched_decision_reported():
    plan = _plan()
    _, applied, unmatched = apply_decisions(
        plan, [ApprovalDecision(item_id="NOPE-999", decision=ApprovalState.APPROVED)]
    )
    assert applied == []
    assert unmatched == ["NOPE-999"]


def test_already_decided_item_not_reapplied():
    plan = _plan()
    d = [ApprovalDecision(item_id="FEAT-001", decision=ApprovalState.APPROVED)]
    once, _, _ = apply_decisions(plan, d)
    # Re-applying a rejection to an already-approved item must not change it.
    twice, applied, unmatched = apply_decisions(
        once, [ApprovalDecision(item_id="FEAT-001", decision=ApprovalState.REJECTED)]
    )
    # The item exists (so it is matched, not "unmatched"), but it is no longer
    # proposed, so the new decision is NOT applied - the human decision stands.
    assert applied == []
    assert unmatched == []
    assert twice.features[0].approval is ApprovalState.APPROVED
