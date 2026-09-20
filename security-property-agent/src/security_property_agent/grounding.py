"""Evidence-based RTL grounding.

Maps requirement terms to RTL symbols using ONLY the canonical Manifest as
evidence. Rules enforced here (spec 6.13):

* No symbol is treated as resolved without a Manifest match (exact or a clearly
  labelled alias). Author-provided signal hints are still checked against the
  Manifest; a hint with no evidence becomes an unresolved term, not a mapping.
* Threat models / trust boundaries are never inferred. A declared boundary on
  the requirement is passed through as evidence; its absence produces an
  ambiguity note, never a fabricated boundary.
* Clock/reset come from the Manifest's own candidate lists (themselves
  heuristic upstream); we do not invent them.
"""

from __future__ import annotations

from .manifest import ManifestView
from .models import (
    GroundingResult,
    MatchKind,
    Provenance,
    SecurityRequirement,
    SymbolRef,
)
from .util import candidate_identifiers, sha256_text


def ground(
    requirement: SecurityRequirement,
    manifest: ManifestView,
    git_sha: str = "UNKNOWN",
) -> GroundingResult:
    """Ground one requirement's terms against the Manifest."""
    # Terms come from explicit author hints first, then prose candidates.
    terms: list[str] = []
    for t in requirement.signals:
        if t not in terms:
            terms.append(t)
    for t in candidate_identifiers(requirement.text):
        if t not in terms:
            terms.append(t)

    symbols: list[SymbolRef] = []
    unresolved: list[str] = []
    ambiguities: list[str] = []

    for term in terms:
        exact = manifest.find(term)
        if exact:
            if len(exact) > 1:
                ambiguities.append(
                    f"term '{term}' matches {len(exact)} symbols across modules "
                    f"{sorted({s.module for s in exact})}; needs disambiguation"
                )
            s = exact[0]
            symbols.append(
                SymbolRef(
                    term=term,
                    match_kind=MatchKind.EXACT,
                    module=s.module,
                    symbol=s.name,
                    kind=s.kind,
                    evidence=[f"manifest exact match: {s.module}.{s.name} ({s.kind})"],
                )
            )
            continue

        alias = manifest.find_alias(term)
        if alias:
            s = alias[0]
            symbols.append(
                SymbolRef(
                    term=term,
                    match_kind=MatchKind.ALIAS,
                    module=s.module,
                    symbol=s.name,
                    kind=s.kind,
                    evidence=[
                        f"heuristic alias match: {s.module}.{s.name} ({s.kind}); "
                        "low confidence, human confirmation required"
                    ],
                )
            )
            ambiguities.append(
                f"term '{term}' resolved only by heuristic alias to "
                f"{s.module}.{s.name}; confirm before use"
            )
            continue

        # Author explicitly named this signal but the Manifest has no evidence.
        if term in requirement.signals:
            unresolved.append(term)
            symbols.append(
                SymbolRef(
                    term=term,
                    match_kind=MatchKind.UNRESOLVED,
                    evidence=["author-declared signal not found in Manifest"],
                )
            )
        else:
            unresolved.append(term)

    if requirement.declared_trust_boundary is None:
        ambiguities.append(
            "no trust boundary declared on this requirement; the tool will NOT "
            "infer one. Any boundary-dependent property must be reviewed."
        )

    prov = Provenance(
        stage="grounding",
        git_sha=git_sha,
        input_hashes={requirement.requirement_id: sha256_text(requirement.text)},
        notes=[
            "grounding uses the canonical Manifest as the only symbol evidence",
            "alias matches are heuristic and flagged for human confirmation",
        ],
    )
    return GroundingResult(
        requirement_id=requirement.requirement_id,
        clock_candidates=list(manifest.clock_candidates),
        reset_candidates=list(manifest.reset_candidates),
        symbols=symbols,
        unresolved_terms=unresolved,
        ambiguities=ambiguities,
        provenance=prov,
    )
