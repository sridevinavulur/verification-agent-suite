"""Sandboxed optional execution adapter - DOCUMENTED STUB (Phase 2).

The pack section says: "Implement static repository inspection first, then
sandboxed optional execution adapters." Phase 1 (this release) is static only.

This module defines the *interface* a future sandboxed executor must satisfy,
plus a default ``DisabledExecutor`` that refuses to run anything. It never
executes a recovered command. When Phase 2 lands, a real adapter (e.g. a
container/nsjail-backed runner) will implement ``SandboxExecutor`` with:

* explicit allow-listing of non-destructive commands only,
* resource limits (CPU, wall-clock, memory) recorded per run,
* full provenance capture (command, exit code, stdout/stderr hashes),
* a hard refusal for any command flagged ``destructive``.

Until then, calling ``run`` raises ``NotImplementedError`` by design so no
accidental execution can occur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import CandidateCommand


@dataclass(frozen=True)
class ExecutionResult:
    """Result contract a Phase-2 executor will return (unused in Phase 1)."""

    command: str
    exit_code: int
    status: str  # PASS | FAIL | TIMEOUT | ERROR | UNKNOWN
    stdout_sha256: str
    stderr_sha256: str
    wall_seconds: float
    peak_memory_kb: int | None


@runtime_checkable
class SandboxExecutor(Protocol):
    """Interface for a future sandboxed execution adapter."""

    def run(self, command: CandidateCommand, *, cwd: str) -> ExecutionResult: ...


class DisabledExecutor:
    """Default executor: refuses to run anything (safe by construction)."""

    enabled: bool = False

    def run(self, command: CandidateCommand, *, cwd: str) -> ExecutionResult:
        raise NotImplementedError(
            "Sandboxed execution is a Phase-2 stub and is disabled. "
            "This tool performs static inspection only; it never executes "
            "recovered repository commands."
        )
