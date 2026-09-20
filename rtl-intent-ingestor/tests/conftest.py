"""Shared test fixtures and the canonical manifest-build helper.

Golden manifests are built through :func:`build_example_manifest` so both the
regeneration script and the tests use the *identical* deterministic path
(fixed command string, fixed git sha). This keeps golden JSON byte-stable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rtl_intent.manifest import build_manifest_from_texts
from rtl_intent.models import Manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

EXAMPLES = ["counter", "fifo_queue", "valid_ready"]


def build_example_manifest(name: str) -> Manifest:
    """Deterministically build the manifest for an example by base name."""
    src = (EXAMPLES_DIR / f"{name}.sv").read_text(encoding="utf-8")
    return build_manifest_from_texts(
        {f"{name}.sv": src},
        adapter_name="builtin",
        command=f"rtl-intent ingest examples/{name}.sv",
        git_sha="UNKNOWN",
    )


@pytest.fixture(params=EXAMPLES)
def example_name(request) -> str:
    return request.param
