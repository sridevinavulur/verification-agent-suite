"""tb_recovery - Testbench Recovery Agent (v0.1).

Static inspection of a public RTL/verification repository checkout to
reconstruct how to build, elaborate, run, and analyze its verification targets.
Every recovered command carries provenance: EXTRACTED (with file+line evidence)
vs HYPOTHESIS (heuristic, evidence-free). No repository command is executed.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
