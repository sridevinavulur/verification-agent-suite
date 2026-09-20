"""Formal Run Orchestrator.

Reproducible, provenance-tracked orchestration of formal-verification experiments on
public RTL/SVA. This package ships a deterministic planner, a MOCK executor (no real
formal tool), a result classifier with a fixed status vocabulary, a SQLite ledger, and
an offline, leakage-free policy-evaluation harness.

Authority boundary: the orchestrator NEVER modifies RTL, SVA, or assumptions, never
claims proof/signoff, never treats TIMEOUT/ERROR/INCONCLUSIVE as PASS. Orchestration
is heuristic; formal-tool results remain authoritative. A human gate is required to
change property/assumptions/abstraction/budget (see docs/HUMAN_GATE.md).
"""

from __future__ import annotations

from .models import SCHEMA_VERSION

__version__ = "0.1.0"
__all__ = ["__version__", "SCHEMA_VERSION"]
