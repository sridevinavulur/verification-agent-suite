"""Human-approval workflow.

The agent only ever *proposes* content. A human reviewer records decisions in a
JSON decisions file (a list of :class:`ApprovalDecision`). :func:`apply_decisions`
walks the plan and promotes/demotes matching items by id, returning a new plan
plus a report of applied and unmatched decisions.

This keeps the authority boundary explicit and auditable (BUILD_STANDARD:
"No agent modifies ... signoff conclusions without a documented human-approval
gate").
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from .models import ApprovalDecision, ApprovalState, VerificationPlan

_DECISIONS_ADAPTER = TypeAdapter(list[ApprovalDecision])


def load_decisions(path: Path) -> list[ApprovalDecision]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _DECISIONS_ADAPTER.validate_python(data)


def apply_decisions(
    plan: VerificationPlan, decisions: list[ApprovalDecision]
) -> tuple[VerificationPlan, list[str], list[str]]:
    """Return (new_plan, applied_ids, unmatched_ids).

    Only ``proposed`` items may be promoted; already-decided items are left as
    is and reported as unmatched to keep the workflow explicit.
    """
    by_id = {d.item_id: d for d in decisions}
    applied: list[str] = []
    matched_ids: set[str] = set()

    plan = plan.model_copy(deep=True)
    groups = (
        plan.features,
        plan.plan_items,
        plan.scenarios,
        plan.assertions,
        plan.coverage_targets,
    )
    for group in groups:
        for item in group:
            decision = by_id.get(item.id)
            if decision is None:
                continue
            matched_ids.add(item.id)
            if item.approval is ApprovalState.PROPOSED:
                item.approval = decision.decision
                applied.append(item.id)

    unmatched = [d.item_id for d in decisions if d.item_id not in matched_ids]
    return plan, applied, unmatched
