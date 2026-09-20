"""Optional C++17 graph core exposed via a subprocess JSON interface.

The pure-Python path in :mod:`graph_core` is always authoritative and always
works with no compiler. This bridge lets the SAME COI computation run in the
optional C++ core (``cpp/coi_core.cpp``) when it has been built, purely for
performance on large graphs.

Contract: the C++ binary reads a JSON ``{"edges": [[src,dst,kind_int],...],
"n": N, "seeds": [...], "combinational_only": bool}`` on stdin and writes
``{"coi": [sorted node ids]}`` on stdout. Kind ints match the order of
``list(EdgeKind)``.

If the binary is missing or fails, :func:`coi_via_cpp` raises
``CppCoreUnavailable`` and callers fall back to Python.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .graph_core import PackedGraph
from .models import EdgeKind


class CppCoreUnavailable(RuntimeError):
    pass


def find_cpp_binary() -> Path | None:
    """Locate a built coi_core binary, if any."""
    env_candidates = [
        Path(__file__).resolve().parent.parent.parent / "cpp" / "build" / "coi_core",
        Path(__file__).resolve().parent.parent.parent / "cpp" / "coi_core",
    ]
    for c in env_candidates:
        if c.exists() and c.is_file():
            return c
    which = shutil.which("coi_core")
    return Path(which) if which else None


def coi_via_cpp(
    pg: PackedGraph, seeds: list[int], *, combinational_only: bool
) -> list[int]:
    binary = find_cpp_binary()
    if binary is None:
        raise CppCoreUnavailable("coi_core binary not found; build cpp/ first")
    kind_to_int = {k: i for i, k in enumerate(EdgeKind)}
    edges: list[list[int]] = []
    for src in range(pg.n):
        for dst, kind in pg.neighbours(src):
            edges.append([src, dst, kind_to_int[kind]])
    payload = {
        "n": pg.n,
        "edges": edges,
        "seeds": sorted(set(seeds)),
        "combinational_only": combinational_only,
    }
    try:
        proc = subprocess.run(
            [str(binary)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:  # pragma: no cover
        raise CppCoreUnavailable(f"coi_core failed: {exc}") from exc
    try:
        out = json.loads(proc.stdout)
        return sorted(int(x) for x in out["coi"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:  # pragma: no cover
        raise CppCoreUnavailable(f"bad coi_core output: {exc}") from exc
