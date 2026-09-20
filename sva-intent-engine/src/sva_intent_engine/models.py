"""Typed data contracts for sva-intent-engine.

All contracts are Pydantic v2 models that validate (not merely annotate). These
schemas are the stable interface between pipeline stages:

    requirement -> decomposition -> grounding -> temporal-intent IR
                -> candidate property -> validation report

Provenance is attached at each stage so a run can be audited end to end.

Safety note: none of these models infer signal names, clocks, resets, or cycle
bounds. Missing information is represented explicitly (``None`` / empty lists /
``ambiguities``) so downstream stages can *reject* rather than guess.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1.0"


class StrictModel(BaseModel):
    """Base model: reject unknown fields and validate on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class ClauseKind(str, Enum):
    """Classification of an atomic requirement clause (spec 5.4)."""

    DESIGN_GUARANTEE = "design_guarantee"
    ENVIRONMENT_ASSUMPTION = "environment_assumption"
    COVER_OBJECTIVE = "cover_objective"
    AMBIGUITY = "ambiguity"
    UNSUPPORTED = "unsupported"


class PropertyKind(str, Enum):
    """SVA property directive."""

    ASSERT = "assert"
    ASSUME = "assume"
    COVER = "cover"


class ImplicationStyle(str, Enum):
    """Overlapping (|->) vs non-overlapping (|=>) implication."""

    OVERLAPPING = "overlapping"
    NON_OVERLAPPING = "non_overlapping"


class TemporalStrength(str, Enum):
    STRONG = "strong"
    WEAK = "weak"


