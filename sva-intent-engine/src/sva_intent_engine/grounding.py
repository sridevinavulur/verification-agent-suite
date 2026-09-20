"""RTL symbol-grounding engine (spec 5.5).

Deterministic, ranked mapping of requirement terms to RTL manifest symbols.

Rules enforced here:
    1. Exact name match ranks above alias match.
    2. Alias match requires the alias to be listed on the symbol (lexical
       evidence) or supplied via a glossary.
    3. Multiple equally-good matches are KEPT (never silently collapsed to one).
    4. Terms with no match are recorded in ``unresolved_terms``; a downstream
       caller must STOP SVA emission when anything is unresolved.
    5. Clock/reset selection cites exact manifest entries; polarity is only set
       when the manifest provides evidence, otherwise it stays UNKNOWN.
"""

from __future__ import annotations

from .models import (
    AtomicClause,
    ClockResetSelection,
    GroundingResult,
    MatchKind,
    Provenance,
    ResetPolarity,
    RTLManifest,
    RTLSymbol,
    SymbolMatch,
    TermGrounding,
)

EXACT_SCORE = 1.0
ALIAS_SCORE = 0.7
CASE_INSENSITIVE_SCORE = 0.85


def _match_term(
    term: str, manifest: RTLManifest, glossary: dict[str, str]
) -> list[SymbolMatch]:
    """Return ranked matches for a single term."""
    matches: list[SymbolMatch] = []

    # Glossary can rewrite a requirement term to a design term (alias evidence).
    glossed = glossary.get(term)

    for sym in manifest.symbols:
        # 1. exact name match
        if sym.name == term or (glossed is not None and sym.name == glossed):
            ev = "exact name match"
            if glossed is not None and sym.name == glossed:
                ev = f"glossary alias '{term}' -> '{glossed}' exact match"
            matches.append(
                SymbolMatch(
                    symbol_id=sym.symbol_id,
                    symbol_name=sym.name,
                    match_kind=MatchKind.EXACT,
                    score=EXACT_SCORE,
                    evidence=ev,
                    file=sym.file,
                    line=sym.line,
                )
            )
            continue
        # 2. case-insensitive name match (lexical evidence, below exact)
        if sym.name.lower() == term.lower():
            matches.append(
                SymbolMatch(
                    symbol_id=sym.symbol_id,
                    symbol_name=sym.name,
                    match_kind=MatchKind.ALIAS,
                    score=CASE_INSENSITIVE_SCORE,
                    evidence=f"case-insensitive match on '{term}'",
                    file=sym.file,
                    line=sym.line,
                )
            )
            continue
        # 3. alias list match (requires alias listed on the symbol)
        alias_hit = term in sym.aliases or (
            glossed is not None and glossed in sym.aliases
        )
        if alias_hit:
            matches.append(
                SymbolMatch(
                    symbol_id=sym.symbol_id,
                    symbol_name=sym.name,
                    match_kind=MatchKind.ALIAS,
                    score=ALIAS_SCORE,
                    evidence=f"alias list contains '{term}'",
                    file=sym.file,
                    line=sym.line,
                )
            )

    # Stable, deterministic ordering: score desc, then symbol_id asc.
    matches.sort(key=lambda m: (-m.score, m.symbol_id))
    return matches


def _select_clock(
    clause: AtomicClause, manifest: RTLManifest
) -> tuple[str | None, str | None]:
    # Only from explicit manifest clock candidates. Never invent.
    if clause.clock and clause.clock in {s.name for s in manifest.symbols}:
        return clause.clock, f"clause names clock '{clause.clock}'"
    if len(manifest.clock_candidates) == 1:
        c = manifest.clock_candidates[0]
        return c, f"single clock candidate in manifest: '{c}'"
    if len(manifest.clock_candidates) > 1:
        # Ambiguous -- do not choose. Leave unset with evidence note.
        return None, (
            "multiple clock candidates; selection deferred: "
            + ", ".join(manifest.clock_candidates)
        )
    return None, "no clock candidate in manifest"


