"""Pytest fixtures pointing at the bundled public example ledger + golden."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def sample_ledger_path() -> Path:
    return EXAMPLES / "sample_ledger.jsonl"


@pytest.fixture
def golden_report_path() -> Path:
    return EXAMPLES / "golden_report.json"
