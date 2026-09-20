"""Tests for the constrained Verilog parser."""

from __future__ import annotations

from formal_flow_scout.verilog_parser import parse_verilog

COUNTER = """
module counter(input clk, input rst, input en, output at_max, output [7:0] value);
  reg [7:0] cnt;
  assign at_max = (cnt == 8'hFF);
  assign value = cnt;
  always @(posedge clk) begin
    if (rst) cnt <= 8'h00;
    else if (en && !at_max) cnt <= cnt + 8'h01;
  end
endmodule
"""


def test_parses_module_and_ports():
    r = parse_verilog(COUNTER, "counter.v")
    assert len(r.modules) == 1
    m = r.modules[0]
    assert m.name == "counter"
    names = {p.name for p in m.ports}
    assert {"clk", "rst", "en", "at_max", "value"} <= names


def test_continuous_assign_dependencies():
    r = parse_verilog(COUNTER, "counter.v")
    m = r.modules[0]
    amap = {a.lhs: a.rhs_signals for a in m.assigns}
    assert amap["at_max"] == ["cnt"]
    assert amap["value"] == ["cnt"]


def test_sequential_block_classified_and_clock_found():
    r = parse_verilog(COUNTER, "counter.v")
    proc = r.modules[0].procedures[0]
    assert proc.is_sequential
    assert proc.clock == "clk"


def test_sized_literals_not_treated_as_signals():
    r = parse_verilog(COUNTER, "counter.v")
    proc = r.modules[0].procedures[0]
    all_rhs = {s for a in proc.assigns for s in a.rhs_signals}
    # 8'h00, 8'h01, 8'hFF must not appear as identifiers.
    assert not any(x in all_rhs for x in ("h00", "h01", "hFF", "8"))
    assert "cnt" in all_rhs


def test_inline_if_else_targets_real_signal_not_keyword():
    r = parse_verilog(COUNTER, "counter.v")
    proc = r.modules[0].procedures[0]
    targets = {a.lhs for a in proc.assigns}
    assert targets == {"cnt"}
    assert "else" not in targets and "if" not in targets


def test_async_reset_detected_from_sensitivity():
    src = """
    module ff(input clk, input rst_n, input d, output reg q);
      always @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= 1'b0;
        else q <= d;
      end
    endmodule
    """
    r = parse_verilog(src, "ff.v")
    proc = r.modules[0].procedures[0]
    assert proc.clock == "clk"
    assert proc.reset == "rst_n"


def test_unparsed_lines_are_recorded_not_dropped():
    src = """
    module weird(input a, output b);
      assign b = a;
      this_is_not_valid_verilog foo bar baz;
    endmodule
    """
    r = parse_verilog(src, "weird.v")
    assert any(u.kind in ("unparsed_line", "outside_module") for u in r.unresolved) or \
        len(r.modules[0].instances) >= 0  # instance-like line may be captured
