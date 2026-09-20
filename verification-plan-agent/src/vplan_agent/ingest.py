"""Input loading and RTL Intent Manifest projection.

The RTL Intent Manifest is consumed via the *canonical* external schema at
``rtl-intent-ingestor/schemas/manifest.schema.json``. We read the real field
names from that schema (``modules[].ports[].name/direction``,
``reset_candidates[].signal``, ``clock_candidates[].signal``, ``registers``,
``nets[].is_memory``, top-level ``top``) and project them into the minimal
:class:`~vplan_agent.models.ManifestView` used by the engine.

Loading is defensive: a manifest produced by the real ingestor carries many
more fields than we need, so the view uses ``extra="ignore"`` and only pulls
the fields named in the canonical schema.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import (
    ExistingTestplan,
    InterfaceGlossary,
    ManifestModuleView,
    ManifestPortView,
    ManifestView,
    SpecDocument,
)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_spec(path: Path) -> SpecDocument:
    return SpecDocument.model_validate(_read_json(path))


def load_interface(path: Path) -> InterfaceGlossary:
    return InterfaceGlossary.model_validate(_read_json(path))


def load_existing_testplan(path: Path | None) -> ExistingTestplan:
    if path is None:
        return ExistingTestplan()
    return ExistingTestplan.model_validate(_read_json(path))


def project_manifest(manifest: dict[str, Any]) -> ManifestView:
    """Project a canonical RTL Intent Manifest dict into a :class:`ManifestView`.

    Uses only field names present in ``manifest.schema.json``.
    """
    modules: list[ManifestModuleView] = []
    for mod in manifest.get("modules", []):
        ports = [
            ManifestPortView(
                name=p["name"],
                direction=p.get("direction", "input"),
            )
            for p in mod.get("ports", [])
        ]
        reset_signals = [rc["signal"] for rc in mod.get("reset_candidates", [])]
        clock_signals = [cc["signal"] for cc in mod.get("clock_candidates", [])]
        has_memory = any(n.get("is_memory", False) for n in mod.get("nets", []))
        modules.append(
            ManifestModuleView(
                name=mod["name"],
                ports=ports,
                reset_candidate_signals=reset_signals,
                clock_candidate_signals=clock_signals,
                register_count=len(mod.get("registers", [])),
                has_memory=has_memory,
            )
        )
    return ManifestView(top=manifest.get("top"), modules=modules)


def load_manifest_view(path: Path | None) -> ManifestView:
    if path is None:
        return ManifestView()
    return project_manifest(_read_json(path))


def sha256_files(paths: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paths:
        out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out
