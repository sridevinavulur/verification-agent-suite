"""Verification Knowledge Graph (vkg).

A lightweight, SQLite-backed knowledge graph over verification artifacts:
requirements, modules, interfaces, signals, reset domains, assertions, tests,
coverage bins, regressions, failures, waivers, bugs, and evidence claims.

See ``vkg.models`` for the typed node/edge schema, ``vkg.importers`` for the
five artifact importers, ``vkg.queries`` for the working queries, and
``vkg.export`` for JSON / Graphviz DOT output.
"""

from .models import GRAPH_SCHEMA_VERSION

__all__ = ["GRAPH_SCHEMA_VERSION"]
__version__ = GRAPH_SCHEMA_VERSION
