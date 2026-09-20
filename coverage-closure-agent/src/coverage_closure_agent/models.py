"""Typed data contracts for the Coverage Closure Agent.

All inputs and outputs are Pydantic v2 models so they *validate*, not merely
annotate. The models are grouped as:

* Input contracts   -- what the agent ingests (coverage DB, manifests, logs).
* Analysis contracts -- what the deterministic classifier produces.
* Output contracts  -- the report artifacts (recommendations, provenance, etc.).

Design intent
-------------
The agent is a *triage and prioritization* tool. It never edits RTL, never
waives coverage, and never claims closure. That authority boundary is encoded
here: the only recommendations it may emit come from ``AllowedAction`` and every
recommendation is a *proposal* that lands in a human-review queue.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------


class CoverageKind(StrEnum):
    """Kinds of coverage items supported by the mock coverage format."""

    STATEMENT = "statement"
    BRANCH = "branch"
    TOGGLE = "toggle"
    FSM_STATE = "fsm_state"
    FSM_TRANSITION = "fsm_transition"
    COVERGROUP_BIN = "covergroup_bin"
    ASSERTION = "assertion"


class HoleCategory(StrEnum):
    """Deterministic classification of *why* a coverage item is uncovered.

    These are heuristic categories derived from evidence in the inputs. They are
    hypotheses about the hole, not verified conclusions.
    """

    NO_LINKED_TEST = "no_linked_test"
    TEST_EXISTS_NOT_RUN = "test_exists_not_run"
    TEST_RAN_BUT_FAILED = "test_ran_but_failed"
    TEST_RAN_STILL_UNCOVERED = "test_ran_still_uncovered"
    LIKELY_UNREACHABLE = "likely_unreachable"
    NO_REQUIREMENT_MAPPING = "no_requirement_mapping"
    WAIVER_CANDIDATE = "waiver_candidate"
    UNKNOWN = "unknown"


class AllowedAction(StrEnum):
    """The *only* recommendation types the agent may emit (spec 6.1).

    Anything outside this closed set is a prohibited action and must never be
    produced. The ranker draws exclusively from this enum.
    """

    RUN_EXISTING_TEST = "run_existing_test"
    ADD_COVER_PROPERTY = "add_cover_property"
    ADD_DIRECTED_TEST = "add_directed_test"
    ADD_CONSTRAINED_RANDOM_SCENARIO = "add_constrained_random_scenario"
    INSPECT_UNREACHABLE_CODE = "inspect_unreachable_code"
    REQUEST_WAIVER_REVIEW = "request_waiver_review"
    REQUEST_SPEC_CLARIFICATION = "request_spec_clarification"
    PROPOSE_ASSERTION_CANDIDATE = "propose_assertion_candidate"


class ProhibitedAction(StrEnum):
    """Actions the agent must never take. Kept as an explicit registry so the
    enforcement layer can reference them by name in refusals and tests."""

    MODIFY_RTL = "modify_rtl"
    AUTO_WAIVE_COVERAGE = "auto_waive_coverage"
    CHANGE_COVERAGE_SCOPE = "change_coverage_scope"
    CLAIM_CLOSURE_WITHOUT_MEASUREMENT = "claim_closure_without_measurement"
    ALTER_TESTS_OR_CONSTRAINTS = "alter_tests_or_constraints"


class TestStatus(StrEnum):
    """Result vocabulary from BUILD_STANDARD; a TIMEOUT/ERROR/UNKNOWN is never a PASS."""

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"
    NOT_RUN = "not_run"


# ---------------------------------------------------------------------------
# Input contracts
# ---------------------------------------------------------------------------


class CoverageItem(BaseModel):
    """A single coverage point in the normalized (mock) coverage DB export.

    ``hits`` is an integer count; an item is considered covered when
    ``hits >= 1``. ``goal`` documents the required hit count for context but the
    baseline classifier treats ``hits == 0`` as the hole condition.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_id: str = Field(..., description="Stable unique id, e.g. 'cov.fifo.branch.12'.")
    kind: CoverageKind
    hits: int = Field(..., ge=0, description="Observed hit count (0 == uncovered).")
    goal: int = Field(1, ge=1, description="Required hit count to consider covered.")
    module: str = Field(..., description="RTL module the item belongs to.")
    source_file: str | None = Field(None, description="Source file path (public toy RTL).")
    source_line: int | None = Field(None, ge=0)
    description: str = Field("", description="Human-readable name of the coverage point.")
    exclusion_pragma: bool = Field(
        False,
        description="True if RTL carries a coverage-exclusion pragma near this point.",
    )

    @property
    def is_covered(self) -> bool:
        return self.hits >= self.goal


class CoverageDB(BaseModel):
    """A normalized coverage DB export -- the mock coverage format."""

    model_config = ConfigDict(extra="forbid")

    format_version: str = Field("mock-cov-1.0")
    tool: str = Field("mock", description="Originating coverage tool (labelled 'mock').")
    items: list[CoverageItem]


class TestEntry(BaseModel):
    """A test in the test manifest."""

    model_config = ConfigDict(extra="forbid")

    test_id: str
    name: str
    status: TestStatus = TestStatus.NOT_RUN
    seed: int | None = None
    config: str | None = Field(None, description="Named config/build used to run the test.")
    covers: list[str] = Field(
        default_factory=list,
        description="Coverage ids this test is *intended* to hit (from testplan).",
    )
    last_run_iso: str | None = None


class TestManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tests: list[TestEntry]


