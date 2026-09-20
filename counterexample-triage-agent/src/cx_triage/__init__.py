"""Counterexample Triage Agent.

Deterministic, evidence-grounded triage of formal/simulation counterexamples.
"""

from .compose import compose_report
from .executor import (
    DeterministicExecutor,
    ReproResult,
    ReproStatus,
    VerilatorReproExecutor,
    get_executor,
    verilator_available,
)
from .manifest_adapter import from_canonical_manifest, load_manifest
from .models import (
    AssertionFailure,
    ReproAttempt,
    RTLIntentManifest,
    TriageReport,
    WaveTrace,
)
from .parser import load_json_trace, parse_vcd, parse_vcd_file
from .report import render_markdown
from .triage import TriageEngine

__version__ = "0.1.0"

__all__ = [
    "AssertionFailure",
    "RTLIntentManifest",
    "ReproAttempt",
    "TriageReport",
    "WaveTrace",
    "TriageEngine",
    "parse_vcd",
    "parse_vcd_file",
    "load_json_trace",
    "render_markdown",
    "load_manifest",
    "from_canonical_manifest",
    "get_executor",
    "DeterministicExecutor",
    "VerilatorReproExecutor",
    "ReproResult",
    "ReproStatus",
    "verilator_available",
    "compose_report",
    "__version__",
]
