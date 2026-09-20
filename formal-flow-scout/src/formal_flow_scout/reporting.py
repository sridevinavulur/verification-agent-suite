"""Deterministic Graphviz DOT and text summary emitters for a CoiReport."""

from __future__ import annotations

from .graph_core import PackedGraph
from .models import CoiReport, EdgeKind, NodeKind

_KIND_STYLE = {
    NodeKind.REG: ("box", "lightblue"),
    NodeKind.NET: ("ellipse", "white"),
    NodeKind.PORT_IN: ("invhouse", "palegreen"),
    NodeKind.PORT_OUT: ("house", "palegreen"),
    NodeKind.CLOCK: ("diamond", "khaki"),
    NodeKind.RESET: ("diamond", "salmon"),
    NodeKind.CONST: ("plaintext", "white"),
    NodeKind.BLACKBOX: ("box3d", "orange"),
}

_EDGE_STYLE = {
    EdgeKind.COMB: ("solid", "black"),
    EdgeKind.SEQ: ("bold", "blue"),
    EdgeKind.CLOCK: ("dashed", "goldenrod"),
    EdgeKind.RESET: ("dashed", "red"),
    EdgeKind.HIER: ("dotted", "gray"),
}


def to_dot(report: CoiReport, pg: PackedGraph, *, coi_only: bool = True) -> str:
    """Emit Graphviz DOT. COI nodes are highlighted; seeds are bold.

    Output is fully deterministic (nodes/edges in ascending id order).
    """
    coi = set(report.coi_node_ids)
    seeds = set(report.seed_node_ids)
    lines: list[str] = []
    lines.append("digraph coi {")
    lines.append("  rankdir=RL;  // fan-in points right-to-left")
    lines.append('  node [fontname="Helvetica", fontsize=10];')
    lines.append('  edge [fontname="Helvetica", fontsize=8];')
    lines.append(f'  label="COI: {report.property_name}  (top={report.top})";')

    show = sorted(coi) if coi_only else range(pg.n)
    show_set = set(show)
    for nid in show:
        node = pg.nodes[nid]
        shape, fill = _KIND_STYLE.get(node.kind, ("ellipse", "white"))
        penwidth = "3" if nid in seeds else "1"
        style = "filled"
        color = "red" if nid in seeds else "black"
        label = node.name.replace('"', "'")
        lines.append(
            f'  n{nid} [label="{label}", shape={shape}, style={style}, '
            f'fillcolor={fill}, color={color}, penwidth={penwidth}];'
        )
    for nid in show:
        for dst, kind in pg.neighbours(nid):
            if coi_only and dst not in show_set:
                continue
            style, ecolor = _EDGE_STYLE.get(kind, ("solid", "black"))
            lines.append(
                f'  n{nid} -> n{dst} [style={style}, color={ecolor}, '
                f'label="{kind.value}"];'
            )
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_text_summary(report: CoiReport) -> str:
    s = report.stats
    lines: list[str] = []
    lines.append(f"FormalFlow-Scout COI report: property '{report.property_name}'")
    lines.append(f"  top module          : {report.top}")
    lines.append(f"  graph core          : {report.provenance.graph_core}")
    lines.append(f"  seeds resolved      : {len(report.seed_node_ids)}"
                 f" / {s.seed_signals}")
    if report.unresolved_seed_signals:
        lines.append(f"  UNRESOLVED seeds    : {report.unresolved_seed_signals}")
    lines.append(f"  total nodes / edges : {s.total_nodes} / {s.total_edges}")
    lines.append(f"  COI nodes           : {s.coi_nodes}"
                 f" (reg={s.coi_registers}, comb={s.coi_combinational})")
    lines.append(f"  excluded nodes      : {s.excluded_nodes}")
    lines.append(f"  SCCs (cyclic)       : {s.scc_count} ({s.cyclic_scc_count})"
                 f", largest={s.largest_scc_size}")
    lines.append(f"  clock domains       : {s.clock_domain_count}")
    lines.append(f"  reset domains       : {s.reset_domain_count}")
    lines.append("")
    lines.append(f"  candidate partitions: {len(report.candidate_partitions)} "
                 "(ALL HEURISTIC)")
    for p in report.candidate_partitions:
        lines.append(
            f"    - {p.partition_id} [{p.strategy}] "
            f"nodes={len(p.included_nodes)} cuts={len(p.cut_signals)} "
            f"state_bits={p.estimated_state_bits} soundness={p.soundness.value}"
        )
    if report.soundness_risks:
        lines.append("")
        lines.append("  SOUNDNESS RISKS:")
        for r in report.soundness_risks:
            lines.append(f"    [{r.severity.upper()}] {r.kind}: {r.detail}")
    lines.append("")
    for n in report.notes:
        lines.append(f"  NOTE: {n}")
    return "\n".join(lines) + "\n"
