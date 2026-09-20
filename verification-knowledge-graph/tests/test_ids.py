"""Tests for stable ID generation."""

from __future__ import annotations

import pytest

from vkg.ids import edge_id, node_id
from vkg.models import EdgeType, NodeType


def test_node_id_is_stable_and_deterministic():
    a = node_id(NodeType.MODULE, "fifo")
    b = node_id(NodeType.MODULE, "fifo")
    assert a == b
    assert a.startswith("mod:fifo:")


def test_node_id_normalizes_case_and_whitespace():
    assert node_id(NodeType.MODULE, "FIFO") == node_id(NodeType.MODULE, "  fifo ")


def test_node_id_distinguishes_type_and_key():
    assert node_id(NodeType.MODULE, "x") != node_id(NodeType.SIGNAL, "x")
    assert node_id(NodeType.INTERFACE, "fifo", "wr") != node_id(
        NodeType.INTERFACE, "fifo", "rd"
    )


def test_node_id_rejects_empty_key():
    with pytest.raises(ValueError):
        node_id(NodeType.MODULE, "")


def test_edge_id_is_stable():
    e1 = edge_id(EdgeType.ASSERTS, "a", "b")
    e2 = edge_id(EdgeType.ASSERTS, "a", "b")
    assert e1 == e2
    assert edge_id(EdgeType.ASSERTS, "a", "b") != edge_id(EdgeType.TESTS, "a", "b")
