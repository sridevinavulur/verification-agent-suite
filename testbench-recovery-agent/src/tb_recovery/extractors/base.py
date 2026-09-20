"""Shared extractor infrastructure: result container, tool/phase knowledge.

The knowledge tables here are deliberately *conservative*. They are used to
classify commands and to note that a tool *appears required*. They are NOT used
to invent command-line options or to claim a tool is installed - that would
violate the safety rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import (
    CandidateCommand,
    Dependency,
    SetupIssue,
    TargetPhase,
    TargetSourceMap,
    ToolRequirement,
)


@dataclass
class ExtractResult:
    """Everything a single extractor recovered from one artifact."""

    commands: list[CandidateCommand] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    tools: list[ToolRequirement] = field(default_factory=list)
    target_source_map: list[TargetSourceMap] = field(default_factory=list)
    issues: list[SetupIssue] = field(default_factory=list)

    def extend(self, other: ExtractResult) -> None:
        self.commands.extend(other.commands)
        self.dependencies.extend(other.dependencies)
        self.tools.extend(other.tools)
        self.target_source_map.extend(other.target_source_map)
        self.issues.extend(other.issues)


# Known verification tool executables -> (canonical name, category).
# Keys are matched as whole words against a command's tokens.
KNOWN_TOOLS: dict[str, tuple[str, str]] = {
    "verilator": ("verilator", "simulator"),
    "iverilog": ("icarus-verilog", "simulator"),
    "vvp": ("icarus-verilog", "simulator"),
    "vsim": ("questa/modelsim", "simulator"),
    "vlog": ("questa/modelsim", "simulator"),
    "vcom": ("questa/modelsim", "simulator"),
    "xrun": ("xcelium", "simulator"),
    "xmvlog": ("xcelium", "simulator"),
    "vcs": ("vcs", "simulator"),
    "simv": ("vcs", "simulator"),
    "ghdl": ("ghdl", "simulator"),
    "cocotb": ("cocotb", "simulator"),
    "sby": ("symbiyosys", "formal"),
    "symbiyosys": ("symbiyosys", "formal"),
    "yosys": ("yosys", "synthesis"),
    "jaspergold": ("jaspergold", "formal"),
    "jg": ("jaspergold", "formal"),
    "verible-verilog-lint": ("verible", "lint"),
    "verilator_lint": ("verilator", "lint"),
    "make": ("make", "build"),
    "cmake": ("cmake", "build"),
    "ninja": ("ninja", "build"),
    "python": ("python", "python"),
    "python3": ("python", "python"),
    "pytest": ("pytest", "python"),
}

# Phase classification keyword tables. Order matters: first match wins per group.
_ANALYZE_KW = ("lint", "coverage", "waveform", "gtkwave", "trace", "report", "cover")
_ELAB_KW = ("elaborate", "elab", "-elaborate")
_RUN_KW = ("run", "simulate", "sim", "test", "vvp", "simv", "vsim", "xrun", "sby")
_BUILD_KW = ("build", "compile", "verilator", "iverilog", "vlog", "vcs", "cmake")


def tools_in_command(command: str) -> list[str]:
    """Return canonical tool names referenced by a command (deduped, ordered)."""
    tokens = re.findall(r"[A-Za-z0-9_.\-/]+", command)
    seen: list[str] = []
    for tok in tokens:
        base = tok.rsplit("/", 1)[-1]  # strip any path prefix
        hit = KNOWN_TOOLS.get(base)
        if hit and hit[0] not in seen:
            seen.append(hit[0])
    return seen


def tool_requirements_for(command: str, provenance, evidence) -> list[ToolRequirement]:
    """Build ToolRequirement entries for tools referenced by a command."""
    reqs: list[ToolRequirement] = []
    tokens = re.findall(r"[A-Za-z0-9_.\-/]+", command)
    added: set[str] = set()
    for tok in tokens:
        base = tok.rsplit("/", 1)[-1]
        hit = KNOWN_TOOLS.get(base)
        if hit and hit[0] not in added:
            name, category = hit
            added.add(name)
            reqs.append(
                ToolRequirement(
                    name=name,
                    category=category,
                    provenance=provenance,
                    evidence=list(evidence),
                )
            )
    return reqs


def classify_phase(command: str, target_name: str | None = None) -> TargetPhase:
    """Heuristically classify a command into a verification phase.

    Uses the command text and (optionally) the target/label name. This is a
    heuristic; callers keep the command's provenance separate from this label.
    """
    hay = f"{target_name or ''} {command}".lower()

    if "clean" in hay or re.search(r"\brm\s+-rf?\b", hay):
        return TargetPhase.CLEAN
    if any(k in hay for k in ("apt-get", "pip install", "setup", "install", "venv")):
        # 'install' as a whole word / setup phase
        if re.search(r"\b(install|setup|venv|apt-get|pip)\b", hay):
            return TargetPhase.SETUP
    if any(k in hay for k in _ANALYZE_KW):
        return TargetPhase.ANALYZE
    if any(k in hay for k in _ELAB_KW):
        return TargetPhase.ELABORATE
    if any(re.search(rf"\b{re.escape(k)}\b", hay) for k in _RUN_KW):
        return TargetPhase.RUN
    if any(k in hay for k in _BUILD_KW):
        return TargetPhase.BUILD
    return TargetPhase.UNKNOWN


_DESTRUCTIVE_RE = re.compile(
    r"\b(rm\s+-rf?|rm\s+-fr?|git\s+clean|make\s+\w*clean|dd\s+if=|mkfs|"
    r">\s*/dev/|chmod\s+-R|chown\s+-R)\b"
)


def is_destructive(command: str) -> bool:
    """True if a command deletes/overwrites data (used to keep smoke tests safe)."""
    return bool(_DESTRUCTIVE_RE.search(command))
