"""Assemble a normalized :class:`Manifest` from RTL source files.

This orchestrates: adapter parsing -> heuristic clock/reset detection ->
hierarchy graph construction -> provenance. It is the single deterministic entry
point used by both the CLI and the tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import __version__
from .adapters import get_adapter
from .heuristics import detect_clock_reset
from .models import (
    HierarchyEdge,
    Manifest,
    Module,
    Provenance,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest_from_texts(
    sources: dict[str, str],
    *,
    adapter_name: str = "builtin",
    top: str | None = None,
    command: str = "",
    git_sha: str = "UNKNOWN",
) -> Manifest:
    """Build a manifest from a mapping of ``filename -> source text``.

    Deterministic: iteration order over ``sources`` is preserved, so a stable
    input ordering yields byte-stable JSON (used by the golden tests).
    """
    adapter = get_adapter(adapter_name)
    modules: list[Module] = []
    unresolved = []
    input_files: list[str] = []
    input_sha: dict[str, str] = {}

    for filename, text in sources.items():
        input_files.append(filename)
        input_sha[filename] = _sha256(text)
        result = adapter.parse_text(text, filename=filename)
        modules.extend(result.modules)
        unresolved.extend(result.unresolved)

    # Heuristic clock/reset detection per module.
    for module in modules:
        detect_clock_reset(module)

    # Hierarchy edges.
    defined = {m.name for m in modules}
    hierarchy: list[HierarchyEdge] = []
    for module in modules:
        for inst in module.instances:
            hierarchy.append(
                HierarchyEdge(
                    parent_module=module.name,
                    child_module=inst.module,
                    instance_name=inst.name,
                    child_defined=inst.module in defined,
                )
            )

    resolved_top = top or _infer_top(modules, hierarchy)

    manifest = Manifest(
        provenance=Provenance(
            tool_version=__version__,
            git_sha=git_sha,
            input_files=input_files,
            input_sha256=input_sha,
            command=command,
        ),
        parser=adapter.info(),
        top=resolved_top,
        modules=modules,
        hierarchy=hierarchy,
        unresolved=unresolved,
    )
    return manifest


def build_manifest_from_files(
    paths: list[Path],
    *,
    adapter_name: str = "builtin",
    top: str | None = None,
    command: str = "",
    git_sha: str = "UNKNOWN",
) -> Manifest:
    """Build a manifest from files on disk. Uses basenames as file keys."""
    sources: dict[str, str] = {}
    for p in paths:
        sources[p.name] = p.read_text(encoding="utf-8")
    return build_manifest_from_texts(
        sources,
        adapter_name=adapter_name,
        top=top,
        command=command,
        git_sha=git_sha,
    )


def _infer_top(modules: list[Module], hierarchy: list[HierarchyEdge]) -> str | None:
    """Infer the top module: a defined module never instantiated by another.

    Returns None if ambiguous (0 or >1 candidates) rather than guessing.
    """
    if not modules:
        return None
    instantiated = {
        e.child_module for e in hierarchy if e.child_defined
    }
    roots = [m.name for m in modules if m.name not in instantiated]
    if len(roots) == 1:
        return roots[0]
    if len(modules) == 1:
        return modules[0].name
    return None
