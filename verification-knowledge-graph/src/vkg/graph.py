"""In-memory + SQLite-backed storage for the Verification Knowledge Graph.

Design choice (per spec 6.12): lightweight local storage using plain SQLite
tables. No heavy graph-DB dependency. Two tables -- ``nodes`` and ``edges`` --
store the typed schema; ``attrs`` and ``provenance`` are stored as JSON blobs
in TEXT columns. Traversal is done in Python over adjacency indexes built from
the tables, which is more than adequate for verification-artifact scale.

Upserts are idempotent: re-importing the same artifact overwrites the same
rows by primary key (the stable node/edge ID), so imports are repeatable.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .models import (
    GRAPH_SCHEMA_VERSION,
    Edge,
    EdgeType,
    GraphExport,
    Node,
    NodeType,
    SourceProvenance,
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    attrs       TEXT NOT NULL,   -- JSON object
    provenance  TEXT NOT NULL    -- JSON object
);
CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    attrs       TEXT NOT NULL,   -- JSON object
    provenance  TEXT NOT NULL    -- JSON object
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
CREATE INDEX IF NOT EXISTS idx_edges_src  ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON edges(dst);
"""


class Graph:
    """A verification knowledge graph persisted in SQLite.

    Use ``Graph(":memory:")`` for tests or ``Graph("kg.db")`` on disk.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA_SQL)
        self.conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("schema_version", GRAPH_SCHEMA_VERSION),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #
    def add_node(self, node: Node) -> None:
        """Idempotent upsert of a node by its stable ID."""
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes(id, type, name, attrs, provenance) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                node.id,
                node.type.value,
                node.name,
                json.dumps(node.attrs, sort_keys=True),
                node.provenance.model_dump_json(),
            ),
        )

    def add_edge(self, edge: Edge) -> None:
        """Idempotent upsert of an edge by its stable ID."""
        self.conn.execute(
            "INSERT OR REPLACE INTO edges(id, type, src, dst, attrs, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                edge.id,
                edge.type.value,
                edge.src,
                edge.dst,
                json.dumps(edge.attrs, sort_keys=True),
                edge.provenance.model_dump_json(),
            ),
        )

    def commit(self) -> None:
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node(
            id=row["id"],
            type=NodeType(row["type"]),
            name=row["name"],
            attrs=json.loads(row["attrs"]),
            provenance=SourceProvenance.model_validate_json(row["provenance"]),
        )

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge(
            id=row["id"],
            type=EdgeType(row["type"]),
            src=row["src"],
            dst=row["dst"],
            attrs=json.loads(row["attrs"]),
            provenance=SourceProvenance.model_validate_json(row["provenance"]),
        )

    def get_node(self, node_id: str) -> Node | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return self._row_to_node(row) if row else None

    def nodes(self, node_type: NodeType | None = None) -> list[Node]:
        if node_type is None:
            rows = self.conn.execute(
                "SELECT * FROM nodes ORDER BY id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE type = ? ORDER BY id",
                (node_type.value,),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def edges(self, edge_type: EdgeType | None = None) -> list[Edge]:
        if edge_type is None:
            rows = self.conn.execute(
                "SELECT * FROM edges ORDER BY id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE type = ? ORDER BY id",
                (edge_type.value,),
            ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Adjacency (built on demand from the tables)
    # ------------------------------------------------------------------ #
    def out_edges(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        if edge_type is None:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE src = ? ORDER BY id", (node_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE src = ? AND type = ? ORDER BY id",
                (node_id, edge_type.value),
            ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def in_edges(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        if edge_type is None:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE dst = ? ORDER BY id", (node_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE dst = ? AND type = ? ORDER BY id",
                (node_id, edge_type.value),
            ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def adjacency(self) -> dict[str, list[Edge]]:
        """Full src -> [edges] adjacency map (used by traversals/exporters)."""
        adj: dict[str, list[Edge]] = defaultdict(list)
        for e in self.edges():
            adj[e.src].append(e)
        return adj

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def to_export(self) -> GraphExport:
        return GraphExport(nodes=self.nodes(), edges=self.edges())

    def stats(self) -> dict[str, int]:
        """Counts by node type and edge type, plus totals."""
        out: dict[str, int] = {}
        for nt in NodeType:
            n = self.conn.execute(
                "SELECT COUNT(*) AS c FROM nodes WHERE type = ?", (nt.value,)
            ).fetchone()["c"]
            if n:
                out[f"node:{nt.value}"] = n
        for et in EdgeType:
            n = self.conn.execute(
                "SELECT COUNT(*) AS c FROM edges WHERE type = ?", (et.value,)
            ).fetchone()["c"]
            if n:
                out[f"edge:{et.value}"] = n
        out["total_nodes"] = self.conn.execute(
            "SELECT COUNT(*) AS c FROM nodes"
        ).fetchone()["c"]
        out["total_edges"] = self.conn.execute(
            "SELECT COUNT(*) AS c FROM edges"
        ).fetchone()["c"]
        return out

    def close(self) -> None:
        self.conn.close()
