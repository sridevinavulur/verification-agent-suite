"""Deterministic JSON serialization for the plan contract."""

from __future__ import annotations

import json

from .models import VerificationPlan


def plan_to_json(plan: VerificationPlan) -> str:
    """Stable, indented JSON (sorted keys) for golden comparison."""
    data = plan.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def plan_from_json(text: str) -> VerificationPlan:
    return VerificationPlan.model_validate_json(text)
