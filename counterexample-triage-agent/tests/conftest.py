from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.fixture
def repo_dir() -> Path:
    return REPO


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def golden_dir() -> Path:
    return GOLDEN
