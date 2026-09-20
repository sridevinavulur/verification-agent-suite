"""Graphviz DOT emission for the reset graph.

Deterministic output ordering (nodes and edges in insertion order) so the DOT
is stable and diffable. Heuristic edges (reset-domain crossings) are drawn
dashed and red to make their status visible.
"""

from __future__ import annotations

from .models import ResetGraph

_SHAPE = {"reset": "doubleoctagon", "domain": "box", "register": "ellipse"}


def to_dot(graph: ResetGraph, name: str = "reset_graph") -> str:
    lines: list[str] = [f"digraph {name} {{", "  rankdir=LR;", '  node [fontname="monospace"];']
    for n in graph.nodes:
        shape = _SHAPE.get(n.kind, "ellipse")
        lines.append(f'  "{n.node_id}" [label="{n.label}", shape={shape}];')
    for e in graph.edges:
        if e.kind == "rdc":
            style = ' [style=dashed, color=red, label="RDC?"]'
        elif e.kind == "resets":
            style = ' [color=blue, label="resets"]'
        else:
            style = ' [label="member"]'
        lines.append(f'  "{e.src}" -> "{e.dst}"{style};')
    lines.append("}")
    return "\n".join(lines) + "\n"
