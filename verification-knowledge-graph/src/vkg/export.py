"""Exporters: JSON and Graphviz DOT.

Both exporters are deterministic (sorted node/edge order) so output diffs
cleanly and golden tests are stable.
"""

from __future__ import annotations

from .graph import Graph
from .models import NodeType

# Per-node-type styling for readable DOT output.
_NODE_STYLE: dict[NodeType, tuple[str, str]] = {
    NodeType.REQUIREMENT: ("box", "#cfe8ff"),
    NodeType.MODULE: ("box3d", "#d9ffd9"),
    NodeType.INTERFACE: ("component", "#e6ffe6"),
    NodeType.SIGNAL: ("ellipse", "#f0f0f0"),
    NodeType.RESET_DOMAIN: ("diamond", "#ffe0b3"),
    NodeType.ASSERTION: ("hexagon", "#fff2b3"),
    NodeType.TEST: ("box", "#e0ccff"),
    NodeType.COVERAGE_BIN: ("ellipse", "#ffd9d9"),
    NodeType.REGRESSION: ("folder", "#d9d9d9"),
    NodeType.FAILURE: ("octagon", "#ffb3b3"),
    NodeType.WAIVER: ("note", "#f5f5dc"),
    NodeType.BUG: ("octagon", "#ff9999"),
    NodeType.EVIDENCE_CLAIM: ("note", "#cceeff"),
    NodeType.BENCHMARK: ("cylinder", "#ccffe6"),
}


def to_json(g: Graph, indent: int = 2) -> str:
    """Serialize the whole graph to the JSON export contract."""
    return g.to_export().model_dump_json(indent=indent)


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(g: Graph) -> str:
    """Render the graph as Graphviz DOT.

    Nodes are labelled ``name`` and colored/shaped by type; edges are labelled
    by their edge type. Output ordering is deterministic.
    """
    lines: list[str] = ["digraph verification_knowledge_graph {"]
    lines.append("  rankdir=LR;")
    lines.append('  node [style=filled, fontname="Helvetica"];')
    lines.append('  edge [fontname="Helvetica", fontsize=10];')

    for node in g.nodes():
        shape, fill = _NODE_STYLE.get(node.type, ("box", "#ffffff"))
        label = f"{_dot_escape(node.name)}\\n({node.type.value})"
        extra = ""
        if node.type == NodeType.COVERAGE_BIN and node.attrs.get("hole") == "true":
            extra = ', penwidth=2, color="red"'
        elif node.type == NodeType.FAILURE:
            extra = ', penwidth=2, color="red"'
        lines.append(
            f'  "{node.id}" [label="{label}", shape={shape}, '
            f'fillcolor="{fill}"{extra}];'
        )

    for edge in g.edges():
        lines.append(
            f'  "{edge.src}" -> "{edge.dst}" [label="{edge.type.value}"];'
        )

    lines.append("}")
    return "\n".join(lines) + "\n"
