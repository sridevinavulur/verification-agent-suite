"""Build a :class:`DependencyGraph` from parsed RTL or an RTL Intent Manifest.

Two entry points:

* :func:`build_from_parse` - from the constrained Verilog parser output.
* :func:`build_from_manifest` - from an RTL Intent Manifest JSON (the contract
  emitted by ``rtl-intent-ingestor``). Only the fields we need are read; unknown
  fields are ignored so we stay forward-compatible.

Both produce a graph with **stable node IDs** (dense 0..N-1, first-seen order)
and edges pointing from a signal to its drivers (fan-in). Multi-module designs
are flattened using instance connection maps; the top module's signals are the
roots. Undefined child modules become BLACKBOX output nodes with an explicit
soundness note (their internal dependencies are unknown, so the COI treats their
outputs as free inputs - a sound over-approximation).
"""

from __future__ import annotations

from .models import (
    DependencyGraph,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
    SourceLocation,
)
from .verilog_parser import ParsedModule, ParseResult


class _Builder:
    def __init__(self, top: str, file: str) -> None:
        self.top = top
        self.file = file
        self._nodes: list[GraphNode] = []
        self._id: dict[str, int] = {}
        self._edges: list[tuple[int, int, EdgeKind]] = []
        self._edge_seen: set[tuple[int, int, EdgeKind]] = set()

    def node(
        self,
        name: str,
        kind: NodeKind,
        module: str,
        *,
        line: int | None = None,
        clock_domain: str | None = None,
        reset_domain: str | None = None,
    ) -> int:
        if name in self._id:
            nid = self._id[name]
            # Upgrade kind if we learn it is a register/port (more specific).
            node = self._nodes[nid]
            if node.kind == NodeKind.NET and kind in (
                NodeKind.REG,
                NodeKind.PORT_IN,
                NodeKind.PORT_OUT,
                NodeKind.CLOCK,
                NodeKind.RESET,
                NodeKind.BLACKBOX,
            ):
                node.kind = kind
            if clock_domain and not node.clock_domain:
                node.clock_domain = clock_domain
            if reset_domain and not node.reset_domain:
                node.reset_domain = reset_domain
            return nid
        nid = len(self._nodes)
        self._id[name] = nid
        loc = SourceLocation(file=self.file, line=line) if line else None
        self._nodes.append(
            GraphNode(
                node_id=nid,
                name=name,
                kind=kind,
                module=module,
                clock_domain=clock_domain,
                reset_domain=reset_domain,
                location=loc,
            )
        )
        return nid

    def edge(self, src: int, dst: int, kind: EdgeKind) -> None:
        if src == dst and kind in (EdgeKind.CLOCK, EdgeKind.RESET):
            return
        key = (src, dst, kind)
        if key in self._edge_seen:
            return
        self._edge_seen.add(key)
        self._edges.append(key)

    def finish(self) -> DependencyGraph:
        edges = [GraphEdge(src=s, dst=d, kind=k) for (s, d, k) in self._edges]
        return DependencyGraph(top=self.top, nodes=list(self._nodes), edges=edges)


def build_from_parse(parse: ParseResult, top: str | None = None) -> DependencyGraph:
    """Build a graph from parsed Verilog (single-module or flattened top)."""
    if not parse.modules:
        raise ValueError("no modules parsed")
    module_by_name = {m.name: m for m in parse.modules}
    top_name = top or parse.modules[0].name
    if top_name not in module_by_name:
        raise ValueError(f"top module {top_name!r} not found")

    b = _Builder(top=top_name, file=parse.file)
    _emit_module(b, module_by_name[top_name], module_by_name, prefix=top_name)
    return b.finish()


def _classify_control(name: str) -> NodeKind | None:
    import re

    if re.search(r"clk|clock", name, re.I):
        return NodeKind.CLOCK
    if re.search(r"rst|reset|clr\b|clear", name, re.I):
        return NodeKind.RESET
    return None


