from __future__ import annotations

import pytest

from mav_supervisor.models import TERMINAL_STATES, WorkflowState
from mav_supervisor.state_machine import (
    ALLOWED_TRANSITIONS,
    ProhibitedTransition,
    assert_transition,
    is_allowed,
)

S = WorkflowState


def test_happy_path_transitions_are_allowed() -> None:
    path = [
        S.CREATED, S.RTL_INGESTION, S.SVA_PROPOSAL, S.PROPERTY_REVIEW,
        S.PARTITION_ANALYSIS, S.PLAN_EXPERIMENT, S.EXECUTION,
        S.EVIDENCE_ASSEMBLY, S.DONE,
    ]
    for src, dst in zip(path, path[1:], strict=False):
        assert is_allowed(src, dst), f"{src} -> {dst} should be allowed"


def test_gated_path_through_approval_is_allowed() -> None:
    assert is_allowed(S.PLAN_EXPERIMENT, S.AWAITING_HUMAN_APPROVAL)
    assert is_allowed(S.AWAITING_HUMAN_APPROVAL, S.EXECUTION)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for t in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[t] == frozenset()


def test_direct_jump_to_execution_is_prohibited() -> None:
    # Skipping RTL/SVA/review straight to execution must be blocked.
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.CREATED, S.EXECUTION)


def test_skipping_review_is_prohibited() -> None:
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.SVA_PROPOSAL, S.PARTITION_ANALYSIS)


def test_cannot_leave_terminal_state() -> None:
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.DONE, S.EXECUTION)
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.REJECTED, S.PLAN_EXPERIMENT)


def test_execution_cannot_go_backwards() -> None:
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.EXECUTION, S.SVA_PROPOSAL)
