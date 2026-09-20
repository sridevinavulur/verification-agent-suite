"""Typed data contracts for security-property-agent.

All contracts are Pydantic v2 models that *validate* (not merely annotate).
They form the stable interface between deterministic pipeline stages:

    security requirement (structured input)
        -> decomposition (atomic clauses, requirement text preserved EXACTLY)
        -> RTL grounding (evidence-based symbol mapping against a Manifest)
        -> candidate SVA (rendered from a whitelist of security property forms)
        -> mutation / fault examples (should-fail negatives for a good property)
        -> review packet (human sign-off gate + non-claims)

Safety design notes:
* The original requirement text is stored verbatim and never rewritten. A
  cryptographic-ish hash (sha256) of the text is recorded so a reviewer can
  confirm nothing was mutated by the tool.
* Nothing here infers a threat model, trust boundary, clock, or reset. Missing
  information is represented explicitly (``None`` / empty lists / ``ambiguities``)
  so downstream stages *reject and flag* rather than guess.
* A rendered property is a *candidate*, never "verified". The status vocabulary
  matches the shared BUILD_STANDARD and sva-intent-engine style.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1.0"
TOOL_NAME = "security-property-agent"


class StrictModel(BaseModel):
    """Base model: reject unknown fields and validate on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class SecurityCategory(str, Enum):
    """The security check families this agent supports (spec 6.13)."""

    ACCESS_CONTROL = "access_control"
    PRIVILEGE_GATING = "privilege_gating"
    DEBUG_LOCKOUT = "debug_lockout"
    FAULT_RESPONSE = "fault_response"
    ERROR_CONTAINMENT = "error_containment"
    LOCKSTEP_MISMATCH = "lockstep_mismatch"
    INFORMATION_FLOW_ADJACENT = "information_flow_adjacent"


class ClauseKind(str, Enum):
    """Classification of an atomic requirement clause.

    The spec is explicit that these categories must be kept distinct:
    a *safety property* (something the design must guarantee) is not the same
    as an *environment assumption* (something the surrounding system must
    provide), which is not the same as a *security test objective* (a scenario
    we want to demonstrate is reachable / covered).
    """

    SAFETY_PROPERTY = "safety_property"
    ENVIRONMENT_ASSUMPTION = "environment_assumption"
    SECURITY_TEST_OBJECTIVE = "security_test_objective"
    AMBIGUITY = "ambiguity"
    UNSUPPORTED = "unsupported"


class PropertyKind(str, Enum):
    """SVA directive."""

    ASSERT = "assert"
    ASSUME = "assume"
    COVER = "cover"


class PropertyForm(str, Enum):
    """Whitelisted renderable candidate property forms (security-oriented)."""

    # X must never happen (safety invariant)
    NEVER = "never"
    # condition holds every cycle
    ALWAYS = "always"
    # antecedent |-> consequent (same cycle)
    IMPLICATION = "implication"
    # antecedent |=> consequent (next cycle)
    NEXT_CYCLE = "next_cycle"
    # antecedent |-> ##[min:max] consequent (bounded fault response)
    BOUNDED_RESPONSE = "bounded_response"
    # two replicas must always agree (lockstep)
    LOCKSTEP_EQUAL = "lockstep_equal"
    # cover: a scenario is reachable (security test objective)
    REACHABLE = "reachable"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class MatchKind(str, Enum):
    EXACT = "exact"
    ALIAS = "alias"
    UNRESOLVED = "unresolved"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
class Provenance(StrictModel):
    """Record of how an artifact was produced (BUILD_STANDARD run ledger)."""

    tool: str = TOOL_NAME
    tool_version: str = SCHEMA_VERSION
    schema_version: str = SCHEMA_VERSION
    stage: str
    git_sha: str = "UNKNOWN"
    input_hashes: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    seed: int | None = None
    # There is no LLM in this deterministic core; recorded for honesty.
    model_provider: str | None = None
    model_name: str | None = None
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Structured security requirement (INPUT)
# ---------------------------------------------------------------------------
class SecurityRequirement(StrictModel):
    """A single structured security requirement (the input contract).

    ``text`` is the human-authored requirement statement and is preserved
    EXACTLY by the whole pipeline. ``signals`` optionally names candidate RTL
    signals the author already has in mind; the grounding stage still requires
    evidence in the Manifest before treating any of them as resolved.
    """

    requirement_id: str = Field(min_length=1)
    category: SecurityCategory
    text: str = Field(min_length=1)
    # Optional author hints. Never trusted blindly; grounding needs evidence.
    signals: list[str] = Field(default_factory=list)
    # Optional explicit threat-model note. If present it is EVIDENCE that a
    # human declared a boundary; the tool never fabricates one when absent.
    declared_trust_boundary: str | None = None
    tags: list[str] = Field(default_factory=list)