def _emit_module(
    b: _Builder,
    mod: ParsedModule,
    module_by_name: dict[str, ParsedModule],
    prefix: str,
) -> None:
    """Emit nodes/edges for one module. Instances are recursively flattened.

    ``prefix`` is the hierarchical scope for signal names in this instance.
    """
    reg_names: set[str] = set()
    for proc in mod.procedures:
        if proc.is_sequential:
            for a in proc.assigns:
                reg_names.add(a.lhs)

    def qname(local: str) -> str:
        return f"{prefix}.{local}"

    # Declare ports.
    port_dir = {p.name: p.direction for p in mod.ports}
    for p in mod.ports:
        ctrl = _classify_control(p.name)
        if p.direction == "input":
            kind = ctrl or NodeKind.PORT_IN
        elif p.direction == "output":
            kind = NodeKind.PORT_OUT
        else:
            kind = NodeKind.PORT_IN
        b.node(qname(p.name), kind, mod.name, line=p.line)

    # Declare nets/regs.
    for net in mod.nets:
        kind = NodeKind.REG if net.name in reg_names else NodeKind.NET
        b.node(qname(net.name), kind, mod.name, line=net.line)

    # Continuous assigns -> comb edges lhs depends on each rhs signal.
    for ca in mod.assigns:
        lhs_id = b.node(qname(ca.lhs), NodeKind.NET, mod.name, line=ca.line)
        for rhs in ca.rhs_signals:
            dst = b.node(qname(rhs), NodeKind.NET, mod.name, line=ca.line)
            b.edge(lhs_id, dst, EdgeKind.COMB)

    # Procedures.
    for proc in mod.procedures:
        clk_id = None
        rst_id = None
        clk_dom = None
        rst_dom = None
        if proc.clock:
            clk_id = b.node(qname(proc.clock), NodeKind.CLOCK, mod.name)
            clk_dom = qname(proc.clock)
        if proc.reset:
            rst_id = b.node(qname(proc.reset), NodeKind.RESET, mod.name)
            rst_dom = qname(proc.reset)
        for pa in proc.assigns:
            kind = NodeKind.REG if proc.is_sequential else NodeKind.NET
            lhs_id = b.node(
                qname(pa.lhs),
                kind,
                mod.name,
                line=pa.line,
                clock_domain=clk_dom if proc.is_sequential else None,
                reset_domain=rst_dom if proc.is_sequential else None,
            )
            edge_kind = EdgeKind.SEQ if proc.is_sequential else EdgeKind.COMB
            for rhs in pa.rhs_signals:
                if rhs == proc.clock or rhs == proc.reset:
                    continue
                dst = b.node(qname(rhs), NodeKind.NET, mod.name, line=pa.line)
                b.edge(lhs_id, dst, edge_kind)
            if proc.is_sequential and clk_id is not None:
                b.edge(lhs_id, clk_id, EdgeKind.CLOCK)
            if proc.is_sequential and rst_id is not None:
                b.edge(lhs_id, rst_id, EdgeKind.RESET)

    # Instances: flatten or blackbox.
    for inst in mod.instances:
        child = module_by_name.get(inst.module)
        child_prefix = f"{prefix}.{inst.name}"
        if child is None:
            # Black-box: connect this scope's actuals to blackbox pins. Outputs
            # of the child are free (undriven inside), inputs depend on actuals.
            _emit_blackbox(b, inst, mod, prefix, child_prefix)
            continue
        # Recurse to emit the child's internals under child_prefix.
        _emit_module(b, child, module_by_name, prefix=child_prefix)
        _wire_instance(b, inst, child, mod, prefix, child_prefix, port_dir)


def _emit_blackbox(b, inst, mod, prefix, child_prefix) -> None:
    for formal, actual in inst.connections:
        pin = f"{child_prefix}.{formal or 'pos'}"
        pin_id = b.node(pin, NodeKind.BLACKBOX, inst.module)
        act_id = b.node(f"{prefix}.{actual}", NodeKind.NET, mod.name)
        # Conservatively add a HIER dependency both ways is unsound for outputs;
        # instead the actual (outside signal) depends on the blackbox pin.
        b.edge(act_id, pin_id, EdgeKind.HIER)


