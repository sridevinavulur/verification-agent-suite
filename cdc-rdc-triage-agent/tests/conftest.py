from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples" / "expected"
GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def golden_dir() -> Path:
    return GOLDEN
