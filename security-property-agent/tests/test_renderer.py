from __future__ import annotations

import pytest

from security_property_agent import renderer
from security_property_agent.renderer import RenderError, safe_expr


def test_safe_expr_accepts_whitelisted():
    assert safe_expr("a && (b == 1'b1)") == "a && (b == 1'b1)"
    assert safe_expr("core_a_result != core_b_result")


@pytest.mark.parametrize(
    "bad",
    [
        "a; $display(a)",
        "`MACRO",
        "a // comment",
        "assert x",
        "a / b",  # division is not whitelisted
        "",
    ],
)
def test_safe_expr_rejects_unsafe(bad):
    with pytest.raises(RenderError):
        safe_expr(bad)


def test_clocking_includes_disable_iff():
    out = renderer.clocking("clk", "rst")
    assert "@(posedge clk)" in out
    assert "disable iff (rst)" in out


def test_render_bounded_response_rejects_bad_bounds():
    with pytest.raises(RenderError):
        renderer.render_bounded_response("p", "clk", None, "a", "b", 3, 1)


def test_render_implication_shape():
    out = renderer.render_implication("p", "clk", "rst", "a", "b", next_cycle=False)
    assert "|->" in out and "assert property" in out
    out2 = renderer.render_implication("p", "clk", "rst", "a", "b", next_cycle=True)
    assert "|=>" in out2


def test_render_never_negates():
    out = renderer.render_never("p", "clk", None, "dbg_enable")
    assert "!(dbg_enable)" in out
