"""Regenerate the golden manifests. Run intentionally when output changes.

    python tests/regenerate_golden.py

Never run this in CI - CI compares against committed goldens.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import EXAMPLES, GOLDEN_DIR, build_example_manifest  # noqa: E402
from rtl_intent.serialize import manifest_to_json  # noqa: E402


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in EXAMPLES:
        manifest = build_example_manifest(name)
        (GOLDEN_DIR / f"{name}.json").write_text(
            manifest_to_json(manifest), encoding="utf-8"
        )
        print(f"wrote {GOLDEN_DIR / f'{name}.json'}")


if __name__ == "__main__":
    main()
