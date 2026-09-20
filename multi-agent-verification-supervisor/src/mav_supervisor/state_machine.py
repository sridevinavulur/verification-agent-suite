"""Explicit state-machine transition table for the supervisor.

This is the single authoritative source of *allowed* transitions. Anything not
listed is *prohibited*. ``assert_transition`` raises ``ProhibitedTransition`` on
any illegal move -- this is how the red-team tests prove the supervisor cannot be
walked into an unsafe state (e.g. jumping straight to EXECUTION).
"""

from __future__ import annotations

from .models import TERMINAL_STATES, WorkflowState

S = WorkflowState

# Mapping: from_state -> set of legal next states.
ALLOWED_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    S.CREATED: frozenset({S.RTL_INGESTION, S.FAILED, S.REJECTED}),
    S.RTL_INGESTION: frozenset({S.SVA_PROPOSAL, S.FAILED, S.REJECTED}),
    S.SVA_PROPOSAL: frozenset({S.PROPERTY_REVIEW, S.FAILED, S.REJECTED}),
    # Review can pass to partitioning, retry (back to SVA_PROPOSAL), or reject.
    S.PROPERTY_REVIEW: frozenset(
        {S.PARTITION_ANALYSIS, S.SVA_PROPOSAL, S.REJECTED, S.FAILED}
    ),
    S.PARTITION_ANALYSIS: frozenset({S.PLAN_EXPERIMENT, S.FAILED, S.REJECTED}),
    # Planning either needs approval (gate) or goes straight to execution.
    S.PLAN_EXPERIMENT: frozenset(
        {S.AWAITING_HUMAN_APPROVAL, S.EXECUTION, S.FAILED, S.REJECTED}
    ),
    # The approval gate can proceed to execution or reject (approval denied).
    S.AWAITING_HUMAN_APPROVAL: frozenset({S.EXECUTION, S.REJECTED, S.FAILED}),
    S.EXECUTION: frozenset({S.EVIDENCE_ASSEMBLY, S.FAILED}),
    S.EVIDENCE_ASSEMBLY: frozenset({S.DONE, S.FAILED}),
    # Terminal states have no outgoing transitions.
    S.DONE: frozenset(),
    S.REJECTED: frozenset(),
    S.FAILED: frozenset(),
}


class ProhibitedTransition(RuntimeError):
    """Raised when a state transition is not in ALLOWED_TRANSITIONS."""


def is_allowed(src: WorkflowState, dst: WorkflowState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


def assert_transition(src: WorkflowState, dst: WorkflowState) -> None:
    if src in TERMINAL_STATES:
        raise ProhibitedTransition(
            f"{src.value} is terminal; no transition to {dst.value} is allowed."
        )
    if not is_allowed(src, dst):
        allowed = sorted(s.value for s in ALLOWED_TRANSITIONS.get(src, frozenset()))
        raise ProhibitedTransition(
            f"Prohibited transition {src.value} -> {dst.value}. "
            f"Allowed from {src.value}: {allowed}."
        )
