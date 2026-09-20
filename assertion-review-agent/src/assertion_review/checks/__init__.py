"""Deterministic static checks for SVA properties.

Each check is a pure function ``(ctx) -> list[Finding]``. The registry below
is the single source of truth for which checks run and in what order.
"""

from __future__ import annotations

from collections.abc import Callable

from ..models import Finding
from .context import CheckContext
from .static_checks import (
    check_antecedent_in_consequent,
    check_assume_constrains_output,
    check_disable_iff,
    check_implication_style,
    check_missing_clock,
    check_name_semantics,
    check_reset_polarity,
    check_signals,
    check_trivially_passing,
    check_unbounded_temporal,
    check_vacuity_risk,
    check_weak_consequent,
)
from .traceability import check_requirement_traceability

Check = Callable[[CheckContext], list[Finding]]

# Order matters only for stable, human-friendly output ordering; findings are
# additionally sorted by (line, severity) in the runner.
REGISTRY: list[Check] = [
    check_missing_clock,
    check_disable_iff,
    check_reset_polarity,
    check_implication_style,
    check_unbounded_temporal,
    check_weak_consequent,
    check_antecedent_in_consequent,
    check_trivially_passing,
    check_assume_constrains_output,
    check_signals,
    check_name_semantics,
    check_requirement_traceability,
    check_vacuity_risk,
]

__all__ = ["REGISTRY", "Check", "CheckContext"]
