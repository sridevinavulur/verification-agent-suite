"""README / documentation extractor.

READMEs describe how to build and run, but the commands there are documentation,
not a machine-verified recipe. We therefore recover commands from fenced code
blocks (``` ... ```) and inline shell prompts, but tag phase classification
carefully and keep provenance EXTRACTED *only* when a command is literally
present in the file. Commands are still evidence-backed (file+line), but the
smoke-test selector prefers Makefile/CI evidence over README evidence because
docs drift.

We recover a line as a command if it is inside a fenced code block whose info
string is empty/``sh``/``bash``/``console``/``shell``/``make`` OR it begins with
a ``$`` shell prompt. We strip a leading ``$``.
"""

from __future__ import annotations

import re

from ..models import (
    CandidateCommand,
    Evidence,
    Provenance,
    SourceKind,
)
from .base import (
    KNOWN_TOOLS,
    ExtractResult,
    classify_phase,
    is_destructive,
    tool_requirements_for,
    tools_in_command,
)

_FENCE_RE = re.compile(r"^\s*```(.*)$")
_SHELL_INFO = {"", "sh", "bash", "console", "shell", "shellsession", "make", "text"}
_PROMPT_RE = re.compile(r"^\s*\$\s+(.*)$")


def _is_command_like(cmd: str) -> bool:
    """True if the line plausibly is a runnable command we care about."""
    first = cmd.split()[0] if cmd.split() else ""
    base = first.rsplit("/", 1)[-1]
    if base in KNOWN_TOOLS:
        return True
    if base in ("make", "cmake", "git", "cd", "bash", "sh", "./configure"):
        return True
    if first.startswith("./"):
        return True
    return False


def extract_readme(rel_path: str, text: str) -> ExtractResult:
    result = ExtractResult()
    lines = text.splitlines()

    in_fence = False
    fence_is_shell = False

    for idx, raw in enumerate(lines, start=1):
        fence = _FENCE_RE.match(raw)
        if fence:
            if not in_fence:
                info = fence.group(1).strip().lower()
                in_fence = True
                fence_is_shell = info in _SHELL_INFO
            else:
                in_fence = False
                fence_is_shell = False
            continue

        candidate: str | None = None
        if in_fence and fence_is_shell:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Allow an optional '$' prompt inside fences too.
            pm = _PROMPT_RE.match(raw)
            candidate = pm.group(1).strip() if pm else stripped
        else:
            pm = _PROMPT_RE.match(raw)
            if pm:
                candidate = pm.group(1).strip()

        if not candidate or not _is_command_like(candidate):
            continue

        ev = Evidence(
            file=rel_path, line=idx, snippet=raw.strip(),
            source_kind=SourceKind.README,
        )
        cmd = CandidateCommand(
            command=candidate,
            phase=classify_phase(candidate),
            provenance=Provenance.EXTRACTED,
            evidence=[ev],
            target_name=f"readme:{rel_path}",
            tools=tools_in_command(candidate),
            destructive=is_destructive(candidate),
        )
        result.commands.append(cmd)
        result.tools.extend(
            tool_requirements_for(candidate, Provenance.EXTRACTED, [ev])
        )

    return result
