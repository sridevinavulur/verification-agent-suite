"""Tests for the heuristic clock/reset detection."""

from __future__ import annotations

from rtl_intent.manifest import build_manifest_from_texts
from rtl_intent.models import ResetPolarity, ResetSync


def _module(text: str):
    return build_manifest_from_texts({"t.sv": text}).modules[0]


def test_async_active_low_reset() -> None:
    m = _module(
        """
        module m (input clk, input rst_n, output reg q);
            always @(posedge clk or negedge rst_n)
                if (!rst_n) q <= 0; else q <= 1;
        endmodule
        """
    )
    clk = next(c for c in m.clock_candidates if c.signal == "clk")
    assert clk.confidence >= 0.9
    rst = next(r for r in m.reset_candidates if r.signal == "rst_n")
    assert rst.polarity == ResetPolarity.ACTIVE_LOW
    assert rst.sync == ResetSync.ASYNCHRONOUS
    assert rst.confidence > 0.5


def test_sync_active_high_reset() -> None:
    m = _module(
        """
        module m (input clk, input rst, output reg q);
            always @(posedge clk)
                if (rst) q <= 0; else q <= 1;
        endmodule
        """
    )
    rst = next(r for r in m.reset_candidates if r.signal == "rst")
    assert rst.sync == ResetSync.SYNCHRONOUS
    # 'rst' is not used in the sensitivity list => not asynchronous.
    clk = next(c for c in m.clock_candidates if c.signal == "clk")
    assert clk.confidence >= 0.9


def test_clock_top_candidate_is_edge_signal() -> None:
    m = _module(
        """
        module m (input clk, input data, output reg q);
            always @(posedge clk) q <= data;
        endmodule
        """
    )
    assert m.clock_candidates[0].signal == "clk"
    assert m.clock_candidates[0].confidence >= 0.6
    assert m.clock_candidates[0].rationale  # non-empty rationale


def test_no_clock_reset_when_absent() -> None:
    m = _module(
        """
        module comb (input a, input b, output y);
            assign y = a & b;
        endmodule
        """
    )
    assert m.clock_candidates == []
    assert m.reset_candidates == []


def test_confidence_bounded() -> None:
    m = _module(
        """
        module m (input clk, input rst_n, output reg q);
            always @(posedge clk or negedge rst_n) q <= 0;
        endmodule
        """
    )
    for c in [*m.clock_candidates, *m.reset_candidates]:
        assert 0.0 <= c.confidence <= 1.0
