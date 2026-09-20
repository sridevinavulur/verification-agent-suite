"""Deterministic grounding: map manifest register/field names onto RTL symbols.

Matching is purely lexical and conservative:
* exact name match, or
* normalized match (lowercased, non-alphanumeric stripped).

The tool NEVER guesses a mapping by width/reset similarity, and never invents a
symbol. Unmatched names are reported explicitly. An LLM may later *explain* an
unmatched name, but cannot assert a mapping the deterministic layer rejected.
"""

from __future__ import annotations

import re

from .models import GroundingReport, GroundingResult, RegisterMap, RtlSymbolTable


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def ground(rmap: RegisterMap, rtl: RtlSymbolTable) -> GroundingReport:
    by_exact = rtl.by_name()
    by_norm: dict[str, str] = {}
    for s in rtl.symbols:
        by_norm.setdefault(_normalize(s.name), s.name)

    results: list[GroundingResult] = []
    matched_rtl: set[str] = set()

    # ground each register (fields inherit register grounding for this v0.1 scope)
    for reg in rmap.registers:
        if reg.name in by_exact:
            results.append(
                GroundingResult(
                    manifest_name=reg.name,
                    rtl_symbol=reg.name,
                    matched=True,
                    match_kind="exact",
                )
            )
            matched_rtl.add(reg.name)
            continue
        norm = _normalize(reg.name)
        if norm in by_norm:
            sym = by_norm[norm]
            results.append(
                GroundingResult(
                    manifest_name=reg.name,
                    rtl_symbol=sym,
                    matched=True,
                    match_kind="normalized",
                    notes=f"matched {reg.name!r} ~ {sym!r} by normalized name",
                )
            )
            matched_rtl.add(sym)
            continue
        results.append(
            GroundingResult(
                manifest_name=reg.name,
                matched=False,
                match_kind="none",
                notes="no exact or normalized RTL symbol found",
            )
        )

    matched = [r for r in results if r.matched]
    unmatched_manifest = [r.manifest_name for r in results if not r.matched]
    unmatched_rtl = sorted(
        s.name
        for s in rtl.symbols
        if s.name not in matched_rtl and s.kind.value == "register"
    )
    return GroundingReport(
        results=results,
        matched_count=len(matched),
        total_count=len(results),
        unmatched_manifest=unmatched_manifest,
        unmatched_rtl=unmatched_rtl,
    )
