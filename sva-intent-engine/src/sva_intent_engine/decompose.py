"""Requirement decomposition module (spec 5.4).

Deterministic rules split a compound requirement into atomic clauses, classify
each clause, and flag vague terms. The module NEVER infers a signal name or a
cycle bound -- if a bound is not written literally in the text, ``min_delay`` /
``max_delay`` stay ``None`` and the clause is flagged.

Design:
    * Sentence/clause splitting on ``.``, ``;`` and coordinating "and" that
      joins independent clauses.
    * Keyword-driven classification into the five ClauseKind buckets.
    * Trigger/consequent extraction from "when/if/whenever ... , ..." shapes.
    * Cycle-bound extraction ONLY from explicit numeric phrases
      ("within 3 cycles", "after 2 cycles", "in 1 to 3 cycles").
    * Vague-term detection.
"""

from __future__ import annotations

import re

from .models import (
    AtomicClause,
    ClauseKind,
    DecompositionResult,
    Provenance,
    Requirement,
    Severity,
    SourceSpan,
)

# Vague terms that make a requirement unverifiable without clarification.
VAGUE_TERMS: tuple[str, ...] = (
    "soon",
    "eventually",
    "correct",
    "correctly",
    "safe",
    "safely",
    "properly",
    "when possible",
    "as needed",
    "appropriately",
    "reasonable",
    "fast enough",
)

# Keyword sets for classification.
_ASSUME_MARKERS = ("assume", "environment guarantees", "it is assumed", "the input")
_COVER_MARKERS = ("cover", "should be able to reach", "must be reachable", "exercise")
_GUARANTEE_MARKERS = ("must", "shall", "always", "never", "guarantee", "grant", "assert")
_UNSUPPORTED_MARKERS = (
    "throughput",
    "bandwidth",
    "power",
    "temperature",
    "frequency in mhz",
    "analog",
)

# Trigger connectives.
_TRIGGER_RE = re.compile(
    r"\b(?:when(?:ever)?|if|upon|after)\b\s+(?P<trig>.+?)"
    r"(?:,|\bthen\b|\bmust\b|\bshall\b|\bwill\b)",
    re.IGNORECASE,
)

# Explicit numeric cycle bounds. NEVER guess -- only match literal numbers.
_RANGE_RE = re.compile(
    r"\bwithin\s+(?P<lo>\d+)\s+to\s+(?P<hi>\d+)\s+cycles?", re.IGNORECASE
)
_RANGE_RE2 = re.compile(
    r"\bin\s+(?P<lo>\d+)\s+to\s+(?P<hi>\d+)\s+cycles?", re.IGNORECASE
)
_WITHIN_RE = re.compile(r"\bwithin\s+(?P<hi>\d+)\s+cycles?", re.IGNORECASE)
_AFTER_RE = re.compile(r"\bafter\s+(?P<n>\d+)\s+cycles?", re.IGNORECASE)
_NEXT_CYCLE_RE = re.compile(r"\b(?:on\s+the\s+)?next\s+cycle\b", re.IGNORECASE)

_UNLESS_RE = re.compile(r"\bunless\b\s+(?P<guard>.+?)(?:\.|$)", re.IGNORECASE)


def _find_span(text: str, fragment: str) -> SourceSpan:
    idx = text.find(fragment)
    if idx < 0:
        idx = 0
    return SourceSpan(start=idx, end=idx + len(fragment), text=fragment)


def _split_clauses(text: str) -> list[str]:
    """Split on sentence terminators and semicolons. Keep it conservative."""
    parts = re.split(r"[.;]\s+|;", text)
    return [p.strip() for p in parts if p.strip()]


def _detect_vague(fragment: str) -> list[str]:
    low = fragment.lower()
    return [t for t in VAGUE_TERMS if re.search(rf"\b{re.escape(t)}\b", low)]


def _classify(fragment: str) -> ClauseKind:
    low = fragment.lower()
    if any(m in low for m in _UNSUPPORTED_MARKERS):
        return ClauseKind.UNSUPPORTED
    if any(m in low for m in _COVER_MARKERS):
        return ClauseKind.COVER_OBJECTIVE
    if any(m in low for m in _ASSUME_MARKERS):
        return ClauseKind.ENVIRONMENT_ASSUMPTION
    if any(m in low for m in _GUARANTEE_MARKERS):
        return ClauseKind.DESIGN_GUARANTEE
    return ClauseKind.AMBIGUITY


def _extract_bounds(fragment: str) -> tuple[int | None, int | None, str | None]:
    """Return (min_delay, max_delay, timing_relation) from LITERAL text only."""
    m = _RANGE_RE.search(fragment) or _RANGE_RE2.search(fragment)
    if m:
        return int(m.group("lo")), int(m.group("hi")), "bounded_response"
    m = _WITHIN_RE.search(fragment)
    if m:
        return 0, int(m.group("hi")), "bounded_response"
    m = _AFTER_RE.search(fragment)
    if m:
        n = int(m.group("n"))
        return n, n, "fixed_delay"
    if _NEXT_CYCLE_RE.search(fragment):
        return 1, 1, "next_cycle"
    return None, None, None


