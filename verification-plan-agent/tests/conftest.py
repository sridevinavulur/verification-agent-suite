"""Shared pytest fixtures and paths."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"
EXPECTED = EXAMPLES / "expected"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def expected_dir() -> Path:
    return EXPECTED
