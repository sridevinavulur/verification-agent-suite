"""Tests for the deterministic plan engine."""

from __future__ import annotations

from vplan_agent.engine import (
    build_plan,
    classify_requirement,
    decompose,
    find_ambiguities,
)
from vplan_agent.models import (
    AmbiguityKind,
    ApprovalState,
    Category,
    InterfaceGlossary,
    InterfaceSignal,
    ManifestModuleView,
    ManifestView,
    Requirement,
    SpecDocument,
    Technique,
)


def _spec(*reqs: Requirement) -> SpecDocument:
    return SpecDocument(design_name="d", requirements=list(reqs))


def test_classification_precedence():
    assert classify_requirement(Requirement(id="1", text="on reset clear data")) is Category.RESET
    assert classify_requirement(Requirement(id="2", text="secure access control")) is Category.SECURITY
    assert classify_requirement(Requirement(id="3", text="clock domain crossing sync")) is Category.CDC_RDC
    assert classify_requirement(Requirement(id="4", text="illegal write is an error")) is Category.ERROR_HANDLING
    assert classify_requirement(Requirement(id="5", text="max throughput per cycle")) is Category.PERFORMANCE
    assert classify_requirement(Requirement(id="6", text="clock gating retention")) is Category.LOW_POWER
    assert classify_requirement(Requirement(id="7", text="top-level integration")) is Category.INTEGRATION
    assert classify_requirement(Requirement(id="8", text="add two numbers")) is Category.FUNCTIONAL


def test_decompose_assigns_ids_and_categories():
    feats = decompose(_spec(
        Requirement(id="R1", text="on reset clear the register"),
        Requirement(id="R2", text="add operands"),
    ))
    assert [f.id for f in feats] == ["FEAT-001", "FEAT-002"]
    assert feats[0].category is Category.RESET
    assert feats[0].source_requirements == ["R1"]
    assert all(f.approval is ApprovalState.PROPOSED for f in feats)


def test_security_gets_formal_technique():
    plan = build_plan(
        _spec(Requirement(id="R1", text="secure privileged access must be enforced")),
        InterfaceGlossary(design_name="d", signals=[]),
    )
    item = plan.plan_items[0]
    assert item.category is Category.SECURITY
    assert Technique.FORMAL in item.techniques


def test_risk_ranked_descending():
    plan = build_plan(
        _spec(
            Requirement(id="R1", text="add operands"),  # functional, low
            Requirement(id="R2", text="secure access must never leak"),  # security, high
        ),
        InterfaceGlossary(design_name="d", signals=[]),
    )
    scores = [p.risk_score for p in plan.plan_items]
    assert scores == sorted(scores, reverse=True)
    assert plan.plan_items[0].category is Category.SECURITY


def test_unverifiable_requirement_flagged_not_false_positive_on_fifo():
    # "fifo" contains the substring "if" - must not defeat the check.
    spec = _spec(
        Requirement(id="R1", text="The fifo is easy to use"),
        Requirement(id="R2", text="It shall respond within 3 cycles"),
    )
    ambs = find_ambiguities(spec, InterfaceGlossary(design_name="d", signals=[]),
                            ManifestView(), decompose(spec))
    unverifiable = [a for a in ambs if a.kind is AmbiguityKind.UNVERIFIABLE_REQUIREMENT]
    assert [a.ref for a in unverifiable] == ["R1"]


def test_missing_reset_and_cdc_requirements_detected():
    spec = _spec(Requirement(id="R1", text="drive outputs to match data register"))
    manifest = ManifestView(modules=[
        ManifestModuleView(
            name="m",
            reset_candidate_signals=["rst_n"],
            clock_candidate_signals=["clk_a", "clk_b"],
        )
    ])
    ambs = find_ambiguities(spec, InterfaceGlossary(design_name="d", signals=[]),
                            manifest, decompose(spec))
    kinds = {a.ref for a in ambs if a.kind is AmbiguityKind.MISSING_REQUIREMENT}
    assert "reset" in kinds
    assert "cdc_rdc" in kinds


def test_unmapped_reset_flagged():
    spec = _spec(Requirement(id="R1", text="on reset clear data"))
    manifest = ManifestView(modules=[
        ManifestModuleView(name="m", reset_candidate_signals=["por_n"])
    ])
    glossary = InterfaceGlossary(design_name="d", signals=[])
    ambs = find_ambiguities(spec, glossary, manifest, decompose(spec))
    assert any(
        a.kind is AmbiguityKind.UNMAPPED_MANIFEST_RESET and a.ref == "por_n"
        for a in ambs
    )


def test_unreferenced_signal_becomes_assumption():
    spec = _spec(Requirement(id="R1", text="drive dout from din"))
    glossary = InterfaceGlossary(design_name="d", signals=[
        InterfaceSignal(name="din", direction="input", role="data"),
        InterfaceSignal(name="dout", direction="output", role="data"),
        InterfaceSignal(name="spare", direction="output", role="debug"),
        InterfaceSignal(name="clk", direction="input", role="clock"),
    ])
    ambs = find_ambiguities(spec, glossary, ManifestView(), decompose(spec))
    assumptions = {a.ref for a in ambs if a.kind is AmbiguityKind.ASSUMPTION}
    assert "spare" in assumptions          # unreferenced debug signal
    assert "din" not in assumptions        # referenced
    assert "clk" not in assumptions        # clock role exempt


def test_traceability_covered_flag():
    plan = build_plan(
        _spec(Requirement(id="R1", text="add operands shall work")),
        InterfaceGlossary(design_name="d", signals=[]),
    )
    row = plan.traceability[0]
    assert row.requirement_id == "R1"
    assert row.covered is True
    assert row.scenario_ids


def test_manifest_state_heavy_raises_functional_risk():
    spec = _spec(Requirement(id="R1", text="the datapath must forward operands"))
    lean = build_plan(spec, InterfaceGlossary(design_name="d", signals=[]),
                      ManifestView())
    heavy = build_plan(
        spec, InterfaceGlossary(design_name="d", signals=[]),
        ManifestView(modules=[ManifestModuleView(name="m", register_count=12)]),
    )
    assert heavy.plan_items[0].risk_score > lean.plan_items[0].risk_score
