"""Input loading helpers (JSON / YAML) with sha256 provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .models import ContractRequest, RtlManifest


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_data(path: Path) -> Any:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def load_manifest(path: Path) -> RtlManifest:
    return RtlManifest.model_validate(_load_data(path))


def load_request(path: Path) -> ContractRequest:
    return ContractRequest.model_validate(_load_data(path))