def _reset_polarity(sym: RTLSymbol | None) -> ResetPolarity:
    if sym is None:
        return ResetPolarity.UNKNOWN
    name = sym.name.lower()
    # Lexical evidence only; polarity remains UNKNOWN otherwise.
    if name.endswith("_n") or "rst_n" in name or "resetn" in name:
        return ResetPolarity.ACTIVE_LOW
    if sym.signal_type == "active_low":
        return ResetPolarity.ACTIVE_LOW
    if sym.signal_type == "active_high":
        return ResetPolarity.ACTIVE_HIGH
    return ResetPolarity.UNKNOWN


def _select_reset(
    manifest: RTLManifest,
) -> tuple[str | None, str | None, ResetPolarity]:
    if len(manifest.reset_candidates) == 1:
        name = manifest.reset_candidates[0]
        sym = manifest.by_name(name)
        return name, f"single reset candidate: '{name}'", _reset_polarity(sym)
    if len(manifest.reset_candidates) > 1:
        return None, (
            "multiple reset candidates; selection deferred: "
            + ", ".join(manifest.reset_candidates)
        ), ResetPolarity.UNKNOWN
    return None, "no reset candidate in manifest", ResetPolarity.UNKNOWN


def ground_clause(
    clause: AtomicClause,
    manifest: RTLManifest,
    *,
    glossary: dict[str, str] | None = None,
    git_sha: str = "UNKNOWN",
    command: str | None = None,
) -> GroundingResult:
    """Ground every referenced term of a clause against the RTL manifest."""
    glossary = glossary or {}
    term_groundings: list[TermGrounding] = []
    unresolved: list[str] = []

    for term in clause.referenced_terms:
        matches = _match_term(term, manifest, glossary)
        tg = TermGrounding(term=term, matches=matches)
        term_groundings.append(tg)
        if not tg.resolved:
            unresolved.append(term)

    clock, clock_ev = _select_clock(clause, manifest)
    reset, reset_ev, polarity = _select_reset(manifest)

    prov = Provenance(
        stage="ground",
        git_sha=git_sha,
        command=command,
        input_hashes={"clause": clause.clause_id, "design_top": manifest.design_top},
    )
    return GroundingResult(
        clause_id=clause.clause_id,
        requirement_id=clause.requirement_id,
        design_top=manifest.design_top,
        term_groundings=term_groundings,
        unresolved_terms=unresolved,
        clock_reset=ClockResetSelection(
            clock_signal=clock,
            clock_evidence=clock_ev,
            reset_signal=reset,
            reset_evidence=reset_ev,
            reset_polarity=polarity,
        ),
        provenance=prov,
    )


def grounding_report(result: GroundingResult) -> str:
    """Human-readable grounding report."""
    lines = [
        f"Grounding report for clause {result.clause_id}",
        f"  design_top: {result.design_top}",
        f"  fully_resolved: {result.fully_resolved}",
        "  terms:",
    ]
    for tg in result.term_groundings:
        status = "RESOLVED" if tg.resolved else "UNRESOLVED"
        amb = " (AMBIGUOUS)" if tg.ambiguous else ""
        lines.append(f"    - {tg.term}: {status}{amb}")
        for m in tg.matches:
            lines.append(
                f"        -> {m.symbol_name} [{m.match_kind.value}]"
                f" score={m.score:.2f} ({m.evidence})"
            )
    cr = result.clock_reset
    lines.append(f"  clock: {cr.clock_signal} ({cr.clock_evidence})")
    lines.append(
        f"  reset: {cr.reset_signal} polarity={cr.reset_polarity.value}"
        f" ({cr.reset_evidence})"
    )
    if result.unresolved_terms:
        lines.append(f"  UNRESOLVED (emission blocked): {result.unresolved_terms}")
    return "\n".join(lines)
