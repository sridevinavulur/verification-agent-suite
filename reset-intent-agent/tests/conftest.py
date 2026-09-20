from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def rtl_dir() -> Path:
    return EXAMPLES / "rtl"


@pytest.fixture
def manifest_dir() -> Path:
    return EXAMPLES / "manifests"
