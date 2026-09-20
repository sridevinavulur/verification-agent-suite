"""Requirement-traceability status check.

Traceability tags are read from SVA comments of the form:

    // @requirement: REQ-042

associated with the property that follows. The runner extracts these before
running checks (see ``review.py``) and populates ``ctx.traced``.
"""

from __future__ import annotations

from ..models import CheckId, Finding, PropertyKind, Severity
from .context import CheckContext


def check_requirement_traceability(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.kind == PropertyKind.COVER:
        return []
    key = p.name or f"@line{p.location.line}"
    req = ctx.traced.get(key)
    if req is None:
        return [
            Finding(
                check_id=CheckId.REQ_TRACEABILITY,
                severity=Severity.INFO,
                message="Property is not traced to any requirement "
                "(no '// @requirement: <id>' tag).",
                location=p.location,
                property_name=p.name,
                recommendation="Tag the property with the requirement it verifies.",
            )
        ]
    if ctx.requirement_ids and req not in ctx.requirement_ids:
        return [
            Finding(
                check_id=CheckId.REQ_TRACEABILITY,
                severity=Severity.WARNING,
                message=f"Property is traced to '{req}', which is not in the known "
                "requirement set.",
                location=p.location,
                property_name=p.name,
                recommendation="Fix the requirement ID or add it to the requirement set.",
            )
        ]
    return []
