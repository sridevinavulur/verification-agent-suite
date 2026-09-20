"""Regenerate golden temporal-intent JSON and rendered SVA for examples.

Usage: python scripts/gen_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

from sva_intent_engine.io_utils import load_manifest, load_requirement
from sva_intent_engine.pipeline import run_full
from sva_intent_engine.schema_export import export_all

ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = ROOT / "examples" / "requirements"
MAN_DIR = ROOT / "examples" / "rtl_manifests"
GOLD_INTENT = ROOT / "examples" / "golden_intent"
GOLD_SVA = ROOT / "examples" / "golden_sva"


def _canonical_intent(intent) -> dict:
    """Deterministic subset of an intent (drop volatile provenance)."""
    d = intent.model_dump(mode="json")
    d.pop("provenance", None)
    return d


def main() -> None:
    GOLD_INTENT.mkdir(parents=True, exist_ok=True)
    GOLD_SVA.mkdir(parents=True, exist_ok=True)

    for rf in sorted(REQ_DIR.glob("*.md")):
        mf = MAN_DIR / f"{rf.stem}.json"
        req = load_requirement(rf)
        manifest = load_manifest(mf)
        report = run_full(req, manifest, command="gen_golden")

        intents = [_canonical_intent(i) for i in report.intents]
        (GOLD_INTENT / f"{rf.stem}.json").write_text(
            json.dumps(intents, indent=2, sort_keys=True) + "\n"
        )

        sva_lines = []
        for v in report.validations:
            if v.emitted and v.candidate:
                sva_lines.append(v.candidate.sva_text)
        (GOLD_SVA / f"{rf.stem}.sva").write_text("\n\n".join(sva_lines) + "\n")
        print(f"golden written for {rf.stem}")

    written = export_all(ROOT / "schemas")
    print(f"exported {len(written)} JSON schemas")


if __name__ == "__main__":
    main()
