"""security-property-agent: structured security requirements -> candidate SVA.

Deterministic pipeline that decomposes structured security requirements,
grounds them against a canonical RTL Intent Manifest, and emits reviewable
candidate SystemVerilog Assertions plus mutation/fault examples.

Nothing here proves a security property. All output is candidate material for
human review.
"""

from __future__ import annotations

from .models import SCHEMA_VERSION, TOOL_NAME

__all__ = ["SCHEMA_VERSION", "TOOL_NAME", "__version__"]
__version__ = SCHEMA_VERSION
