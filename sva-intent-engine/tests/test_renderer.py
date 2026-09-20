from __future__ import annotations

import pytest

from sva_intent_engine.models import (
    ImplicationStyle,
    PropertyForm,
    PropertyKind,
    Provenance,
    ResetPolarity,
    TemporalIntent,
)
from sva_intent_engine.renderer import RenderError, render, render_property, safe_expr


def _intent(**kw) -> TemporalIntent:
    base = {
        "requirement_id": "r",
        "clause_id": "r.c0",
        "source_text": "x",
        "design_top": "dut",
        "property_kind": PropertyKind.ASSERT,
        "property_form": PropertyForm.INVARIANT,
        "render_template_id": "invariant",
        "clock_signal": "clk",
        "confidence": 0.9,
        "provenance": Provenance(stage="test"),
    }
    base.update(kw)
    return TemporalIntent(**base)


# --- safe_expr whitelist -------------------------------------------------
def test_safe_expr_accepts_boolean():
    assert safe_expr("valid && ready") == "valid && ready"


def test_safe_expr_accepts_comparison():
    assert safe_expr("count == 0") == "count == 0"


def test_safe_expr_rejects_semicolon():
    with pytest.raises(RenderError):
        safe_expr("a; b")


def test_safe_expr_rejects_system_task():
    with pytest.raises(RenderError):
        safe_expr("$display(a)")


def test_safe_expr_rejects_empty():
    with pytest.raises(RenderError):
        safe_expr("   ")


# --- clock / timing safety ----------------------------------------------
def test_render_rejects_absent_clock():
    i = _intent(clock_signal=None, consequent="a")
    with pytest.raises(RenderError):
        render(i)


def test_bounded_response_fixed_delay_uses_hashN():
    # min == max renders as ##N (no range brackets).
    i = _intent(
        property_form=PropertyForm.BOUNDED_RESPONSE,
        render_template_id="bounded_response",
        antecedent="a",
        consequent="b",
        min_delay=2,
        max_delay=2,
    )
    out = render(i)
    assert "##2" in out and "##[" not in out


# --- overlapping vs non-overlapping -------------------------------------
def test_implication_overlapping_uses_pipe_arrow():
    i = _intent(
        property_form=PropertyForm.IMPLICATION,
        render_template_id="implication",
        antecedent="a",
        consequent="b",
        implication_style=ImplicationStyle.OVERLAPPING,
    )
    assert "|->" in render(i)


def test_next_cycle_uses_non_overlapping():
    i = _intent(
        property_form=PropertyForm.NEXT_CYCLE,
        render_template_id="next_cycle",
        antecedent="a",
        consequent="b",
    )
    assert "|=>" in render(i)


def test_bounded_response_renders_range():
    i = _intent(
        property_form=PropertyForm.BOUNDED_RESPONSE,
        render_template_id="bounded_response",
        antecedent="a",
        consequent="b",
        min_delay=1,
        max_delay=3,
    )
    assert "##[1:3]" in render(i)


def test_bounded_response_requires_bounds():
    i = _intent(
        property_form=PropertyForm.BOUNDED_RESPONSE,
        render_template_id="bounded_response",
        antecedent="a",
        consequent="b",
    )
    with pytest.raises(RenderError):
        render(i)


# --- disable iff --------------------------------------------------------
def test_disable_iff_active_low():
    i = _intent(
        property_form=PropertyForm.IMPLICATION,
        render_template_id="implication",
        antecedent="a",
        consequent="b",
        reset_signal="rst_n",
        reset_polarity=ResetPolarity.ACTIVE_LOW,
    )
    assert "disable iff (!rst_n)" in render(i)


def test_disable_iff_omitted_when_polarity_unknown():
    i = _intent(
        property_form=PropertyForm.IMPLICATION,
        render_template_id="implication",
        antecedent="a",
        consequent="b",
        reset_signal="rst",
        reset_polarity=ResetPolarity.UNKNOWN,
    )
    assert "disable iff" not in render(i)


# --- reset_state safety -------------------------------------------------
def test_reset_state_rejects_unknown_polarity():
    i = _intent(
        property_form=PropertyForm.RESET_STATE,
        render_template_id="reset_state",
        consequent="count == 0",
        reset_signal="rst_n",
        reset_polarity=ResetPolarity.UNKNOWN,
    )
    with pytest.raises(RenderError):
        render(i)


def test_one_hot_renders_onehot():
    i = _intent(
        property_form=PropertyForm.ONE_HOT,
        render_template_id="one_hot",
        consequent="state",
    )
    assert "$onehot(state)" in render(i)


def test_render_property_names_and_directive():
    i = _intent(consequent="a")
    cp = render_property(i)
    assert cp.property_name.startswith("p_")
    assert "assert property" in cp.sva_text
    assert cp.status == "candidate_compiled_offline"


def test_cover_directive():
    i = _intent(
        property_kind=PropertyKind.COVER,
        property_form=PropertyForm.EVENTUALLY_WITHIN_BOUND,
        render_template_id="eventually_within_bound",
        consequent="done",
        max_delay=4,
    )
    cp = render_property(i)
    assert "cover property" in cp.sva_text
