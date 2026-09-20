"""Assertion Mutation Agent.

Estimate whether an SVA property suite can detect intentionally introduced RTL
defects via real source mutation on a constrained Verilog subset. This is a
property-quality evaluation tool, not proof of complete verification.
"""

from .models import (
    Mutant,
    MutantResult,
    MutantStatus,
    MutationOperator,
    MutationReport,
    ScoreBreakdown,
)

__version__ = "0.1.0"

__all__ = [
    "Mutant",
    "MutantResult",
    "MutantStatus",
    "MutationOperator",
    "MutationReport",
    "ScoreBreakdown",
    "__version__",
]
