"""Input loaders for requirement files and RTL manifests.

Supports Markdown, JSON, YAML, and plain text requirement files, and JSON/YAML
RTL manifests. YAML support is optional (falls back gracefully if PyYAML is
absent).
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Requirement, RTLManifest

try:  # optional dependency
    import yaml  # type: ignore

    _HAVE_YAML = True
except Exception:  # pragma: no cover
    _HAVE_YAML = False


def _load_structured(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        if not _HAVE_YAML:  # pragma: no cover
            raise RuntimeError("PyYAML not installed; cannot read YAML")
        return yaml.safe_load(text)
    return json.loads(text)


def load_requirement(path: Path) -> Requirement:
    """Load a requirement from json/yaml (structured) or md/txt (freeform)."""
    suffix = path.suffix.lower()
    if suffix in (".json", ".yaml", ".yml"):
        data = _load_structured(path)
        data.setdefault("origin_path", str(path))
        return Requirement.model_validate(data)

    # Markdown / plain text: the whole file body is the requirement text.
    raw = path.read_text().strip()
    # For markdown, strip a leading "# ..." heading if present.
    lines = raw.splitlines()
    if lines and lines[0].startswith("#"):
        req_id = lines[0].lstrip("# ").strip().replace(" ", "_").lower()
        body = "\n".join(lines[1:]).strip()
    else:
        req_id = path.stem
        body = raw
    return Requirement(
        requirement_id=req_id or path.stem,
        source_text=body or raw,
        origin_path=str(path),
    )


def load_manifest(path: Path, *, manifest_format: str = "auto") -> RTLManifest:
    """Load an RTL Intent Manifest (engine fixture or canonical ingestor output).

    ``manifest_format`` is ``auto`` (default), ``canonical``, or ``fixture``.
    ``auto`` detects and adapts the canonical ``rtl-intent-ingestor`` manifest,
    while still accepting the engine's own fixture format (back-compat).
    JSON and YAML are both supported for either format.
    """
    from .rtl_intent_adapter import _is_canonical, from_rtl_intent_manifest

    data = _load_structured(path)
    if manifest_format == "fixture":
        return RTLManifest.model_validate(data)
    if manifest_format == "canonical" or (
        manifest_format == "auto" and _is_canonical(data)
    ):
        return from_rtl_intent_manifest(data)
    if manifest_format == "auto":
        return RTLManifest.model_validate(data)
    raise ValueError(f"unknown manifest_format: {manifest_format!r}")
