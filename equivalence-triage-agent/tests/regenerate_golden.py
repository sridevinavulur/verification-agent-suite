"""Regenerate golden report files for the toy examples.

Run:  python tests/regenerate_golden.py

Provenance is normalized (fixed tool_version, no git SHA, basename-only input
paths) so golden files are byte-stable across machines.
"""

from __future__ import annotations

import json
from pathlib import Path

from eq_triage.models import Provenance, SourceMap
from eq_triage.parser import load_manifest, parse_equivalence_log
from eq_triage.report import render_markdown
from eq_triage.triage import TriageEngine

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
GOLDEN = ROOT / "tests" / "golden"


def _fixed_provenance(name: str) -> Provenance:
    return Provenance(
        tool_version="0.1.0",
        command=f"eq-triage demo {name}",
        git_sha="GOLDEN",
        input_files=[],
        input_sha256={},
    )


def build(name: str):
    d = EXAMPLES / name
    log = parse_equivalence_log(
        (d / "equivalence.eqlog").read_text(),
        source_path=f"examples/{name}/equivalence.eqlog",
    )
    ref = load_manifest(d / "ref_manifest.json")
    rev = load_manifest(d / "rev_manifest.json")
    smap = SourceMap.model_validate_json((d / "source_map.json").read_text())
    engine = TriageEngine(log, ref, rev, smap)
    return engine.run(
        provenance=_fixed_provenance(name),
        repro_command=f"eq-triage demo {name}",
        input_files=[],
    )


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in ("toy_alu", "toy_counter"):
        report = build(name)
        (GOLDEN / f"{name}_report.json").write_text(
            json.dumps(json.loads(report.model_dump_json()), indent=2) + "\n"
        )
        (GOLDEN / f"{name}_report.md").write_text(render_markdown(report))
        print(f"wrote golden for {name}")


if __name__ == "__main__":
    main()
