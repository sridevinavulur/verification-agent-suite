"""Pipeline orchestration: build TemporalIntent from grounded clauses,
generate candidate properties, and assemble review reports.

This wires together decompose -> ground -> intent -> render -> validate. All
steps are deterministic. The LLM adapter is never on the critical path.

Key safety behavior:
    * If a clause has unresolved terms (grounding not complete), NO temporal
      intent is emitted for it -- SVA emission stops (spec 5.5 rule 5).
    * property_form is chosen deterministically from clause structure; if the
      structure is insufficient (e.g. missing bound for a bounded response),
      the clause is skipped with a recorded ambiguity.
"""

from __future__ import annotations

import hashlib

from .decompose import decompose
from .expr_normalize import normalize
from .grounding import ground_clause
from .models import (
    AtomicClause,
    CandidateProperty,
    ClauseKind,
    DecompositionResult,
    GroundingResult,
    ImplicationStyle,
    PropertyForm,
    PropertyKind,
    Provenance,
    Requirement,
    ReviewChecklistItem,
    ReviewReport,
    RTLManifest,
    Severity,
    SymbolRef,
    TemporalIntent,
    TemporalStrength,
    ValidationCheck,
    ValidationReport,
)
from .renderer import RenderError, render_property, validate_intent

NON_CLAIMS = [
    "A rendered property is a CANDIDATE, not a verified property.",
    "This tool does not prove semantic correctness, completeness, or signoff.",
    "Clock/reset/bounds are never inferred; missing detail blocks emission.",
    "Grounding is deterministic and lexical; it does not understand design intent.",
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _kind_for_clause(clause: AtomicClause) -> PropertyKind | None:
    if clause.kind == ClauseKind.DESIGN_GUARANTEE:
        return PropertyKind.ASSERT
    if clause.kind == ClauseKind.ENVIRONMENT_ASSUMPTION:
        return PropertyKind.ASSUME
    if clause.kind == ClauseKind.COVER_OBJECTIVE:
        return PropertyKind.COVER
    return None  # ambiguity / unsupported -> no emission


def _choose_form(clause: AtomicClause) -> tuple[PropertyForm | None, list[str]]:
    """Deterministically choose a property form from clause structure.

    Returns (form, ambiguities). Uses only structure the decomposer extracted;
    never guesses bounds.
    """
    amb: list[str] = []
    text = clause.source_span.text.lower()

    if clause.kind == ClauseKind.COVER_OBJECTIVE:
        if clause.max_delay is not None:
            return PropertyForm.EVENTUALLY_WITHIN_BOUND, amb
        amb.append("cover objective without explicit bound -> not emitted")
        return None, amb

    # Structural keyword hints (deterministic).
    if "overflow" in text:
        return PropertyForm.NO_OVERFLOW, amb
    if "underflow" in text:
        return PropertyForm.NO_UNDERFLOW, amb
    if "one-hot" in text or "one hot" in text or "onehot" in text:
        return PropertyForm.ONE_HOT, amb
    if "reset" in text and clause.consequent is None and clause.trigger is None:
        return PropertyForm.RESET_STATE, amb
    if "stable" in text and ("stall" in text or "stalled" in text):
        return PropertyForm.STABLE_WHILE_STALLED, amb

    # Implication-shaped.
    if clause.trigger is not None and clause.consequent is not None:
        if clause.timing_relation == "bounded_response":
            if clause.min_delay is not None and clause.max_delay is not None:
                return PropertyForm.BOUNDED_RESPONSE, amb
            amb.append("bounded response without explicit bound -> not emitted")
            return None, amb
        if clause.timing_relation == "next_cycle":
            return PropertyForm.NEXT_CYCLE, amb
        if clause.timing_relation == "fixed_delay":
            # fixed delay N == bounded [N:N]
            return PropertyForm.BOUNDED_RESPONSE, amb
        return PropertyForm.IMPLICATION, amb

    # Bare invariant (must/always with a single condition).
    if clause.consequent is not None or "always" in text or "never" in text:
        return PropertyForm.INVARIANT, amb

    amb.append("clause structure insufficient to choose a property form")
    return None, amb


def _best_symbol_ref(term: str, grounding: GroundingResult) -> SymbolRef | None:
    for tg in grounding.term_groundings:
        if tg.term == term and tg.matches:
            m = tg.matches[0]
            return SymbolRef(
                symbol_id=m.symbol_id, name=m.symbol_name, file=m.file, line=m.line
            )
    return None


def _first_resolved_term(clause: AtomicClause, resolved: set[str]) -> str | None:
    for term in clause.referenced_terms:
        if term in resolved:
            return term
    return None


def _build_expressions(
    clause: AtomicClause, form: PropertyForm, resolved: set[str]
) -> tuple[str | None, str | None, list[str]]:
    """Deterministically build (antecedent, consequent) SV expressions.

    Uses only grounded signal names. Records an ambiguity for any phrase that
    cannot be normalized -- which causes downstream rejection (no emission).
    """
    amb: list[str] = []

    def norm(phrase: str | None, role: str) -> str | None:
        if phrase is None:
            return None
        expr, reason = normalize(phrase, resolved)
        if expr is None:
            amb.append(f"could not normalize {role}: {reason}")
        return expr

    if form in (PropertyForm.RESET_STATE,):
        # consequent = "<sig> == 0" from the single resolved data term.
        sig = _first_resolved_term(clause, resolved)
        if sig is None:
            amb.append("reset_state: no grounded state signal")
            return None, None, amb
        return None, f"{sig} == 0", amb

    if form in (PropertyForm.INVARIANT,):
        cons = norm(clause.consequent or clause.source_span.text, "invariant")
        return None, cons, amb

    if form in (PropertyForm.ONE_HOT,):
        sig = _first_resolved_term(clause, resolved)
        if sig is None:
            amb.append("one_hot: no grounded vector signal")
        return None, sig, amb

    # Implication-shaped forms.
    ante = norm(clause.trigger, "antecedent")
    cons = norm(clause.consequent, "consequent")
    return ante, cons, amb


def build_intent(
    clause: AtomicClause,
    grounding: GroundingResult,
    *,
    git_sha: str = "UNKNOWN",
) -> TemporalIntent | None:
    """Build a TemporalIntent from a clause + grounding, or None if blocked.

    Blocking conditions (return None):
        * clause is ambiguity/unsupported
        * grounding has unresolved terms (STOP emission)
        * no property form can be chosen
    """
    if not grounding.fully_resolved:
        return None

    kind = _kind_for_clause(clause)
    if kind is None:
        return None

    form, ambiguities = _choose_form(clause)
    if form is None:
        return None

    ambiguities = list(ambiguities)
    for tg in grounding.term_groundings:
        if tg.ambiguous:
            ambiguities.append(
                f"term '{tg.term}' has multiple equally-ranked matches"
            )

    refs = [
        ref
        for term in clause.referenced_terms
        if (ref := _best_symbol_ref(term, grounding)) is not None
    ]

    style = ImplicationStyle.OVERLAPPING
    if clause.timing_relation in ("next_cycle",):
        style = ImplicationStyle.NON_OVERLAPPING

    # Resolved signal names (best match per resolved term).
    resolved = {
        tg.matches[0].symbol_name for tg in grounding.term_groundings if tg.matches
    }

    antecedent, consequent, expr_amb = _build_expressions(clause, form, resolved)
    ambiguities.extend(expr_amb)

    prov = Provenance(
        stage="intent",
        git_sha=git_sha,
        input_hashes={"clause": clause.clause_id},
    )
    intent = TemporalIntent(
        requirement_id=clause.requirement_id,
        clause_id=clause.clause_id,
        source_text=clause.source_span.text,
        design_top=grounding.design_top,
        property_kind=kind,
        property_form=form,
        render_template_id=form.value,
        clock_signal=grounding.clock_reset.clock_signal,
        reset_signal=grounding.clock_reset.reset_signal,
        reset_polarity=grounding.clock_reset.reset_polarity,
        antecedent=antecedent,
        consequent=consequent,
        implication_style=style,
        min_delay=clause.min_delay,
        max_delay=clause.max_delay,
        temporal_strength=TemporalStrength.WEAK,
        environmental_assumptions=[],
        referenced_symbols=refs,
        ambiguities=ambiguities,
        confidence=clause.confidence,
        provenance=prov,
    )
    return intent


def validate_and_render(
    intent: TemporalIntent, *, git_sha: str = "UNKNOWN"
) -> ValidationReport:
    """Run static validation and render if all error-level checks pass."""
    checks = validate_intent(intent)
    emit = all(c.passed for c in checks if c.severity == Severity.ERROR)
    candidate: CandidateProperty | None = None
    if emit:
        try:
            candidate = render_property(intent, git_sha=git_sha)
        except RenderError as exc:
            emit = False
            checks.append(
                ValidationCheck(
                    check="render",
                    passed=False,
                    severity=Severity.ERROR,
                    detail=str(exc),
                )
            )
    prov = Provenance(
        stage="validate",
        git_sha=git_sha,
        input_hashes={"clause": intent.clause_id},
    )
    return ValidationReport(
        requirement_id=intent.requirement_id,
        clause_id=intent.clause_id,
        checks=checks,
        emitted=emit,
        candidate=candidate,
        provenance=prov,
    )


def _checklist(
    decomp: DecompositionResult,
    groundings: list[GroundingResult],
    validations: list[ValidationReport],
) -> list[ReviewChecklistItem]:
    items: list[ReviewChecklistItem] = []
    amb = sum(1 for c in decomp.clauses if c.kind == ClauseKind.AMBIGUITY)
    items.append(
        ReviewChecklistItem(
            item="All vague/ambiguous clauses resolved with a human",
            status="ok" if amb == 0 else "needs_attention",
        )
    )
    unresolved = any(not g.fully_resolved for g in groundings)
    items.append(
        ReviewChecklistItem(
            item="Every referenced term grounded to an RTL symbol",
            status="needs_attention" if unresolved else "ok",
        )
    )
    items.append(
        ReviewChecklistItem(
            item="Clock and reset selection reviewed against manifest evidence"
        )
    )
    items.append(
        ReviewChecklistItem(item="Reset polarity and semantics confirmed by reviewer")
    )
    emitted = sum(1 for v in validations if v.emitted)
    items.append(
        ReviewChecklistItem(
            item=f"Candidate properties independently validated ({emitted} emitted)"
        )
    )
    items.append(
        ReviewChecklistItem(
            item="Confirm rendered != verified; run formal/sim before signoff"
        )
    )
    return items


def run_full(
    requirement: Requirement,
    manifest: RTLManifest,
    *,
    run_id: str | None = None,
    glossary: dict[str, str] | None = None,
    git_sha: str = "UNKNOWN",
    command: str | None = None,
) -> ReviewReport:
    """End-to-end deterministic run for a single requirement."""
    run_id = run_id or f"run-{_hash(requirement.source_text)}"
    decomp = decompose(requirement, git_sha=git_sha, command=command)

    groundings: list[GroundingResult] = []
    intents: list[TemporalIntent] = []
    validations: list[ValidationReport] = []

    for clause in decomp.clauses:
        g = ground_clause(
            clause, manifest, glossary=glossary, git_sha=git_sha, command=command
        )
        groundings.append(g)
        intent = build_intent(clause, g, git_sha=git_sha)
        if intent is None:
            continue
        intents.append(intent)
        validations.append(validate_and_render(intent, git_sha=git_sha))

    prov = Provenance(
        stage="run_full",
        git_sha=git_sha,
        command=command,
        input_hashes={
            "requirement": _hash(requirement.source_text),
            "manifest": _hash(manifest.model_dump_json()),
        },
    )
    return ReviewReport(
        run_id=run_id,
        requirement=requirement,
        decomposition=decomp,
        groundings=groundings,
        intents=intents,
        validations=validations,
        checklist=_checklist(decomp, groundings, validations),
        non_claims=NON_CLAIMS,
        provenance=prov,
    )
