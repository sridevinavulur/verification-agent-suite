"""Formal Regression Intelligence Agent.

Deterministic clustering + statistical baselines over formal-run ledgers, with a
mock-LLM explanation layer. See README.md for scope and non-claims.
"""

from .analysis import Thresholds, analyze
from .ledger import load_ledger
from .models import (
    Finding,
    FindingKind,
    RegressionReport,
    RunLedger,
    RunRecord,
    RunStatus,
    Severity,
)

__version__ = "0.1.0"

__all__ = [
    "Thresholds",
    "analyze",
    "load_ledger",
    "Finding",
    "FindingKind",
    "RegressionReport",
    "RunLedger",
    "RunRecord",
    "RunStatus",
    "Severity",
    "__version__",
]
