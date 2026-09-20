"""Tests for JSON and Graphviz DOT export."""

from __future__ import annotations

import json

from vkg.export import to_dot, to_json
from vkg.graph import Graph
from vkg.models import GRAPH_SCHEMA_VERSION, GraphExport


def test_json_export_roundtrips(demo_graph: Graph):
    text = to_json(demo_graph)
    data = json.loads(text)
    assert data["schema_version"] == GRAPH_SCHEMA_VERSION
    export = GraphExport.model_validate(data)
    assert len(export.nodes) == demo_graph.stats()["total_nodes"]
    assert len(export.edges) == demo_graph.stats()["total_edges"]


def test_json_export_is_deterministic(demo_graph: Graph):
    assert to_json(demo_graph) == to_json(demo_graph)


def test_dot_export_wellformed(demo_graph: Graph):
    dot = to_dot(demo_graph)
    assert dot.startswith("digraph verification_knowledge_graph {")
    assert dot.rstrip().endswith("}")
    # every node id appears in the DOT
    for node in demo_graph.nodes():
        assert f'"{node.id}"' in dot
    # edges are rendered with labels
    assert "->" in dot
    assert "label=" in dot


def test_dot_marks_holes_and_failures_red(demo_graph: Graph):
    dot = to_dot(demo_graph)
    assert 'color="red"' in dot
