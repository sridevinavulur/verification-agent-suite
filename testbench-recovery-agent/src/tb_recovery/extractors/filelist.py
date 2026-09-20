"""Verilog/SystemVerilog file-list (``.f``) extractor.

A ``.f`` file is the standard argument-file simulators accept via ``-f``. It
lists source files, ``+incdir+`` include dirs, ``-y`` library dirs, defines,
and (recursively) other ``-f`` file lists. We recover the concrete source files
and record include dirs / nested filelists so downstream target-source mapping
is accurate.

Each recovered source becomes a ``TargetSourceMap`` entry (EXTRACTED). Comment
lines (``//``, ``#``) are ignored.
"""

from __future__ import annotations

from ..models import (
    Evidence,
    Provenance,
    SetupIssue,
    Severity,
    SourceKind,
    TargetSourceMap,
)
from .base import ExtractResult

_SRC_SUFFIXES = (".sv", ".svh", ".v", ".vh", ".vhd", ".vhdl")


def extract_filelist(rel_path: str, text: str) -> ExtractResult:
    result = ExtractResult()
    sources: list[str] = []
    filelists: list[str] = []
    incdirs: list[str] = []
    ev_line = 1

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        # Strip trailing inline comment.
        line = line.split("//", 1)[0].strip()
        if not line:
            continue

        for tok in line.split():
            if tok.startswith("+incdir+"):
                incdirs.append(tok[len("+incdir+"):])
            elif tok.startswith(("-f", "-F")) and len(tok) > 2:
                filelists.append(tok[2:])
            elif tok in ("-f", "-F"):
                continue  # next token is the filelist; handled loosely below
            elif tok.endswith(".f"):
                filelists.append(tok)
                ev_line = idx
            elif tok.startswith(("+", "-")):
                continue  # define/flag - not a source
            elif tok.endswith(_SRC_SUFFIXES):
                sources.append(tok)
                ev_line = idx

    if not sources and not filelists:
        result.issues.append(
            SetupIssue(
                severity=Severity.INFO,
                message=f"Filelist {rel_path} contained no recognizable source files.",
                evidence=[
                    Evidence(file=rel_path, line=1, snippet="(empty filelist)",
                             source_kind=SourceKind.FILELIST)
                ],
            )
        )
        return result

    result.target_source_map.append(
        TargetSourceMap(
            target_name=rel_path,
            sources=sorted(set(sources)),
            filelists=sorted(set(filelists)),
            provenance=Provenance.EXTRACTED,
            evidence=[
                Evidence(file=rel_path, line=ev_line,
                         snippet=f"{len(sources)} source(s), "
                                 f"{len(incdirs)} incdir(s)",
                         source_kind=SourceKind.FILELIST)
            ],
        )
    )
    return result
