"""Stable JSON serialization for manifests.

Uses Pydantic v2 ``model_dump`` with enum values and sorted keys so output is
byte-stable across runs and platforms - a hard requirement for golden tests.
"""

from __future__ import annotations

import json

from .models import Manifest


def manifest_to_json(manifest: Manifest, *, indent: int = 2) -> str:
    data = manifest.model_dump(mode="json")
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def manifest_from_json(text: str) -> Manifest:
    return Manifest.model_validate_json(text)
