"""Unit tests for the built-in parser on real Verilog fragments."""

from __future__ import annotations

from rtl_intent.adapters import BuiltinVerilogAdapter
from rtl_intent.manifest import build_manifest_from_texts
from rtl_intent.models import NetKind, PortDirection, ProcedureKind


def _parse(text: str):
    return BuiltinVerilogAdapter().parse_text(text, filename="t.sv")


def test_module_and_ansi_ports() -> None:
    res = _parse(
        """
        module m (
            input wire clk,
            input wire [7:0] d,
            output reg [7:0] q
        );
        endmodule
        """
    )
    assert len(res.modules) == 1
    m = res.modules[0]
    assert m.name == "m"
    assert [p.name for p in m.ports] == ["clk", "d", "q"]
    q = next(p for p in m.ports if p.name == "q")
    assert q.direction == PortDirection.OUTPUT
    assert q.net_kind == NetKind.REG
    assert q.range is not None and q.range.msb == "7" and q.range.lsb == "0"


def test_sticky_direction_in_port_list() -> None:
    res = _parse("module m (input wire a, b, c); endmodule")
    m = res.modules[0]
    assert [p.direction for p in m.ports] == [PortDirection.INPUT] * 3


def test_non_ansi_ports() -> None:
    res = _parse(
        """
        module m (a, b, y);
            input a;
            input b;
            output y;
            assign y = a & b;
        endmodule
        """
    )
    m = res.modules[0]
    dirs = {p.name: p.direction for p in m.ports}
    assert dirs == {
        "a": PortDirection.INPUT,
        "b": PortDirection.INPUT,
        "y": PortDirection.OUTPUT,
    }
    assert len(m.continuous_assigns) == 1
    assert m.continuous_assigns[0].lhs == "y"


def test_parameters_and_localparams() -> None:
    res = _parse(
        """
        module m #(parameter W = 8, parameter D = 16) ();
            localparam Z = W + D;
        endmodule
        """
    )
    m = res.modules[0]
    params = {p.name: (p.default, p.is_localparam) for p in m.parameters}
    assert params["W"] == ("8", False)
    assert params["D"] == ("16", False)
    assert params["Z"][1] is True


def test_always_ff_classification_and_registers() -> None:
    res = _parse(
        """
        module m (input clk, input rst_n, output reg [3:0] q);
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) q <= 4'd0;
                else q <= q + 1;
            end
        endmodule
        """
    )
    m = res.modules[0]
    assert len(m.procedures) == 1
    assert m.procedures[0].kind == ProcedureKind.ALWAYS_FF
    assert [r.name for r in m.registers] == ["q"]
    assert m.procedure_summary.always_ff == 1


def test_always_comb_star_and_explicit() -> None:
    res = _parse(
        """
        module m (input a, input b, output reg y, output reg z);
            always @* y = a & b;
            always_comb z = a | b;
        endmodule
        """
    )
    m = res.modules[0]
    kinds = [p.kind for p in m.procedures]
    assert kinds == [ProcedureKind.ALWAYS_COMB, ProcedureKind.ALWAYS_COMB]
    # Blocking assignments do not create registers.
    assert m.registers == []


def test_blocking_vs_nonblocking() -> None:
    res = _parse(
        """
        module m (input clk, output reg a, output reg b);
            always @(posedge clk) begin
                a = 1;
                b <= a;
            end
        endmodule
        """
    )
    proc = res.modules[0].procedures[0]
    by_lhs = {asg.lhs: asg.nonblocking for asg in proc.assignments}
    assert by_lhs == {"a": False, "b": True}
    # Only nonblocking targets under always_ff become registers.
    assert [r.name for r in res.modules[0].registers] == ["b"]


def test_instances_named_and_positional() -> None:
    res = _parse(
        """
        module child (input a, output b);
        endmodule
        module parent (input x, output y);
            child u0 (.a(x), .b(y));
            child u1 (x, y);
        endmodule
        """
    )
    parent = next(m for m in res.modules if m.name == "parent")
    assert [i.name for i in parent.instances] == ["u0", "u1"]
    u0 = parent.instances[0]
    assert u0.module == "child"
    assert [(c.formal, c.actual) for c in u0.connections] == [("a", "x"), ("b", "y")]
    u1 = parent.instances[1]
    assert [c.formal for c in u1.connections] == [None, None]
    assert [c.actual for c in u1.connections] == ["x", "y"]


def test_memory_array_net() -> None:
    res = _parse(
        """
        module m ();
            reg [7:0] mem [0:15];
        endmodule
        """
    )
    net = res.modules[0].nets[0]
    assert net.name == "mem"
    assert net.is_memory is True
    assert net.unpacked_range is not None
    assert net.unpacked_range.msb == "0" and net.unpacked_range.lsb == "15"
    assert res.modules[0]  # no crash


def test_source_locations_present() -> None:
    res = _parse("module m (input clk); endmodule")
    m = res.modules[0]
    assert m.location.line == 1
    assert m.ports[0].location.file == "t.sv"
    assert m.ports[0].location.line >= 1


def test_unsupported_construct_is_visible() -> None:
    res = _parse(
        """
        module m (input clk);
            function integer f; f = 1; endfunction
        endmodule
        """
    )
    assert any("function" in u.detail for u in res.unresolved)


def test_hierarchy_and_external_module() -> None:
    manifest = build_manifest_from_texts(
        {
            "t.sv": """
            module top (input clk);
                leaf u_leaf (.clk(clk));
                blackbox u_bb (.clk(clk));
            endmodule
            module leaf (input clk);
            endmodule
            """
        }
    )
    edges = {(e.instance_name, e.child_module, e.child_defined) for e in manifest.hierarchy}
    assert ("u_leaf", "leaf", True) in edges
    assert ("u_bb", "blackbox", False) in edges
    assert manifest.top == "top"
