from __future__ import annotations

from pathlib import Path

import pytest

from security_property_agent.io_utils import load_requirement_set
from security_property_agent.manifest import load_manifest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def manifest_path() -> Path:
    return EXAMPLES / "rtl" / "secure_soc.manifest.json"


@pytest.fixture
def requirements_path() -> Path:
    return EXAMPLES / "requirements" / "secure_soc.requirements.yaml"


@pytest.fixture
def manifest(manifest_path: Path):
    return load_manifest(manifest_path)


@pytest.fixture
def reqset(requirements_path: Path):
    return load_requirement_set(requirements_path)
