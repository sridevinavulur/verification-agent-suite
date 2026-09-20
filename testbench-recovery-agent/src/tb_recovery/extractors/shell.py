"""Shell build-script extractor.

Recovers command lines from ``*.sh`` build/run scripts with file+line evidence.
It focuses on lines that invoke a known verification/build tool, install a
dependency, or reference a source/filelist - not every shell statement.

Constrained parser: it does not evaluate control flow, does not follow sourced
files, and does best-effort ``VAR=...`` substitution for simple variables.
"""

from __future__ import annotations

import re

from ..models import (
    CandidateCommand,
    Dependency,
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

_ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_VAR_REF_RE = re.compile(r"\$[{]?([A-Za-z_][A-Za-z0-9_]*)[}]?")
_PIP_RE = re.compile(r"\bpip3?\s+install\s+(.+)$")
_APT_RE = re.compile(r"\bapt(?:-get)?\s+install\s+(?:-y\s+)?(.+)$")


def _expand(value: str, variables: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        return variables.get(m.group(1), m.group(0))

    return _VAR_REF_RE.sub(repl, value)


def _looks_interesting(cmd: str) -> bool:
    tokens = re.findall(r"[A-Za-z0-9_.\-/]+", cmd)
    for tok in tokens:
        base = tok.rsplit("/", 1)[-1]
        if base in KNOWN_TOOLS:
            return True
    return bool(_PIP_RE.search(cmd) or _APT_RE.search(cmd))


def extract_shell(rel_path: str, text: str) -> ExtractResult:
    result = ExtractResult()
    variables: dict[str, str] = {}

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        am = _ASSIGN_RE.match(line)
        if am and " " not in am.group(2).strip().split("#")[0].strip():
            val = am.group(2).strip().strip('"').strip("'")
            variables[am.group(1)] = _expand(val, variables)
            continue

        expanded = _expand(stripped, variables)
        ev = Evidence(
            file=rel_path, line=idx, snippet=stripped, source_kind=SourceKind.SHELL
        )

        # Dependency installs.
        pip = _PIP_RE.search(expanded)
        if pip:
            for pkg in _split_pkgs(pip.group(1)):
                result.dependencies.append(
                    Dependency(
                        name=pkg,
                        manager="pip",
                        provenance=Provenance.EXTRACTED,
                        evidence=[ev],
                    )
                )
        apt = _APT_RE.search(expanded)
        if apt:
            for pkg in _split_pkgs(apt.group(1)):
                result.dependencies.append(
                    Dependency(
                        name=pkg,
                        manager="apt",
                        provenance=Provenance.EXTRACTED,
                        evidence=[ev],
                    )
                )

        if not _looks_interesting(expanded):
            continue

        cmd = CandidateCommand(
            command=expanded,
            phase=classify_phase(expanded),
            provenance=Provenance.EXTRACTED,
            evidence=[ev],
            target_name=rel_path,
            tools=tools_in_command(expanded),
            destructive=is_destructive(expanded),
        )
        result.commands.append(cmd)
        result.tools.extend(
            tool_requirements_for(expanded, Provenance.EXTRACTED, [ev])
        )

    return result


def _split_pkgs(spec: str) -> list[str]:
    spec = spec.split("#", 1)[0].split("&&", 1)[0].split(";", 1)[0]
    pkgs: list[str] = []
    for tok in spec.split():
        tok = tok.strip()
        if not tok or tok.startswith("-"):
            continue  # flags like -y, -r
        if tok in ("&&", "\\"):
            continue
        pkgs.append(tok)
    return pkgs
