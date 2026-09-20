"""Build the prioritized human-review queue from all findings.

The queue makes the human-approval gate concrete: no assumption may be changed
without a human working this queue. Priority 1 = must review before signoff.
"""

from __future__ import annotations

from ..models import Finding, FindingCode, ReviewItem, Severity

_PRIORITY_BY_CODE = {
    FindingCode.CONTRADICTION: 1,
    FindingCode.CONSTANT_CONFLICT: 1,
    FindingCode.OUTPUT_CONSTRAINT: 1,
    FindingCode.VACUITY_RISK: 1,
    FindingCode.INTERNAL_STATE_CONSTRAINT: 2,
    FindingCode.UNKNOWN_SIGNAL: 2,
    FindingCode.UNUSED_ASSUMPTION: 3,
    FindingCode.REACHABILITY_RISK: 3,
}


def build_review_queue(all_findings: list[Finding]) -> list[ReviewItem]:
    # Group by subject (a property name, or "<constraint-set>" for global items).
    grouped: dict[str, dict] = {}
    for f in all_findings:
        if not f.needs_human_review:
            continue
        if f.severity is Severity.INFO and f.code not in (
            FindingCode.VACUITY_RISK,
            FindingCode.REACHABILITY_RISK,
        ):
            continue
        subject = f.properties[0] if f.properties else "<constraint-set>"
        entry = grouped.setdefault(
            subject,
            {"priority": 3, "reasons": [], "codes": set()},
        )
        entry["priority"] = min(entry["priority"], _PRIORITY_BY_CODE.get(f.code, 3))
        entry["reasons"].append(f.message)
        entry["codes"].add(f.code)

    items: list[ReviewItem] = []
    for subject, entry in grouped.items():
        items.append(
            ReviewItem(
                priority=entry["priority"],
                subject=subject,
                reason="; ".join(sorted(set(entry["reasons"]))),
                related_findings=sorted(entry["codes"], key=lambda c: c.value),
            )
        )
    items.sort(key=lambda i: (i.priority, i.subject))
    return items
