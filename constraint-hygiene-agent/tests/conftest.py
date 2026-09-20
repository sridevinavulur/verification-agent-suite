from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def manifest_path() -> Path:
    return EXAMPLES / "dut_manifest.json"


@pytest.fixture
def good_sva() -> Path:
    return EXAMPLES / "good" / "good_constraints.sva"


@pytest.fixture
def bad_sva() -> Path:
    return EXAMPLES / "bad" / "bad_constraints.sva"
