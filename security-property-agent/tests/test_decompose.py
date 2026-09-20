from __future__ import annotations

from security_property_agent.decompose import decompose
from security_property_agent.models import (
    ClauseKind,
    SecurityCategory,
    SecurityRequirement,
)


def _req(text: str, category=SecurityCategory.ACCESS_CONTROL) -> SecurityRequirement:
    return SecurityRequirement(requirement_id="R1", category=category, text=text)


def test_clauses_are_verbatim_slices():
    req = _req("A write must never occur unless wr_grant is asserted.")
    result = decompose(req)
    for c in result.clauses:
        assert result.original_text[c.span.start : c.span.end] == c.text
        assert c.text in result.original_text


def test_requirement_text_preserved_exactly():
    text = "When dbg_locked is asserted, dbg_enable must never be high."
    req = _req(text)
    result = decompose(req)
    # The tool must NEVER rewrite the original text.
    assert result.original_text == text
    from security_property_agent.util import sha256_text

    assert result.original_text_sha256 == sha256_text(text)


def test_assumption_classified_as_assumption_not_property():
    req = _req("The tester assumes wr_grant is only ever asserted by the unit.")
    result = decompose(req)
    kinds = {c.kind for c in result.clauses}
    assert ClauseKind.ENVIRONMENT_ASSUMPTION in kinds
    # It must not be silently treated as a safety property.


def test_objective_classified_as_test_objective():
    req = _req("Demonstrate a reachable scenario where secure_op fires.")
    result = decompose(req)
    kinds = {c.kind for c in result.clauses}
    assert ClauseKind.SECURITY_TEST_OBJECTIVE in kinds


def test_safety_property_classified():
    req = _req("dbg_enable must never be high.")
    result = decompose(req)
    kinds = {c.kind for c in result.clauses}
    assert ClauseKind.SAFETY_PROPERTY in kinds


def test_unclassifiable_flagged_as_ambiguity():
    req = _req("core_a_result core_b_result register")
    result = decompose(req)
    assert result.ambiguities  # something needs human review
