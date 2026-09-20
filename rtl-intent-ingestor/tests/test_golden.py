"""Golden-output tests: parsed manifests must match committed goldens byte-for-byte.

If the parser output legitimately changes, regenerate with
``python tests/regenerate_golden.py`` and review the diff.
"""

from __future__ import annotations

from conftest import GOLDEN_DIR, build_example_manifest
from rtl_intent.serialize import manifest_from_json, manifest_to_json


def test_golden_matches(example_name: str) -> None:
    manifest = build_example_manifest(example_name)
    produced = manifest_to_json(manifest)
    golden = (GOLDEN_DIR / f"{example_name}.json").read_text(encoding="utf-8")
    assert produced == golden, (
        f"manifest for {example_name} differs from golden; "
        "run 'python tests/regenerate_golden.py' if the change is intended"
    )


def test_golden_roundtrips_through_model(example_name: str) -> None:
    """Golden JSON must validate against the Pydantic contract and round-trip."""
    golden = (GOLDEN_DIR / f"{example_name}.json").read_text(encoding="utf-8")
    manifest = manifest_from_json(golden)
    assert manifest_to_json(manifest) == golden


def test_manifest_is_deterministic(example_name: str) -> None:
    a = manifest_to_json(build_example_manifest(example_name))
    b = manifest_to_json(build_example_manifest(example_name))
    assert a == b