class RequirementSet(StrictModel):
    """A file's worth of structured security requirements."""

    schema_version: str = SCHEMA_VERSION
    design: str | None = None
    requirements: list[SecurityRequirement]


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------
class SourceSpan(StrictModel):
    """Character span into the original requirement text (verbatim slice)."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _order(self) -> SourceSpan:
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class Clause(StrictModel):
    """An atomic requirement clause.

    ``text`` is a VERBATIM slice of the requirement (never paraphrased). The
    span records where it came from so a reviewer can confirm fidelity.
    """

    clause_id: str
    kind: ClauseKind
    text: str
    span: SourceSpan
    rationale: list[str] = Field(default_factory=list)


class DecompositionResult(StrictModel):
    requirement_id: str
    original_text: str
    original_text_sha256: str
    clauses: list[Clause]
    ambiguities: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _clauses_are_verbatim(self) -> DecompositionResult:
        """Hard guarantee: every clause text is a substring of the original.

        This is the machine-checked form of "preserve requirements exactly".
        """
        for c in self.clauses:
            slice_ = self.original_text[c.span.start : c.span.end]
            if slice_ != c.text:
                raise ValueError(
                    f"clause {c.clause_id} text is not a verbatim slice of the requirement"
                )
        return self


# ---------------------------------------------------------------------------
# RTL grounding (against the canonical Manifest)
# ---------------------------------------------------------------------------
class SymbolRef(StrictModel):
    """A resolved-or-not reference to an RTL symbol from the Manifest."""

    term: str
    match_kind: MatchKind
    module: str | None = None
    symbol: str | None = None
    kind: str | None = None  # port | net | register | parameter
    evidence: list[str] = Field(default_factory=list)


class GroundingResult(StrictModel):
    requirement_id: str
    clock_candidates: list[str] = Field(default_factory=list)
    reset_candidates: list[str] = Field(default_factory=list)
    symbols: list[SymbolRef] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    provenance: Provenance

    @property
    def fully_grounded(self) -> bool:
        return not self.unresolved_terms and all(
            s.match_kind is not MatchKind.UNRESOLVED for s in self.symbols
        )


# ---------------------------------------------------------------------------
# Candidate SVA
# ---------------------------------------------------------------------------
class CandidateProperty(StrictModel):
    """A rendered candidate SVA property. 'Rendered' != 'verified'."""

    property_name: str
    requirement_id: str
    clause_id: str
    category: SecurityCategory
    property_kind: PropertyKind
    property_form: PropertyForm
    sva_text: str
    referenced_symbols: list[SymbolRef] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    # A rendered property is a candidate only, never a verified property.
    status: str = "candidate_rendered_offline"
    provenance: Provenance


# ---------------------------------------------------------------------------
# Mutation / fault examples
# ---------------------------------------------------------------------------
class MutationKind(str, Enum):
    NEGATE_ANTECEDENT = "negate_antecedent"
    NEGATE_CONSEQUENT = "negate_consequent"
    WEAKEN_BOUND = "weaken_bound"
    BREAK_LOCKSTEP = "break_lockstep"
    DROP_GUARD = "drop_guard"


class MutationExample(StrictModel):
    """A deliberately-broken variant of a candidate.

    The intent: if the candidate property is meaningful, the mutated property
    (or the described fault stimulus) SHOULD produce a failure. This gives a
    reviewer a concrete "sanity witness". It is NOT proof the original holds.
    """

    mutation_id: str
    of_property: str
    mutation_kind: MutationKind
    description: str
    mutated_sva_text: str
    expected_effect: str = "should_fail_if_original_is_meaningful"
    provenance: Provenance


# ---------------------------------------------------------------------------
# Validation report (deterministic static checks)
# ---------------------------------------------------------------------------
class ValidationCheck(StrictModel):
    name: str
    passed: bool
    severity: Severity
    detail: str = ""


class RequirementArtifacts(StrictModel):
    """Everything derived from one requirement."""

    requirement: SecurityRequirement
    decomposition: DecompositionResult
    grounding: GroundingResult
    candidates: list[CandidateProperty]
    mutations: list[MutationExample]
    checks: list[ValidationCheck]
    emitted: bool

    @property
    def has_errors(self) -> bool:
        return any(not c.passed and c.severity is Severity.ERROR for c in self.checks)


# ---------------------------------------------------------------------------
# Review packet (top-level output)
# ---------------------------------------------------------------------------
class ReviewChecklistItem(StrictModel):
    item: str
    status: str = "pending"  # pending | ok | needs_attention


class SecurityReviewReport(StrictModel):
    run_id: str
    design: str | None = None
    manifest_top: str | None = None
    artifacts: list[RequirementArtifacts]
    checklist: list[ReviewChecklistItem] = Field(default_factory=list)
    non_claims: list[str] = Field(default_factory=list)
    provenance: Provenance
