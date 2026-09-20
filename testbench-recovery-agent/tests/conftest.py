"""Shared pytest fixtures/paths for the Testbench Recovery Agent tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_REPO = REPO_ROOT / "examples" / "toy_repo"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
