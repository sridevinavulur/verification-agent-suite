from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def toy_alu(examples_dir: Path) -> Path:
    return examples_dir / "toy_alu"


@pytest.fixture
def toy_counter(examples_dir: Path) -> Path:
    return examples_dir / "toy_counter"
