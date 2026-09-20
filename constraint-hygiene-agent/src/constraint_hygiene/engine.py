"""Top-level orchestration: SVA + manifest -> HygieneReport.

This is the deterministic core. Given SVA text and an optional manifest view it
runs every analysis pass and assembles a :class:`HygieneReport`. It performs no
network or LLM calls; all logic is reproducible.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import __version__
from .analysis.contradictions import find_contradictions
from .analysis.dependency import build_dependency_map, vacuity_recommendations
from .analysis.ownership import classify_signals
from .analysis.review import build_review_queue
from .analysis.usage import find_output_constraints, find_unused_assumptions
from .models import (
    HygieneReport,
    Property,
    Provenance,
    SvaKind,
)
from .parsers.manifest import ManifestView
from .parsers.sva import parse_sva


def analyze(
    properties: list[Property],
    manifest: ManifestView,
    provenance: Provenance | None = None,
) -> HygieneReport:
    """Run all hygiene passes over already-parsed properties."""
    assumes = [p for p in properties if p.kind is SvaKind.ASSUME]
    asserts = [p for p in properties if p.kind is SvaKind.ASSERT]
    covers = [p for p in properties if p.kind is SvaKind.COVER]

    all_signals: set[str] = set()
    for p in properties:
        all_signals.update(p.signals)

    ownership = classify_signals(all_signals, manifest)
    contradictions = find_contradictions(properties)
    unused = find_unused_assumptions(properties)
    output_warnings = find_output_constraints(properties, ownership)
    dep_map = build_dependency_map(properties)
    vacuity = vacuity_recommendations(properties, len(contradictions))

    review_queue = build_review_queue(
        contradictions + unused + output_warnings + vacuity
    )

    return HygieneReport(
        provenance=provenance or Provenance(tool_version=__version__),
        top_module=manifest.top,
        assumption_inventory=assumes,
        assertion_inventory=asserts,
        cover_inventory=covers,
        signal_ownership=ownership,
        contradiction_candidates=contradictions,
        unused_assumption_candidates=unused,
        output_constraint_warnings=output_warnings,
        dependency_map=dep_map,
        vacuity_recommendations=vacuity,
        human_review_queue=review_queue,
    )


def analyze_files(
    sva_path: str | Path,
    manifest_path: str | Path | None = None,
    command: str = "",
) -> HygieneReport:
    """Convenience: parse files from disk and analyze."""
    sva_path = Path(sva_path)
    sva_text = sva_path.read_text()
    properties = parse_sva(sva_text, filename=sva_path.name)

    manifest = ManifestView()
    input_files = [str(sva_path)]
    input_sha = {sva_path.name: _sha256(sva_text)}

    if manifest_path is not None:
        from .parsers.manifest import load_manifest

        mp = Path(manifest_path)
        manifest = load_manifest(mp)
        input_files.append(str(mp))
        input_sha[mp.name] = _sha256(mp.read_text())

    prov = Provenance(
        tool_version=__version__,
        command=command,
        input_files=input_files,
        input_sha256=input_sha,
    )
    return analyze(properties, manifest, provenance=prov)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
