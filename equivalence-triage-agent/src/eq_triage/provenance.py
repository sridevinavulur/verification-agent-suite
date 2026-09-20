"""Run-provenance helpers (input hashing, git SHA)."""

from __future__ import annotations

import hashlib
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .models import Provenance


def tool_version() -> str:
    try:
        return version("eq-triage")
    except PackageNotFoundError:
        return "0.1.0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        sha = out.stdout.strip()
        return sha or "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def build_provenance(command: str, input_files: list[Path]) -> Provenance:
    hashes: dict[str, str] = {}
    existing: list[str] = []
    for p in input_files:
        p = Path(p)
        if p.exists():
            hashes[str(p)] = sha256_file(p)
            existing.append(str(p))
    return Provenance(
        tool_version=tool_version(),
        command=command,
        git_sha=git_sha(),
        input_files=existing,
        input_sha256=hashes,
    )
