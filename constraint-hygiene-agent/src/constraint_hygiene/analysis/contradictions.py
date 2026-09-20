"""Contradiction / constant-conflict detection across assumptions.

We detect two *structural* contradiction classes that are unconditionally
implied by top-level conjunct facts extracted by the SVA parser:

1. Boolean contradiction: one assumption forces ``sig == 1`` while another
   forces ``sig == 0`` (i.e. ``assume sig`` vs ``assume !sig``).
2. Constant conflict: two assumptions force ``sig == C1`` and ``sig == C2``
   with ``C1 != C2``.
3. Mixed conflict: a boolean fact and an incompatible constant equality on the
   same signal (``assume !en`` vs ``assume en == 1``).

Everything reported here is a STATIC SUSPICION.  Two assumptions active in
different clocking/reset regimes might not actually conflict; we say so in the
evidence and route every finding to human review.  Critically, the *absence* of
findings here is never reported as proof of soundness.
"""

from __future__ import annotations

from itertools import combinations

from ..models import Confidence, Finding, FindingCode, Property, Severity, SvaKind


def _bool_to_const(v: bool) -> str:
    return "1" if v else "0"


def find_contradictions(properties: list[Property]) -> list[Finding]:
    assumes = [p for p in properties if p.kind is SvaKind.ASSUME]
    findings: list[Finding] = []

    # Build per-signal fact tables: signal -> list of (prop, const_value_str, kind_of_fact)
    for a, b in combinations(assumes, 2):
        findings.extend(_pairwise(a, b))

    # Deterministic ordering.
    findings.sort(key=lambda f: (f.code.value, tuple(f.properties), tuple(f.signals)))
    return findings


def _facts(p: Property) -> dict[str, str]:
    """Merge boolean + equality facts into signal -> canonical-const string."""
    merged: dict[str, str] = {}
    for sig, val in p.boolean_facts.items():
        merged[sig] = _bool_to_const(val)
    for sig, const in p.equalities.items():
        merged[sig] = const
    return merged


def _pairwise(a: Property, b: Property) -> list[Finding]:
    fa = _facts(a)
    fb = _facts(b)
    out: list[Finding] = []
    for sig in sorted(set(fa) & set(fb)):
        va, vb = fa[sig], fb[sig]
        # x/z values are not comparable -> do not claim a contradiction.
        if va.startswith(("b:", "o:", "d:", "h:")) or vb.startswith(
            ("b:", "o:", "d:", "h:")
        ):
            continue
        if va == vb:
            continue
        both_boolean = sig in a.boolean_facts and sig in b.boolean_facts
        code = FindingCode.CONTRADICTION if both_boolean else FindingCode.CONSTANT_CONFLICT
        out.append(
            Finding(
                code=code,
                severity=Severity.ERROR,
                confidence=Confidence.STATIC_SUSPICION,
                message=(
                    f"Assumptions '{a.name}' and '{b.name}' impose conflicting values on "
                    f"'{sig}' ({va} vs {vb})."
                ),
                evidence=(
                    f"{a.name} (line {a.line}) implies {sig}=={va}; "
                    f"{b.name} (line {b.line}) implies {sig}=={vb}. "
                    "Facts are top-level conjuncts. NOTE: static suspicion only - the two "
                    "assumptions could apply under different clock/reset regimes; confirm "
                    "with a formal vacuity/reachability check before acting."
                ),
                properties=[a.name, b.name],
                signals=[sig],
                needs_human_review=True,
            )
        )
    return out
