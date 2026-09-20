"""Unused-assumption and constraint-target hygiene checks."""

from __future__ import annotations

from ..models import (
    Confidence,
    Finding,
    FindingCode,
    Ownership,
    Property,
    Severity,
    SignalClassification,
    SvaKind,
)


def find_unused_assumptions(properties: list[Property]) -> list[Finding]:
    """Flag assumptions whose signals are never referenced by any assert/cover.

    An assumption exists to constrain the environment of *some* property. If none
    of the signals it constrains appear in any assertion or cover (directly or as
    a fan-in proxy via shared signals), it is a candidate for being dead - either
    stale, or masking a missing assertion.

    This is a STATIC candidate: a signal can matter through RTL fan-in the SVA
    text does not show. We say so and route to human review.
    """
    assumes = [p for p in properties if p.kind is SvaKind.ASSUME]
    checks = [p for p in properties if p.kind in (SvaKind.ASSERT, SvaKind.COVER)]

    used_signals: set[str] = set()
    for c in checks:
        used_signals.update(c.signals)

    findings: list[Finding] = []
    for a in assumes:
        overlap = set(a.signals) & used_signals
        if not overlap:
            findings.append(
                Finding(
                    code=FindingCode.UNUSED_ASSUMPTION,
                    severity=Severity.WARNING,
                    confidence=Confidence.STATIC_SUSPICION,
                    message=(
                        f"Assumption '{a.name}' constrains signals not referenced by any "
                        "assertion or cover."
                    ),
                    evidence=(
                        f"{a.name} (line {a.line}) touches {sorted(a.signals)}; none appear "
                        "in any assert/cover directive in the analyzed set. Candidate for a "
                        "stale/dead assumption OR a missing assertion. STATIC ONLY: the "
                        "signal may still matter through RTL fan-in not visible in the SVA "
                        "text - confirm before removing."
                    ),
                    properties=[a.name],
                    signals=sorted(a.signals),
                    needs_human_review=True,
                )
            )
    findings.sort(key=lambda f: f.properties)
    return findings


def find_output_constraints(
    properties: list[Property], classifications: list[SignalClassification]
) -> list[Finding]:
    """Flag assumptions that constrain DUT outputs / internal state / unknowns."""
    owner = {c.signal: c for c in classifications}
    assumes = [p for p in properties if p.kind is SvaKind.ASSUME]
    findings: list[Finding] = []

    for a in assumes:
        for sig in sorted(a.signals):
            c = owner.get(sig)
            if c is None:
                continue
            if c.ownership is Ownership.DUT_OUTPUT:
                findings.append(
                    _finding(
                        FindingCode.OUTPUT_CONSTRAINT,
                        Severity.ERROR,
                        a,
                        sig,
                        c,
                        "constrains a DUT OUTPUT. Assumptions on outputs are overconstraint: "
                        "they can mask real bugs and make the environment illegal. This should "
                        "almost always be an assertion, not an assumption.",
                    )
                )
            elif c.ownership is Ownership.INTERNAL_STATE:
                findings.append(
                    _finding(
                        FindingCode.INTERNAL_STATE_CONSTRAINT,
                        Severity.WARNING,
                        a,
                        sig,
                        c,
                        "constrains DUT INTERNAL STATE (a register/internal net). White-box "
                        "state assumptions are a common source of hidden overconstraint and "
                        "vacuous proofs.",
                    )
                )
            elif c.ownership is Ownership.UNKNOWN:
                findings.append(
                    _finding(
                        FindingCode.UNKNOWN_SIGNAL,
                        Severity.WARNING,
                        a,
                        sig,
                        c,
                        "constrains a signal that could not be classified from the manifest. "
                        "Ownership must be confirmed before trusting this assumption.",
                    )
                )
    findings.sort(key=lambda f: (f.code.value, f.properties, f.signals))
    return findings


def _finding(
    code: FindingCode,
    severity: Severity,
    a: Property,
    sig: str,
    c: SignalClassification,
    tail: str,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        confidence=Confidence.STATIC_SUSPICION,
        message=f"Assumption '{a.name}' {tail.split('.')[0].strip()}.",
        evidence=f"{a.name} (line {a.line}) assumes on '{sig}': {c.rationale} {tail}",
        properties=[a.name],
        signals=[sig],
        needs_human_review=True,
    )
