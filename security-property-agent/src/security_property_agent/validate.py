"""Deterministic static validation checks on generated artifacts.

These are the ONLY things this tool can honestly claim: syntactic / structural
sanity. None of these constitute a formal security proof.
"""

from __future__ import annotations

from .models import (
    CandidateProperty,
    GroundingResult,
    PropertyKind,
    Severity,
    ValidationCheck,
)
from .renderer import RenderError, safe_expr


def validate_candidate(
    candidate: CandidateProperty, grounding: GroundingResult
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    # 1. Every referenced symbol must be grounded with evidence.
    ungrounded = [s.term for s in candidate.referenced_symbols if not s.symbol]
    checks.append(
        ValidationCheck(
            name="all_symbols_grounded",
            passed=not ungrounded,
            severity=Severity.ERROR,
            detail="" if not ungrounded else f"ungrounded terms: {ungrounded}",
        )
    )

    # 2. The rendered SVA must be non-empty and contain a directive.
    has_directive = any(
        d in candidate.sva_text for d in ("assert property", "assume property", "cover property")
    )
    checks.append(
        ValidationCheck(
            name="has_directive",
            passed=has_directive,
            severity=Severity.ERROR,
            detail="" if has_directive else "no SVA directive found",
        )
    )

    # 3. The clocking block must be present (clocked property).
    checks.append(
        ValidationCheck(
            name="has_clocking",
            passed="@(posedge" in candidate.sva_text,
            severity=Severity.ERROR,
            detail="" if "@(posedge" in candidate.sva_text else "no clocking block",
        )
    )

    # 4. Directive kind must match the property_kind field.
    expected = {
        PropertyKind.ASSERT: "assert property",
        PropertyKind.ASSUME: "assume property",
        PropertyKind.COVER: "cover property",
    }[candidate.property_kind]
    checks.append(
        ValidationCheck(
            name="directive_matches_kind",
            passed=expected in candidate.sva_text,
            severity=Severity.WARNING,
            detail="" if expected in candidate.sva_text else f"expected {expected}",
        )
    )

    # 5. Explicit non-claim reminder (always INFO, always present).
    checks.append(
        ValidationCheck(
            name="not_a_formal_proof",
            passed=True,
            severity=Severity.INFO,
            detail="candidate rendered offline; no formal proof performed",
        )
    )
    return checks


def validate_expression_safe(expr: str) -> ValidationCheck:
    try:
        safe_expr(expr)
        return ValidationCheck(
            name="expression_whitelist", passed=True, severity=Severity.ERROR
        )
    except RenderError as e:
        return ValidationCheck(
            name="expression_whitelist",
            passed=False,
            severity=Severity.ERROR,
            detail=str(e),
        )