def _wire_instance(b, inst, child, mod, prefix, child_prefix, port_dir) -> None:
    child_dir = {p.name: p.direction for p in child.ports}
    for formal, actual in inst.connections:
        if formal is None:
            continue
        outer = f"{prefix}.{actual}"
        inner = f"{child_prefix}.{formal}"
        outer_id = b.node(outer, NodeKind.NET, mod.name)
        inner_id = b.node(inner, NodeKind.NET, child.name)
        direction = child_dir.get(formal, "input")
        if direction == "output":
            # outer signal is driven by the child's inner output.
            b.edge(outer_id, inner_id, EdgeKind.HIER)
        else:
            # inner input driven by outer actual.
            b.edge(inner_id, outer_id, EdgeKind.HIER)


# --------------------------------------------------------------------------- #
# Manifest ingestion
# --------------------------------------------------------------------------- #


def build_from_manifest(manifest: dict, top: str | None = None) -> DependencyGraph:
    """Build a graph from an RTL Intent Manifest dict.

    Reads modules[].ports/nets/registers/continuous_assigns/procedures and
    hierarchy. RHS identifiers are extracted lexically from assign/assignment
    ``rhs`` strings (over-approximating, hence sound).
    """
    from .verilog_parser import _rhs_identifiers

    modules = {m["name"]: m for m in manifest.get("modules", [])}
    if not modules:
        raise ValueError("manifest has no modules")
    top_name = top or manifest.get("top") or next(iter(modules))
    if top_name not in modules:
        raise ValueError(f"top module {top_name!r} not in manifest")

    # Convert manifest modules into ParsedModule-like structures and reuse the
    # parse-based builder for a single code path.
    parsed_modules: list[ParsedModule] = []
    for name, m in modules.items():
        pm = ParsedModule(name=name, line=_loc_line(m.get("location")))
        from .verilog_parser import (
            ParsedAssign,
            ParsedNet,
            ParsedPort,
            ParsedProcAssign,
            ParsedProcedure,
        )

        for p in m.get("ports", []):
            pm.ports.append(
                ParsedPort(p["name"], p["direction"], _loc_line(p.get("location")))
            )
        reg_targets = {r["name"] for r in m.get("registers", [])}
        for net in m.get("nets", []):
            pm.nets.append(
                ParsedNet(net["name"], net["net_kind"], _loc_line(net.get("location")))
            )
        for rname in reg_targets:
            if not any(n.name == rname for n in pm.nets):
                pm.nets.append(ParsedNet(rname, "reg", 1))
        for ca in m.get("continuous_assigns", []):
            pm.assigns.append(
                ParsedAssign(
                    _base(ca["lhs"]),
                    _rhs_identifiers(ca["rhs"]),
                    _loc_line(ca.get("location")),
                )
            )
        for proc in m.get("procedures", []):
            is_seq = proc.get("kind") == "always_ff"
            clock = None
            reset = None
            for s in proc.get("sensitivity", []):
                if s.get("edge") in ("posedge", "negedge"):
                    if clock is None:
                        clock = s["signal"]
                    elif reset is None:
                        reset = s["signal"]
            passigns: list[ParsedProcAssign] = []
            for a in proc.get("assignments", []):
                passigns.append(
                    ParsedProcAssign(
                        _base(a["lhs"]),
                        _rhs_identifiers(a["rhs"]),
                        a.get("nonblocking", is_seq),
                        _loc_line(a.get("location")),
                    )
                )
            pm.procedures.append(
                ParsedProcedure(
                    is_sequential=is_seq,
                    clock=clock,
                    reset=reset,
                    reset_edge=None,
                    assigns=passigns,
                    line=_loc_line(proc.get("location")),
                )
            )
        from .verilog_parser import ParsedInstance

        for inst in m.get("instances", []):
            conns = [
                (c.get("formal"), _base(c["actual"]))
                for c in inst.get("connections", [])
            ]
            pm.instances.append(
                ParsedInstance(
                    inst["module"],
                    inst["name"],
                    conns,
                    _loc_line(inst.get("location")),
                )
            )
        parsed_modules.append(pm)

    file = manifest.get("provenance", {}).get("input_files", ["<manifest>"])
    result = ParseResult(
        modules=parsed_modules, file=file[0] if file else "<manifest>"
    )
    return build_from_parse(result, top=top_name)


def _loc_line(loc: dict | None) -> int:
    if loc and isinstance(loc, dict):
        return int(loc.get("line", 1))
    return 1


def _base(name: str) -> str:
    from .verilog_parser import _base_name

    return _base_name(name)
