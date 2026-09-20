"""Static extractors for the Testbench Recovery Agent.

Each extractor consumes exactly one artifact type and returns an
``ExtractResult``. Extractors are deterministic and never execute anything.
"""

from __future__ import annotations

from .base import ExtractResult, classify_phase, tools_in_command
from .ci import extract_ci_workflow
from .filelist import extract_filelist
from .makefile import extract_makefile
from .readme import extract_readme
from .shell import extract_shell

__all__ = [
    "ExtractResult",
    "classify_phase",
    "tools_in_command",
    "extract_makefile",
    "extract_shell",
    "extract_ci_workflow",
    "extract_filelist",
    "extract_readme",
]
