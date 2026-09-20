#!/usr/bin/env python3
"""Regenerate golden fixtures for the curated corpus.

Run only after confirming a behaviour change is intended:

    python scripts/regen_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from conftest import CORPUS, GOLDEN, golden_name, summarize  # noqa: E402


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for sva, man in CORPUS:
        summary = summarize(sva, man)
        (GOLDEN / golden_name(sva)).write_text(json.dumps(summary, indent=2) + "\n")
        print(f"wrote {golden_name(sva)}: {summary['counts']} grade {summary['grade']}")


if __name__ == "__main__":
    main()
