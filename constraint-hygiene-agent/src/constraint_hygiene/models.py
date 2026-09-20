"""Typed data contracts for the Constraint Hygiene Agent.

All models are Pydantic v2 models that *validate* (not merely annotate) the
data flowing between the deterministic parsers, the analysis passes, and the
report renderers.

Design notes
------------
* Every finding produced by an analysis pass carries an explicit
  :class:`Severity` and an ``evidence`` string.  Nothing in this tool ever
  claims a proof is valid; findings are *static suspicions*, and that framing
  is baked into the vocabulary (see :class:`Confidence`).
* Signal ownership is classified against the canonical RTL Intent Manifest
  port directions, so the classifier is grounded in real design facts rather
  than string heuristics alone.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #
class SvaKind(str, Enum):
    """The three SVA directive kinds this tool reasons about."""

    ASSUME = "assume"
    ASSERT = "assert"
    COVER = "cover"


class Ownership(str, Enum):
    """Who owns a signal, from the DUT's point of view.

    The classification is grounded in RTL Intent Manifest *port directions* of
    the top module (the DUT boundary):

    * ``ENVIRONMENT_INPUT`` - a DUT input.  Legal to constrain with ``assume``.
    * ``DUT_OUTPUT``        - a DUT output.  Constraining it is overconstraint.
    * ``INTERNAL_STATE``    - a register/net inside the DUT.  Constraining it is
      suspicious white-box overconstraint.
    * ``UNKNOWN``           - not found in the manifest; needs human review.
    """

    ENVIRONMENT_INPUT = "environment_input"
    DUT_OUTPUT = "dut_output"
    INTERNAL_STATE = "internal_state"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Confidence(str, Enum):
    """Deliberately labels everything as static, never formal.

    The build standard forbids presenting heuristic results as sound. These
    values make the distinction impossible to lose in the report.
    """

    STATIC_SUSPICION = "static_suspicion"
    STATIC_FACT = "static_fact"  # e.g. "this signal is a DUT output per manifest"


class FindingCode(str, Enum):
    CONTRADICTION = "CONTRADICTION"
    CONSTANT_CONFLICT = "CONSTANT_CONFLICT"
    UNUSED_ASSUMPTION = "UNUSED_ASSUMPTION"
    OUTPUT_CONSTRAINT = "OUTPUT_CONSTRAINT"
    INTERNAL_STATE_CONSTRAINT = "INTERNAL_STATE_CONSTRAINT"
    UNKNOWN_SIGNAL = "UNKNOWN_SIGNAL"
    VACUITY_RISK = "VACUITY_RISK"
    REACHABILITY_RISK = "REACHABILITY_RISK"


# --------------------------------------------------------------------------- #
# Parsed SVA
# --------------------------------------------------------------------------- #
class Property(_Base):
    """A single parsed SVA directive (assume / assert / cover)."""

    name: str
    kind: SvaKind
    expr: str = Field(description="Raw property expression text (best-effort).")
    signals: list[str] = Field(
        default_factory=list,
        description="Identifiers referenced in the expression (deterministic extraction).",
    )
    # Constant equality facts parsed from the expression, e.g. {"mode": "0"}.
    equalities: dict[str, str] = Field(default_factory=dict)
    # Boolean-literal facts, e.g. {"en": True} for `en`, {"en": False} for `!en`.
    boolean_facts: dict[str, bool] = Field(default_factory=dict)
    file: str = "<input>"
    line: int = 0


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
class Finding(_Base):
    code: FindingCode
    severity: Severity
    confidence: Confidence
    message: str
    evidence: str
    properties: list[str] = Field(default_factory=list, description="Property names involved.")
    signals: list[str] = Field(default_factory=list)
    needs_human_review: bool = True


class SignalClassification(_Base):
    signal: str
    ownership: Ownership
    rationale: str


class DependencyEdge(_Base):
    """A dependency edge: ``property`` depends on ``signal`` (and any assume that
    also drives that signal)."""

    property: str
    signal: str
    constrained_by_assumptions: list[str] = Field(default_factory=list)


class ReviewItem(_Base):
    priority: int = Field(ge=1, le=3, description="1 = highest.")
    reason: str
    related_findings: list[FindingCode] = Field(default_factory=list)
    subject: str


class Provenance(_Base):
    tool: str = "constraint-hygiene-agent"
    tool_version: str
    command: str = ""
    git_sha: str = "UNKNOWN"
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)


class HygieneReport(_Base):
    """The top-level deterministic output of the agent."""

    schema_version: str = "0.1.0"
    provenance: Provenance
    top_module: str | None = None

    assumption_inventory: list[Property] = Field(default_factory=list)
    assertion_inventory: list[Property] = Field(default_factory=list)
    cover_inventory: list[Property] = Field(default_factory=list)

    signal_ownership: list[SignalClassification] = Field(default_factory=list)
    contradiction_candidates: list[Finding] = Field(default_factory=list)
    unused_assumption_candidates: list[Finding] = Field(default_factory=list)
    output_constraint_warnings: list[Finding] = Field(default_factory=list)
    dependency_map: list[DependencyEdge] = Field(default_factory=list)
    vacuity_recommendations: list[Finding] = Field(default_factory=list)
    human_review_queue: list[ReviewItem] = Field(default_factory=list)

    # A single, honest safety disclaimer travels with every report.
    disclaimer: str = (
        "STATIC HYGIENE ONLY. Absence of a flagged contradiction does NOT mean the "
        "constraint set is sound or that any proof is valid. All findings are static "
        "suspicions requiring human review; no assumption may be changed without human "
        "approval."
    )
