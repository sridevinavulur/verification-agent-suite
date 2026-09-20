"""Safe SVA renderer tests."""

from __future__ import annotations

import pytest

from protocol_contract_agent import sva
from protocol_contract_agent.models import ResetPolarity


def test_safe_expr_accepts_basic():
    assert sva.safe_expr("count <= 16") == "count <= 16"
    assert sva.safe_expr("a && !b") == "a && !b"


@pytest.mark.parametrize("bad", [
    "a; b",            # statement terminator
    "$display(x)",     # system task
    "a // comment",    # comment
    "a`b",             # backtick / macro
    "",                # empty
    "a / b",           # division not allowed
])
def test_safe_expr_rejects_unsafe(bad):
    with pytest.raises(sva.RenderError):
        sva.safe_expr(bad)


def test_clocking_requires_clock():
    with pytest.raises(sva.RenderError):
        sva.clocking(None)
    assert sva.clocking("clk") == "@(posedge clk)"


def test_disable_iff_never_guesses_polarity():
    assert sva.disable_iff("rst_n", ResetPolarity.ACTIVE_LOW) == " disable iff (!rst_n)"
    assert sva.disable_iff("rst", ResetPolarity.ACTIVE_HIGH) == " disable iff (rst)"
    # unknown polarity -> no clause (do NOT guess)
    assert sva.disable_iff("rst", ResetPolarity.UNKNOWN) == ""
    assert sva.disable_iff(None, ResetPolarity.ACTIVE_LOW) == ""


def test_bounded_response_rejects_bad_range():
    with pytest.raises(sva.RenderError):
        sva.body_bounded_response("clk", "rst_n", ResetPolarity.ACTIVE_LOW,
                                  "a", "b", 3, 1)


def test_reset_state_rejects_unknown_polarity():
    with pytest.raises(sva.RenderError):
        sva.body_reset_state("clk", "rst", ResetPolarity.UNKNOWN, "x")


def test_bounded_response_single_delay_form():
    body = sva.body_bounded_response("clk", "rst_n", ResetPolarity.ACTIVE_LOW,
                                     "req", "gnt", 2, 2)
    assert "##2" in body and "##[" not in body
