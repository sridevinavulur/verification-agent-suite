"""FormalFlow-Scout: RTL cone-of-influence and partition analysis.

Public API re-exports for programmatic use.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .analyzer import Analyzer
from .graph_builder import build_from_manifest, build_from_parse
from .graph_core import PackedGraph
from .models import (
    CoiReport,
    DependencyGraph,
    PropertySet,
    PropertySpec,
    Provenance,
)
from .verilog_parser import parse_verilog

__all__ = [
    "Analyzer",
    "CoiReport",
    "DependencyGraph",
    "PackedGraph",
    "PropertySet",
    "PropertySpec",
    "Provenance",
    "build_from_manifest",
    "build_from_parse",
    "parse_verilog",
    "__version__",
]
