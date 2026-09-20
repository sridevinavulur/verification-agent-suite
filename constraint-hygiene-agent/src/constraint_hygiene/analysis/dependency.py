"""Property dependency map + vacuity/reachability recommendations."""

from __future__ import annotations

from ..models import (
    Confidence,
    DependencyEdge,
    Finding,
    FindingCode,
    Property,
    Severity,
    SvaKind,
)


def build_dependency_map(properties: list[Property]) -> list[DependencyEdge]:
    """For each assert/cover, map which signals it depends on and which
    assumptions constrain those same signals."""
    assumes = [p for p in properties if p.kind is SvaKind.ASSUME]
    sig_to_assumes: dict[str, list[str]] = {}
    for a in assumes:
        for s in a.signals:
            sig_to_assumes.setdefault(s, []).append(a.name)

    edges: list[DependencyEdge] = []
    for p in properties:
        if p.kind not in (SvaKind.ASSERT, SvaKind.COVER):
            continue
        for sig in sorted(set(p.signals)):
            edges.append(
                DependencyEdge(
                    property=p.name,
                    signal=sig,
                    constrained_by_assumptions=sorted(sig_to_assumes.get(sig, [])),
                )
            )
    edges.sort(key=lambda e: (e.property, e.signal))
    return edges


def vacuity_recommendations(
    properties: list[Property], contradiction_count: int
) -> list[Finding]:
    """Emit reachability/vacuity *recommendations* (never conclusions).

    Rules enforced here (from the spec):
      * We never say a proof is valid because no contradiction was found.
      * We recommend that every assertion has a paired cover/reachability check.
      * If any contradiction candidate exists, we raise a vacuity risk.
    """
    findings: list[Finding] = []
    asserts = [p for p in properties if p.kind is SvaKind.ASSERT]
    covers = [p for p in properties if p.kind is SvaKind.COVER]
    cover_signals: set[str] = set()
    for c in covers:
        cover_signals.update(c.signals)

    # Recommend reachability cover for assertions with no related cover.
    for a in asserts:
        if not (set(a.signals) & cover_signals):
            findings.append(
                Finding(
                    code=FindingCode.REACHABILITY_RISK,
                    severity=Severity.INFO,
                    confidence=Confidence.STATIC_SUSPICION,
                    message=(
                        f"Assertion '{a.name}' has no paired cover exercising its signals."
                    ),
                    evidence=(
                        f"{a.name} touches {sorted(a.signals)} but no cover directive shares "
                        "any of these signals. Add a reachability cover to guard against a "
                        "vacuous pass. RECOMMENDATION ONLY - this is not evidence of vacuity."
                    ),
                    properties=[a.name],
                    signals=sorted(a.signals),
                    needs_human_review=True,
                )
            )

    if contradiction_count > 0:
        findings.append(
            Finding(
                code=FindingCode.VACUITY_RISK,
                severity=Severity.ERROR,
                confidence=Confidence.STATIC_SUSPICION,
                message=(
                    f"{contradiction_count} contradiction candidate(s) present: high vacuity "
                    "risk for ALL assertions under these assumptions."
                ),
                evidence=(
                    "Contradictory assumptions can make the constrained state space empty, in "
                    "which case every assertion passes VACUOUSLY. Run a formal vacuity check "
                    "and resolve contradictions before trusting any PASS. Absence of a proven "
                    "counterexample is NOT proof of correctness."
                ),
                properties=[],
                signals=[],
                needs_human_review=True,
            )
        )

    # Always emit the standing reminder that clean != sound.
    findings.append(
        Finding(
            code=FindingCode.VACUITY_RISK,
            severity=Severity.INFO,
            confidence=Confidence.STATIC_SUSPICION,
            message="Reminder: a clean hygiene report is NOT a soundness or validity result.",
            evidence=(
                "This tool performs static structural checks only. It cannot and does not "
                "conclude that the constraint set is consistent, non-vacuous, or that any "
                "proof is valid. Always run formal vacuity/reachability analysis in the tool."
            ),
            properties=[],
            signals=[],
            needs_human_review=False,
        )
    )
    findings.sort(key=lambda f: (f.severity.value, f.code.value, f.properties))
    return findings
