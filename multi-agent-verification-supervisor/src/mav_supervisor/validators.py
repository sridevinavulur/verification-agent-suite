"""Deterministic validation gates for candidate properties.

These are the *non-LLM* checks that the supervisor runs before accepting a
candidate property. They implement the mandatory rejection rules:

* unresolved signal grounding
* ambiguous clock/reset
* syntax failure
* insufficient review state

The supervisor REJECTS the property if any of these fire. Nothing here calls a
property "correct"; a clean report only means the property is *eligible* to
proceed to partition analysis and (gated) execution.
"""

from __future__ import annotations

import re

from .models import CandidateProperty, ReviewState, RtlManifest

# Very small, conservative SVA-ish syntax gate. This is deliberately a syntactic
# smoke check, not a SystemVerilog parser: balanced parens, presence of an
# implication or a boolean body, and no obviously dangling operators.
_IMPLICATION = re.compile(r"\|->|\|=>")
_DANGLING_OP = re.compile(r"(\|->|\|=>|&&|\|\||##)\s*$")


def _balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def check_syntax(prop: CandidateProperty) -> list[str]:
    findings: list[str] = []
    text = prop.sva_text.strip()
    if not text:
        findings.append("SYNTAX: empty SVA text.")
        return findings
    if not _balanced(text):
        findings.append("SYNTAX: unbalanced parentheses.")
    if _DANGLING_OP.search(text):
        findings.append("SYNTAX: expression ends with a dangling operator.")
    # A response/implication property must contain an implication operator.
    references_handshake = "grant" in text or "req" in text
    if references_handshake and prop.property_kind == "assert" and not _IMPLICATION.search(text):
        # Flag a weak/degenerate implication form for a handshake response property.
        findings.append("SYNTAX: assert property lacks an implication operator.")
    return findings


def check_grounding(prop: CandidateProperty, manifest: RtlManifest) -> list[str]:
    findings: list[str] = []
    if not prop.groundings:
        findings.append("GROUNDING: property has no signal groundings.")
    ungrounded = prop.ungrounded_terms()
    if ungrounded:
        findings.append(
            f"GROUNDING: unresolved terms with no RTL symbol: {sorted(ungrounded)}."
        )
    symbols = manifest.symbol_names()
    for g in prop.groundings:
        if g.symbol is not None and g.symbol not in symbols:
            findings.append(
                f"GROUNDING: term '{g.term}' maps to '{g.symbol}' "
                "which is not present in the RTL manifest."
            )
    return findings


def check_clock_reset(prop: CandidateProperty, manifest: RtlManifest) -> list[str]:
    findings: list[str] = []
    if prop.clock_signal is None:
        findings.append("CLOCK: temporal property has no clock; underspecified.")
    elif prop.clock_signal not in manifest.clock_candidates:
        findings.append(
            f"CLOCK: '{prop.clock_signal}' is not among RTL clock candidates "
            f"{manifest.clock_candidates}."
        )
    # Reset is required to be unambiguous only if the property references reset.
    references_reset = prop.reset_signal is not None or "reset" in prop.sva_text.lower(
    ) or "rst" in prop.sva_text.lower()
    if references_reset:
        if prop.reset_signal is None:
            findings.append("RESET: property references reset but no reset signal set.")
        elif prop.reset_signal not in manifest.reset_candidates:
            findings.append(
                f"RESET: '{prop.reset_signal}' is not among RTL reset candidates "
                f"{manifest.reset_candidates}."
            )
        if prop.reset_polarity in (None, "unknown"):
            findings.append("RESET: reset polarity is ambiguous/unknown.")
    return findings


def check_review(prop: CandidateProperty) -> list[str]:
    findings: list[str] = []
    if prop.review_state == ReviewState.REVIEWED_REJECTED:
        findings.append("REVIEW: property was rejected during review.")
    elif prop.review_state != ReviewState.REVIEWED_OK:
        findings.append(
            "REVIEW: insufficient review state "
            f"({prop.review_state.value}); REVIEWED_OK required."
        )
    return findings


def validate_property(prop: CandidateProperty, manifest: RtlManifest) -> list[str]:
    """Run all deterministic gates. Empty list => property is eligible."""

    findings: list[str] = []
    findings += check_syntax(prop)
    findings += check_grounding(prop, manifest)
    findings += check_clock_reset(prop, manifest)
    findings += check_review(prop)
    return findings
