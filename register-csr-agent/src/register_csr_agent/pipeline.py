"""End-to-end pipeline: sources -> normalized manifest -> verification package."""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import __version__
from .checks import run_all_checks
from .generators import (
    build_coverage,
    build_review_checklist,
    generate_directed_tests,
    generate_sva,
)
from .grounding import ground
from .llm_adapter import MockLLM, annotate_discrepancies
from .models import (
    GroundingReport,
    Provenance,
    RegisterMap,
    RtlSymbolTable,
    VerificationPackage,
)
from .parsers import load_register_map
from .rtl_symbols import load_rtl_symbols


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_package(
    rmap: RegisterMap,
    rtl: RtlSymbolTable | None = None,
    *,
    provenance: Provenance | None = None,
    explain: bool = True,
) -> VerificationPackage:
    """Assemble a full verification package from an already-loaded manifest."""
    if rtl is not None:
        grounding = ground(rmap, rtl)
    else:
        grounding = GroundingReport(total_count=len(rmap.registers))

    discrepancies = run_all_checks(rmap, rtl, grounding if rtl is not None else None)
    if explain:
        annotate_discrepancies(discrepancies, MockLLM())

    sva = generate_sva(rmap)
    tests = generate_directed_tests(rmap)
    coverage = build_coverage(rmap, sva, tests)
    checklist = build_review_checklist(rmap)

    return VerificationPackage(
        provenance=provenance or Provenance(tool_version=__version__),
        register_map=rmap,
        grounding=grounding,
        discrepancies=discrepancies,
        candidate_sva=sva,
        directed_tests=tests,
        coverage=coverage,
        review_checklist=checklist,
    )


def run_from_files(
    map_path: str | Path,
    rtl_path: str | Path | None = None,
    *,
    fmt: str | None = None,
    command: str = "",
    explain: bool = True,
) -> VerificationPackage:
    """Load sources from disk and build the package with provenance."""
    map_path = Path(map_path)
    rmap = load_register_map(map_path, fmt)
    rtl: RtlSymbolTable | None = None
    input_files = [str(map_path)]
    input_sha = {str(map_path): _sha256(map_path)}
    if rtl_path is not None:
        rtl_path = Path(rtl_path)
        rtl = load_rtl_symbols(rtl_path)
        input_files.append(str(rtl_path))
        input_sha[str(rtl_path)] = _sha256(rtl_path)

    prov = Provenance(
        tool_version=__version__,
        command=command,
        input_files=input_files,
        input_sha256=input_sha,
    )
    return build_package(rmap, rtl, provenance=prov, explain=explain)
