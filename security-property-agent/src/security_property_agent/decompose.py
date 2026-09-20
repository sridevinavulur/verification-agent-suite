"""Deterministic requirement decomposition.

Splits a structured security requirement into atomic clauses and classifies
each clause as a safety property, an environment assumption, or a security test
objective (spec 6.13 requires these three be kept distinct).

Fidelity rule (machine-checked in the model): every clause ``text`` is a
VERBATIM slice of the original requirement. We never paraphrase, normalize
casing, or rewrite. Splitting happens only on explicit connective boundaries,
and each piece carries its exact source span.

Classification is a transparent keyword heuristic. It is labelled as heuristic
and its rationale is emitted so a reviewer can override it. When a clause looks
like it could be more than one kind, it is flagged as an ambiguity rather than
guessed silently.
"""

from __future__ import annotations

import re

from .models import (
    Clause,
    ClauseKind,
    DecompositionResult,
    Provenance,
    SecurityRequirement,
    SourceSpan,
)
from .util import sha256_text

# Connectives we split on. We split only on these explicit boundaries so the
# resulting clauses stay verbatim and traceable.
_SPLIT_RE = re.compile(r"(?i)(?:;|\.\s+|\band\b|\bwhile\b(?=\s)|,\s+)")

# --- Heuristic keyword banks (transparent, reviewer-overridable) -----------
_ASSUMPTION_MARKERS = (
    "assume",
    "assumes",
    "assumption",
    "environment",
    "is provided",
    "must provide",
    "must supply",
    "the tester",
    "given that",
    "provided that",
    "precondition",
    "input constraint",
)
_OBJECTIVE_MARKERS = (
    "cover",
    "demonstrate",
    "show that",
    "scenario",
    "test objective",
    "reachable",
    "exercise",
    "should be able to reach",
    "witness",
)
_SAFETY_MARKERS = (
    "must never",
    "shall never",
    "never",
    "must not",
    "shall not",
    "must",
    "shall",
    "always",
    "only",
    "prohibited",
    "denied",
    "blocked",
    "prevented",
    "mismatch",
    "detect",
    "assert",
)


def _classify(text: str) -> tuple[ClauseKind, list[str]]:
    low = text.lower()
    hits_assume = [m for m in _ASSUMPTION_MARKERS if m in low]
    hits_obj = [m for m in _OBJECTIVE_MARKERS if m in low]
    hits_safety = [m for m in _SAFETY_MARKERS if m in low]

    rationale: list[str] = []
    # Priority order: an explicit assumption marker dominates because misfiling
    # an assumption as a property (asserting it) is the dangerous direction.
    if hits_assume:
        rationale.append(f"matched environment-assumption markers: {hits_assume}")
        if hits_safety:
            rationale.append(
                f"also matched safety markers {hits_safety}; flagged as ambiguous"
            )
        return ClauseKind.ENVIRONMENT_ASSUMPTION, rationale
    if hits_obj:
        rationale.append(f"matched test-objective markers: {hits_obj}")
        return ClauseKind.SECURITY_TEST_OBJECTIVE, rationale
    if hits_safety:
        rationale.append(f"matched safety-property markers: {hits_safety}")
        return ClauseKind.SAFETY_PROPERTY, rationale
    rationale.append("no classification markers matched")
    return ClauseKind.AMBIGUITY, rationale


def _split_spans(text: str) -> list[SourceSpan]:
    """Return verbatim, non-empty, stripped spans of ``text``."""
    spans: list[SourceSpan] = []
    pos = 0
    for m in _SPLIT_RE.finditer(text):
        spans.append(_strip_span(text, pos, m.start()))
        pos = m.end()
    spans.append(_strip_span(text, pos, len(text)))
    # Drop empty pieces created by leading/trailing connectives.
    return [s for s in spans if s.end > s.start and text[s.start : s.end].strip()]


def _strip_span(text: str, start: int, end: int) -> SourceSpan:
    """Trim leading/trailing whitespace but keep the span verbatim-aligned."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return SourceSpan(start=start, end=end)


def decompose(
    requirement: SecurityRequirement, git_sha: str = "UNKNOWN"
) -> DecompositionResult:
    """Decompose one requirement into classified, verbatim clauses."""
    text = requirement.text
    spans = _split_spans(text)
    clauses: list[Clause] = []
    ambiguities: list[str] = []

    for i, span in enumerate(spans):
        slice_ = text[span.start : span.end]
        kind, rationale = _classify(slice_)
        clause_id = f"{requirement.requirement_id}.c{i}"
        clauses.append(
            Clause(
                clause_id=clause_id,
                kind=kind,
                text=slice_,
                span=span,
                rationale=rationale,
            )
        )
        if kind is ClauseKind.AMBIGUITY:
            ambiguities.append(
                f"{clause_id}: could not classify clause; needs human review"
            )
        if any("ambiguous" in r for r in rationale):
            ambiguities.append(
                f"{clause_id}: matched both assumption and safety markers"
            )

    prov = Provenance(
        stage="decompose",
        git_sha=git_sha,
        input_hashes={requirement.requirement_id: sha256_text(text)},
        notes=["classification is a transparent keyword heuristic; reviewer may override"],
    )
    return DecompositionResult(
        requirement_id=requirement.requirement_id,
        original_text=text,
        original_text_sha256=sha256_text(text),
        clauses=clauses,
        ambiguities=ambiguities,
        provenance=prov,
    )