class RTLModule(BaseModel):
    """A module entry from the RTL Intent Manifest (subset used for triage)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_file: str | None = None
    dead_code_hints: list[int] = Field(
        default_factory=list,
        description="Source lines flagged by upstream tools as likely unreachable.",
    )


class RTLIntentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: str | None = None
    modules: list[RTLModule]


class RequirementLink(BaseModel):
    """One row of the requirement-to-test matrix."""

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    description: str = ""
    tests: list[str] = Field(default_factory=list, description="Test ids satisfying the req.")
    covers: list[str] = Field(
        default_factory=list,
        description="Coverage ids the requirement is expected to exercise.",
    )


class RequirementMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    links: list[RequirementLink]


class LogEntry(BaseModel):
    """A failure or compile log record associated with a test."""

    model_config = ConfigDict(extra="forbid")

    test_id: str
    kind: str = Field("failure", description="'failure' or 'compile'.")
    message: str = ""
    source_file: str | None = None
    source_line: int | None = None


class LogBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[LogEntry] = Field(default_factory=list)


class TriageInputs(BaseModel):
    """The complete bundle the agent ingests."""

    model_config = ConfigDict(extra="forbid")

    coverage: CoverageDB
    tests: TestManifest
    rtl: RTLIntentManifest
    requirements: RequirementMatrix
    logs: LogBundle = Field(default_factory=LogBundle)


# ---------------------------------------------------------------------------
# Analysis + output contracts
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A single piece of evidence backing a classification or hypothesis.

    Evidence is always a *fact drawn from an input*, cited by source, never an
    unsupported claim.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., description="Which input the fact came from, e.g. 'test_manifest'.")
    detail: str = Field(..., description="The concrete observed fact.")
    ref: str | None = Field(None, description="Optional id/line the fact points at.")


class Recommendation(BaseModel):
    """A ranked, allowed next action. This is a *proposal* only."""

    model_config = ConfigDict(extra="forbid")

    action: AllowedAction
    rationale: str
    priority_score: float = Field(..., ge=0.0, le=1.0)
    expected_impact_items: int = Field(
        ..., ge=0, description="Hypothesized number of coverage items this could close."
    )
    expected_impact_note: str = Field(
        "", description="Explicit hypothesis label -- never a guarantee."
    )
    requires_human_approval: bool = Field(
        True, description="Every recommendation requires human approval before action."
    )
    detail: str = Field("", description="Concrete, copy-pasteable next step where possible.")

    @field_validator("action")
    @classmethod
    def _must_be_allowed(cls, v: AllowedAction) -> AllowedAction:
        # Redundant given the enum type, but makes the authority boundary explicit
        # and guards against any future widening of the field type.
        if v not in AllowedAction:
            raise ValueError(f"{v!r} is not an allowed recommendation")
        return v


class HoleClassification(BaseModel):
    """The classification of one coverage hole plus its ranked recommendations."""

    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    kind: CoverageKind
    module: str
    category: HoleCategory
    is_heuristic: bool = Field(
        True, description="All categories are heuristic hypotheses, not verified facts."
    )
    root_cause_hypotheses: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    provenance_complete: bool = Field(
        False, description="True when every classification field is backed by cited evidence."
    )


class IndependentMeasurementStep(BaseModel):
    """One instruction in the independent-measurement manifest.

    The agent cannot claim closure; closure must be *independently measured* by
    re-running coverage after approved actions. This manifest tells a human how.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    instruction: str
    verify_covered_when: str = Field(
        "hits >= goal in a fresh coverage export", description="Objective pass condition."
    )


class HumanReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    reason: str
    recommendations: list[AllowedAction]


class ScopeProvenance(BaseModel):
    """Scope + provenance report for the whole run."""

    model_config = ConfigDict(extra="forbid")

    tool_version: str
    input_hashes: dict[str, str]
    seed: int
    coverage_format: str
    total_items: int
    total_holes: int
    scope_note: str = Field(
        "Triage is heuristic; coverage-tool measurement remains authoritative. "
        "This run did not modify RTL, tests, constraints, scope, or waivers."
    )


class TriageMetrics(BaseModel):
    """Metrics computed over the run / a labelled sample (spec 6.1)."""

    model_config = ConfigDict(extra="forbid")

    total_holes: int
    total_recommendations: int
    valid_proposal_rate: float = Field(..., ge=0.0, le=1.0)
    provenance_completeness: float = Field(..., ge=0.0, le=1.0)
    # Sample-based metrics (only populated when a labelled sample is supplied).
    sample_size: int = 0
    accepted_proposal_rate: float | None = None
    false_positive_proposal_rate: float | None = None
    category_precision: float | None = None


class TriageReport(BaseModel):
    """The complete output artifact."""

    model_config = ConfigDict(extra="forbid")

    classifications: list[HoleClassification]
    independent_measurement: list[IndependentMeasurementStep]
    human_review_queue: list[HumanReviewItem]
    scope_provenance: ScopeProvenance
    metrics: TriageMetrics
    prohibited_actions_enforced: list[ProhibitedAction] = Field(
        default_factory=lambda: list(ProhibitedAction)
    )


# ---------------------------------------------------------------------------
# Sample labels (for metric evaluation over a sample)
# ---------------------------------------------------------------------------


class HoleLabel(BaseModel):
    """Ground-truth label for one coverage hole, used to score the classifier."""

    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    true_category: HoleCategory
    proposals_accepted: list[AllowedAction] = Field(
        default_factory=list, description="Which proposed actions a reviewer accepted."
    )
    proposals_rejected: list[AllowedAction] = Field(default_factory=list)


class SampleLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[HoleLabel]
