"""Top-level orchestration for the Reset Intent Agent.

Wires the parser/manifest-adapter -> analyzer -> SVA generator ->
ResetIntentManifest. This is the deterministic core; there is no LLM in the
analysis path (the tool's outputs are structural facts and heuristics, not
generated prose).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .analyzer import ResetAnalyzer, generate_candidate_sva, module_clock
from .manifest_adapter import parsed_modules_from_manifest
from .models import Provenance, ResetIntentManifest
from .rtl_parser import ParsedModule, parse_text


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_provenance(input_files: list[str], sha: dict[str, str], command: str) -> Provenance:
    return Provenance(
        tool_version=__version__,
        command=command,
        input_files=input_files,
        input_sha256=sha,
    )


def analyze_module(module: ParsedModule) -> ResetIntentManifest:
    """Run the full analysis on a single parsed module (provenance is minimal)."""
    return _analyze([module], _build_provenance([], {}, ""))


def _analyze(modules: list[ParsedModule], provenance: Provenance) -> ResetIntentManifest:
    # Analyze the first module with reset activity (or the first module).
    target = _select_module(modules)
    analyzer = ResetAnalyzer(target)
    (
        candidates,
        targets,
        domains,
        crossings,
        graph,
        risks,
        ambiguities,
        recs,
    ) = analyzer.analyze()
    clock = module_clock(target)
    sva = generate_candidate_sva(candidates, targets, clock)
    return ResetIntentManifest(
        design_top=target.name,
        provenance=provenance,
        reset_candidates=candidates,
        reset_targets=targets,
        reset_domains=domains,
        domain_crossings=crossings,
        reset_graph=graph,
        candidate_sva=sva,
        risks=risks,
        ambiguities=ambiguities,
        recommendations=recs,
    )


def _select_module(modules: list[ParsedModule]) -> ParsedModule:
    for m in modules:
        if any(b.is_edge_sensitive for b in m.always_blocks):
            return m
    return modules[0]


def analyze_rtl_file(path: str | Path, command: str = "") -> ResetIntentManifest:
    p = Path(path)
    text = p.read_text()
    modules = parse_text(text, p.name)
    prov = _build_provenance([p.name], {p.name: _sha256(text)}, command)
    return _analyze(modules, prov)


def analyze_rtl_text(
    text: str, filename: str = "input.sv", command: str = ""
) -> ResetIntentManifest:
    modules = parse_text(text, filename)
    prov = _build_provenance([filename], {filename: _sha256(text)}, command)
    return _analyze(modules, prov)


def analyze_manifest_file(path: str | Path, command: str = "") -> ResetIntentManifest:
    p = Path(path)
    text = p.read_text()
    data: dict[str, Any] = json.loads(text)
    modules = parsed_modules_from_manifest(data)
    prov = _build_provenance([p.name], {p.name: _sha256(text)}, command)
    return _analyze(modules, prov)