def _extract_trigger_consequent(
    fragment: str,
) -> tuple[str | None, str | None]:
    m = _TRIGGER_RE.search(fragment)
    if not m:
        return None, None
    trigger = m.group("trig").strip().rstrip(",")
    consequent = fragment[m.end() :].strip()
    # Trim trailing "unless ..." from the consequent -- it is a guard.
    consequent = _UNLESS_RE.sub("", consequent).strip().rstrip(".,")
    return trigger or None, consequent or None


def _extract_guard(fragment: str) -> str | None:
    m = _UNLESS_RE.search(fragment)
    if m:
        return m.group("guard").strip().rstrip(".")
    return None


def _referenced_terms(fragment: str) -> list[str]:
    """Extract candidate domain terms (identifier-like tokens).

    These are the raw *terms* to be grounded later; this does NOT choose a
    signal name -- it only surfaces words the grounding engine must resolve.
    """
    # Identifiers only (snake_case / dotted). Trailing punctuation is trimmed by
    # the regex boundary. This surfaces candidate *terms*; it does not choose a
    # signal -- grounding decides resolution.
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*", fragment)
    stop = {
        "the", "a", "an", "is", "are", "be", "to", "of", "and", "or", "must",
        "shall", "when", "whenever", "if", "then", "within", "after", "cycles",
        "cycle", "unless", "on", "next", "in", "with", "that", "it", "its",
        "for", "each", "value", "high", "low", "asserted", "deasserted",
        "arrive", "arrives", "assert", "asserts", "state", "condition",
        "design", "never", "always", "allow", "allows", "equals", "equal",
        "maximum", "minimum", "zero", "during", "goes",
        "become", "becomes", "remain", "remains", "while",
        "reach", "reaches", "reachable", "should", "will",
        "completes", "complete", "granted",
        "reset", "clock", "posedge", "negedge",
    }
    seen: list[str] = []
    for tok in raw:
        low = tok.lower()
        if low in stop or len(tok) < 2:
            continue
        if tok not in seen:
            seen.append(tok)
    return seen


def decompose(
    requirement: Requirement, *, git_sha: str = "UNKNOWN", command: str | None = None
) -> DecompositionResult:
    """Decompose a requirement into classified atomic clauses (spec 5.4)."""
    clauses: list[AtomicClause] = []
    fragments = _split_clauses(requirement.source_text)

    for i, frag in enumerate(fragments):
        vague = _detect_vague(frag)
        kind = _classify(frag)
        # A vague term forces an ambiguity classification unless it is clearly
        # unsupported (unsupported is a stronger stop).
        if vague and kind != ClauseKind.UNSUPPORTED:
            kind = ClauseKind.AMBIGUITY

        trigger, consequent = _extract_trigger_consequent(frag)
        min_d, max_d, timing = _extract_bounds(frag)
        guard = _extract_guard(frag)
        terms = _referenced_terms(frag)

        severity = Severity.INFO
        rationale_bits: list[str] = [f"classified as {kind.value}"]
        if vague:
            severity = Severity.WARNING
            rationale_bits.append(f"vague terms flagged: {', '.join(vague)}")
        if kind == ClauseKind.UNSUPPORTED:
            severity = Severity.ERROR
            rationale_bits.append("performance/analog concern outside SVA scope")
        if timing:
            rationale_bits.append(f"explicit timing: {timing} [{min_d},{max_d}]")
        else:
            rationale_bits.append("no explicit cycle bound in text (not inferred)")

        confidence = 0.85
        if kind == ClauseKind.AMBIGUITY:
            confidence = 0.4
        elif kind == ClauseKind.UNSUPPORTED:
            confidence = 0.2

        clauses.append(
            AtomicClause(
                clause_id=f"{requirement.requirement_id}.c{i}",
                requirement_id=requirement.requirement_id,
                kind=kind,
                source_span=_find_span(requirement.source_text, frag),
                trigger=trigger,
                consequent=consequent,
                timing_relation=timing,
                min_delay=min_d,
                max_delay=max_d,
                clock=None,  # never inferred here
                reset_behavior=None,  # never inferred here
                guard=guard,
                severity=severity,
                referenced_terms=terms,
                vague_terms=vague,
                confidence=confidence,
                rationale="; ".join(rationale_bits),
            )
        )

    prov = Provenance(
        stage="decompose",
        git_sha=git_sha,
        command=command,
        input_hashes={"requirement": requirement.requirement_id},
    )
    return DecompositionResult(
        requirement=requirement, clauses=clauses, provenance=prov
    )
