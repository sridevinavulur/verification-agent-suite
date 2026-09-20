from __future__ import annotations

from security_property_agent.decompose import decompose
from security_property_agent.generate import generate_candidates, generate_mutations
from security_property_agent.grounding import ground
from security_property_agent.models import (
    ClauseKind,
    PropertyForm,
    PropertyKind,
    SecurityCategory,
    SecurityRequirement,
)


def _artifacts(text, category, manifest, signals=None, boundary=None):
    req = SecurityRequirement(
        requirement_id="R1",
        category=category,
        text=text,
        signals=signals or [],
        declared_trust_boundary=boundary,
    )
    decomp = decompose(req)
    g = ground(req, manifest)
    cands, skips = generate_candidates(req, decomp.clauses, g)
    return req, decomp, g, cands, skips


def test_access_control_implication(manifest):
    _, _, _, cands, _ = _artifacts(
        "A committed write must never occur unless wr_grant is asserted.",
        SecurityCategory.ACCESS_CONTROL,
        manifest,
        signals=["wr_commit", "wr_grant", "mem_wr_en"],
    )
    assert cands
    c = cands[0]
    assert c.property_kind is PropertyKind.ASSERT
    assert c.property_form is PropertyForm.IMPLICATION
    assert "wr_commit" in c.sva_text and "wr_grant" in c.sva_text


def test_debug_lockout_implies_disabled(manifest):
    _, _, _, cands, _ = _artifacts(
        "When dbg_locked is asserted, dbg_enable must never be high.",
        SecurityCategory.DEBUG_LOCKOUT,
        manifest,
        signals=["dbg_locked", "dbg_enable"],
    )
    assert cands
    assert "dbg_locked" in cands[0].sva_text
    assert "!dbg_enable" in cands[0].sva_text


def test_fault_response_is_bounded(manifest):
    _, _, _, cands, _ = _artifacts(
        "When fault_detected is high, safe_halt must assert within a few cycles.",
        SecurityCategory.FAULT_RESPONSE,
        manifest,
        signals=["fault_detected", "safe_halt"],
    )
    assert cands
    assert cands[0].property_form is PropertyForm.BOUNDED_RESPONSE
    assert "##[1:3]" in cands[0].sva_text


def test_lockstep_generates_equality(manifest):
    _, _, _, cands, _ = _artifacts(
        "The redundant cores core_a_result and core_b_result must always match.",
        SecurityCategory.LOCKSTEP_MISMATCH,
        manifest,
        signals=["core_a_result", "core_b_result"],
    )
    assert cands
    assert cands[0].property_form is PropertyForm.LOCKSTEP_EQUAL
    assert " == " in cands[0].sva_text


def test_environment_assumption_never_emitted_as_assert(manifest):
    req = SecurityRequirement(
        requirement_id="R1",
        category=SecurityCategory.ACCESS_CONTROL,
        text="The tester assumes wr_grant is only ever asserted by the unit.",
        signals=["wr_grant"],
    )
    decomp = decompose(req)
    # sanity: it decomposed to an assumption
    assert any(c.kind is ClauseKind.ENVIRONMENT_ASSUMPTION for c in decomp.clauses)
    g = ground(req, manifest)
    cands, skips = generate_candidates(req, decomp.clauses, g)
    assert all(c.property_kind is not PropertyKind.ASSERT for c in cands)
    assert any("environment assumption" in s or "not grounded" in s for s in skips) or not cands


def test_objective_becomes_cover(manifest):
    _, _, _, cands, _ = _artifacts(
        "Demonstrate a reachable scenario where secure_op fires while priv_mode is set.",
        SecurityCategory.PRIVILEGE_GATING,
        manifest,
        signals=["secure_op", "priv_mode"],
    )
    covers = [c for c in cands if c.property_kind is PropertyKind.COVER]
    assert covers
    assert covers[0].property_form is PropertyForm.REACHABLE


def test_unresolved_symbols_cause_skip_not_guess(manifest):
    _, _, _, cands, skips = _artifacts(
        "made_up_a must equal made_up_b.",
        SecurityCategory.LOCKSTEP_MISMATCH,
        manifest,
        signals=["made_up_a", "made_up_b"],
    )
    assert not cands
    assert skips


def test_mutations_are_should_fail_witnesses(manifest):
    _, _, _, cands, _ = _artifacts(
        "A committed write must never occur unless wr_grant is asserted.",
        SecurityCategory.ACCESS_CONTROL,
        manifest,
        signals=["wr_commit", "wr_grant"],
    )
    muts = generate_mutations(cands[0])
    assert muts
    for m in muts:
        assert m.expected_effect == "should_fail_if_original_is_meaningful"
        assert m.mutated_sva_text != cands[0].sva_text


def test_candidate_status_is_never_verified(manifest):
    _, _, _, cands, _ = _artifacts(
        "A committed write must never occur unless wr_grant is asserted.",
        SecurityCategory.ACCESS_CONTROL,
        manifest,
        signals=["wr_commit", "wr_grant"],
    )
    for c in cands:
        assert "candidate" in c.status
        assert "verified" not in c.status
