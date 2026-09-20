from reset_intent_agent.rtl_parser import _is_constant, looks_like_reset_name, parse_text


def test_parses_module_and_ports():
    src = """
    module m(input wire clk, input wire rst_n, output reg [7:0] q);
    endmodule
    """
    mods = parse_text(src, "m.sv")
    assert len(mods) == 1
    assert mods[0].name == "m"
    names = {p.name for p in mods[0].ports}
    assert {"clk", "rst_n", "q"} <= names


def test_no_module_reported_unsupported():
    mods = parse_text("wire x;", "x.sv")
    assert mods[0].unsupported
    assert mods[0].unsupported[0].kind == "no_module"


def test_async_edge_sensitivity_detected():
    src = """
    module m(input clk, input rst_n, output reg q);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 1'b0;
        else q <= 1'b1;
    endmodule
    """
    blk = parse_text(src, "m.sv")[0].always_blocks[0]
    assert blk.is_edge_sensitive
    edges = {(s.signal, s.edge) for s in blk.sensitivity}
    assert ("clk", "posedge") in edges
    assert ("rst_n", "negedge") in edges


def test_reset_branch_only_constants_attributed():
    # 'else if (en)' must NOT be treated as a reset guard, and the increment
    # (non-constant) must NOT be attributed as a reset value.
    src = """
    module m(input clk, input rst_n, input en, output reg [7:0] c);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) c <= 8'b0;
        else if (en) c <= c + 1'b1;
    endmodule
    """
    blk = parse_text(src, "m.sv")[0].always_blocks[0]
    reset_assigns = [a for a in blk.assigns if a.under_reset]
    assert len(reset_assigns) == 1
    assert reset_assigns[0].lhs == "c"
    assert reset_assigns[0].rhs == "8'b0"
    assert reset_assigns[0].reset_signal == "rst_n"


def test_begin_end_reset_branch_multiple_regs():
    src = """
    module m(input clk, input rst, output reg a, output reg b);
      always @(posedge clk) begin
        if (rst) begin
          a <= 1'b0;
          b <= 1'b0;
        end else begin
          a <= 1'b1;
          b <= 1'b1;
        end
      end
    endmodule
    """
    blk = parse_text(src, "m.sv")[0].always_blocks[0]
    reset_lhs = {a.lhs for a in blk.assigns if a.under_reset}
    assert reset_lhs == {"a", "b"}


def test_comment_stripping_preserves_offsets():
    src = "module m(input clk); // a reset comment rst_n\n endmodule"
    mods = parse_text(src, "m.sv")
    # 'rst_n' inside a comment must not become a port
    assert all(p.name != "rst_n" for p in mods[0].ports)


def test_is_constant():
    assert _is_constant("8'b0")
    assert _is_constant("4'd0")
    assert _is_constant("0")
    assert not _is_constant("c + 1")
    assert not _is_constant("din")


def test_reset_name_heuristic():
    assert looks_like_reset_name("rst_n")
    assert looks_like_reset_name("reset")
    assert looks_like_reset_name("arst_n")
    assert not looks_like_reset_name("data")
    assert not looks_like_reset_name("clk")