class ResetPolarity(str, Enum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class MatchKind(str, Enum):
    EXACT = "exact"
    ALIAS = "alias"


class PropertyForm(str, Enum):
    """Renderable candidate property forms (spec 5.6)."""

    INVARIANT = "invariant"
    IMPLICATION = "implication"
    BOUNDED_RESPONSE = "bounded_response"
    NEXT_CYCLE = "next_cycle"
    NO_OVERFLOW = "no_overflow"
    NO_UNDERFLOW = "no_underflow"
    ONE_HOT = "one_hot"
    STABLE_WHILE_STALLED = "stable_while_stalled"
    RESET_STATE = "reset_state"
    EVENTUALLY_WITHIN_BOUND = "eventually_within_bound"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
class Provenance(StrictModel):
    """Immutable-ish record of how an artifact was produced."""

    tool: str = "sva-intent-engine"
    tool_version: str = SCHEMA_VERSION
    stage: str
    git_sha: str = "UNKNOWN"
    input_hashes: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    seed: int | None = None
    model_provider: str | None = None
    model_name: str | None = None
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Requirement + decomposition (spec 5.4)
# ---------------------------------------------------------------------------
class SourceSpan(StrictModel):
    """Character span into the original requirement text."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def _check_order(self) -> SourceSpan:
        if self.end < self.start:
            raise ValueError("SourceSpan.end must be >= start")
        return self


class Requirement(StrictModel):
    """A raw natural-language requirement as ingested."""

    requirement_id: str
    source_text: str
    design_top: str | None = None
    origin_path: str | None = None


class AtomicClause(StrictModel):
    """One atomic clause extracted from a requirement (spec 5.4).

    Fields that cannot be determined deterministically are left ``None`` and
    the term is recorded in ``referenced_terms`` / ``ambiguities`` instead of
    being guessed.
    """

    clause_id: str
    requirement_id: str
    kind: ClauseKind
    source_span: SourceSpan
    trigger: str | None = None
    consequent: str | None = None
    timing_relation: str | None = None
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)
    clock: str | None = None
    reset_behavior: str | None = None
    guard: str | None = None
    severity: Severity = Severity.INFO
    referenced_terms: list[str] = Field(default_factory=list)
    vague_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    @model_validator(mode="after")
    def _check_delays(self) -> AtomicClause:
        if (
            self.min_delay is not None
            and self.max_delay is not None
            and self.max_delay < self.min_delay
        ):
            raise ValueError("max_delay must be >= min_delay")
        return self


class DecompositionResult(StrictModel):
    requirement: Requirement
    clauses: list[AtomicClause]
    provenance: Provenance


# ---------------------------------------------------------------------------
# RTL manifest + grounding (spec 5.5)
# ---------------------------------------------------------------------------
class RTLSymbol(StrictModel):
    """A symbol from the RTL Intent Manifest."""

    symbol_id: str
    name: str
    kind: str  # port | reg | wire | net | parameter | state | clock | reset
    direction: str | None = None  # input | output | inout
    width: int | None = Field(default=None, ge=1)
    signal_type: str | None = None
    hierarchy: str | None = None
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    aliases: list[str] = Field(default_factory=list)


class RTLManifest(StrictModel):
    """Minimal RTL Intent Manifest fixture consumed by the grounding engine."""

    design_top: str
    symbols: list[RTLSymbol]
    clock_candidates: list[str] = Field(default_factory=list)
    reset_candidates: list[str] = Field(default_factory=list)

    def by_name(self, name: str) -> RTLSymbol | None:
        for s in self.symbols:
            if s.name == name:
                return s
        return None


class SymbolMatch(StrictModel):
    """A ranked candidate mapping from a requirement term to an RTL symbol."""

    symbol_id: str
    symbol_name: str
    match_kind: MatchKind
    score: float = Field(ge=0.0, le=1.0)
    evidence: str
    file: str | None = None
    line: int | None = None


class TermGrounding(StrictModel):
    """All ranked matches for a single requirement term."""

    term: str
    matches: list[SymbolMatch] = Field(default_factory=list)
    resolved: bool = False
    ambiguous: bool = False

    @model_validator(mode="after")
    def _derive_flags(self) -> TermGrounding:
        # resolved iff at least one match; ambiguous iff >1 top-scoring match.
        # Use object.__setattr__ to avoid re-triggering validate_assignment.
        object.__setattr__(self, "resolved", len(self.matches) > 0)
        if len(self.matches) > 1:
            top = self.matches[0].score
            amb = sum(1 for m in self.matches if m.score == top) > 1
        else:
            amb = False
        object.__setattr__(self, "ambiguous", amb)
        return self

    def best(self) -> SymbolMatch | None:
        return self.matches[0] if self.matches else None


class ClockResetSelection(StrictModel):
    clock_signal: str | None = None
    clock_evidence: str | None = None
    reset_signal: str | None = None
    reset_evidence: str | None = None
    reset_polarity: ResetPolarity = ResetPolarity.UNKNOWN


class GroundingResult(StrictModel):
    """Output of the grounding engine for one clause (spec 5.5)."""

    clause_id: str
    requirement_id: str
    design_top: str
    term_groundings: list[TermGrounding]
    unresolved_terms: list[str] = Field(default_factory=list)
    clock_reset: ClockResetSelection = Field(default_factory=ClockResetSelection)
    provenance: Provenance

    @property
    def fully_resolved(self) -> bool:
        return len(self.unresolved_terms) == 0


# ---------------------------------------------------------------------------
# Temporal-intent IR (spec 5.3)
# ---------------------------------------------------------------------------
class SymbolRef(StrictModel):
    """A grounded symbol reference with source evidence."""

    symbol_id: str
    name: str
    file: str | None = None
    line: int | None = None


class ValidationCheck(StrictModel):
    check: str
    passed: bool
    severity: Severity = Severity.ERROR
    detail: str | None = None


class TemporalIntent(StrictModel):
    """Typed temporal-intent intermediate representation (spec 5.3).

    This is the deterministic contract handed to the renderer. It carries an
    explicit clock (or the renderer rejects it), explicit bounds, and the exact
    grounded symbols used.
    """

    requirement_id: str
    clause_id: str
    source_text: str
    design_top: str

    property_kind: PropertyKind
    property_form: PropertyForm
    render_template_id: str

    clock_signal: str | None = None
    reset_signal: str | None = None
    reset_polarity: ResetPolarity = ResetPolarity.UNKNOWN
    disable_condition: str | None = None

    antecedent: str | None = None
    consequent: str | None = None
    implication_style: ImplicationStyle | None = None
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)
    temporal_strength: TemporalStrength = TemporalStrength.WEAK

    environmental_assumptions: list[str] = Field(default_factory=list)
    referenced_symbols: list[SymbolRef] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reviewer_status: str = "unreviewed"
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _check_delays(self) -> TemporalIntent:
        if (
            self.min_delay is not None
            and self.max_delay is not None
            and self.max_delay < self.min_delay
        ):
            raise ValueError("max_delay must be >= min_delay")
        return self


# ---------------------------------------------------------------------------
# Candidate property + validation report (spec 5.6)
# ---------------------------------------------------------------------------
class CandidateProperty(StrictModel):
    """A rendered SVA property. 'Rendered' != 'verified'."""

    property_name: str
    requirement_id: str
    clause_id: str
    property_kind: PropertyKind
    property_form: PropertyForm
    sva_text: str
    referenced_symbols: list[SymbolRef] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    # A rendered property is a candidate only, never a verified property.
    status: str = "candidate_compiled_offline"
    provenance: Provenance


class ValidationReport(StrictModel):
    """Result of static validation of a temporal intent / candidate."""

    requirement_id: str
    clause_id: str
    checks: list[ValidationCheck]
    emitted: bool
    candidate: CandidateProperty | None = None
    provenance: Provenance

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == Severity.ERROR)


# ---------------------------------------------------------------------------
# Review packet (spec 5.1 outputs)
# ---------------------------------------------------------------------------
class ReviewChecklistItem(StrictModel):
    item: str
    status: str = "pending"  # pending | ok | needs_attention


class ReviewReport(StrictModel):
    run_id: str
    requirement: Requirement
    decomposition: DecompositionResult
    groundings: list[GroundingResult]
    intents: list[TemporalIntent]
    validations: list[ValidationReport]
    checklist: list[ReviewChecklistItem]
    non_claims: list[str] = Field(default_factory=list)
    provenance: Provenance
