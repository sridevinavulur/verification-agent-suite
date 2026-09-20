"""Typed data contracts for the Assertion Review Agent.

All input/output contracts are Pydantic v2 models so they validate rather than
merely annotate. The two authority layers are kept separate:

* deterministic static checks produce :class:`Finding` objects with a
  :class:`Severity` and a :class:`SourceLocation`;
* an optional LLM layer may only *explain* findings (see ``llm.py``); it never
  creates, deletes, or reclassifies a deterministic finding.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Severity of a review finding.

    ``ERROR``   -- almost certainly wrong; would give a misleading formal result.
    ``WARNING`` -- likely defect or strong smell; needs human review.
    ``INFO``    -- advisory / style / traceability note.
    """

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class SourceLocation(BaseModel):
    """A 1-based location inside an SVA source file."""

    model_config = ConfigDict(frozen=True)

    file: str
    line: int = Field(ge=1)
    column: int = Field(default=1, ge=1)
    snippet: str = ""


class ResetPolarity(StrEnum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class SignalRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"
    INTERNAL = "internal"
    CLOCK = "clock"
    RESET = "reset"
    UNKNOWN = "unknown"


class ManifestSignal(BaseModel):
    """A single symbol from the RTL Intent Manifest fixture."""

    name: str
    role: SignalRole = SignalRole.UNKNOWN
    width: int = Field(default=1, ge=1)
    reset_polarity: ResetPolarity = ResetPolarity.UNKNOWN


class RtlIntentManifest(BaseModel):
    """A constrained RTL Intent Manifest used to ground SVA identifiers.

    This is a *fixture* format for this tool. It mirrors the fields the prompt
    pack's RTL Intent Ingestor is meant to emit (name, direction/role, width,
    clock/reset candidates), but only the subset the reviewer needs.
    """

    model_config = ConfigDict(extra="forbid")

    top: str
    signals: list[ManifestSignal] = Field(default_factory=list)
    clock_candidates: list[str] = Field(default_factory=list)
    reset_candidates: list[str] = Field(default_factory=list)

    def by_name(self) -> dict[str, ManifestSignal]:
        return {s.name: s for s in self.signals}


class PropertyKind(StrEnum):
    ASSERT = "assert"
    ASSUME = "assume"
    COVER = "cover"


class ImplicationStyle(StrEnum):
    OVERLAPPING = "overlapping"  # |->
    NON_OVERLAPPING = "non_overlapping"  # |=>
    NONE = "none"


class ParsedProperty(BaseModel):
    """A parsed SVA property from the constrained subset parser.

    Fields are best-effort; when the parser cannot determine a field it is left
    ``None`` so checks can reason about "missing" vs "present".
    """

    name: str | None = None
    kind: PropertyKind = PropertyKind.ASSERT
    clock: str | None = None
    disable_iff: str | None = None  # raw expression inside disable iff (...)
    antecedent: str | None = None
    consequent: str | None = None
    implication: ImplicationStyle = ImplicationStyle.NONE
    body: str = ""  # full raw property/assert body text
    location: SourceLocation
    identifiers: list[str] = Field(default_factory=list)
    raw: str = ""


class CheckId(StrEnum):
    """Stable identifiers for each deterministic check."""

    MISSING_DISABLE_IFF = "MISSING_DISABLE_IFF"
    RESET_POLARITY_RISK = "RESET_POLARITY_RISK"
    IMPLICATION_STYLE_RISK = "IMPLICATION_STYLE_RISK"
    UNBOUNDED_TEMPORAL = "UNBOUNDED_TEMPORAL"
    WEAK_CONSEQUENT = "WEAK_CONSEQUENT"
    ANTECEDENT_IN_CONSEQUENT = "ANTECEDENT_IN_CONSEQUENT"
    TRIVIALLY_PASSING = "TRIVIALLY_PASSING"
    ASSUME_CONSTRAINS_OUTPUT = "ASSUME_CONSTRAINS_OUTPUT"
    UNDECLARED_SIGNAL = "UNDECLARED_SIGNAL"
    WIDTH_MISMATCH = "WIDTH_MISMATCH"
    NAME_SEMANTICS = "NAME_SEMANTICS"
    MISSING_CLOCK = "MISSING_CLOCK"
    REQ_TRACEABILITY = "REQ_TRACEABILITY"
    VACUITY_RISK = "VACUITY_RISK"


class Finding(BaseModel):
    """A single deterministic review finding."""

    model_config = ConfigDict(frozen=True)

    check_id: CheckId
    severity: Severity
    message: str
    location: SourceLocation
    property_name: str | None = None
    heuristic: bool = False
    recommendation: str = ""
    explanation: str | None = None  # filled only by the optional LLM layer


class ReviewReport(BaseModel):
    """Full deterministic review output for one SVA file."""

    source_file: str
    manifest_top: str | None = None
    property_count: int = 0
    findings: list[Finding] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    def score(self) -> ReviewScore:
        """Compute the review-quality score from the rubric (see ``scoring.py``)."""
        from .scoring import score_report

        return score_report(self)


class ReviewScore(BaseModel):
    """Weighted review-quality score. See ``docs/SCORING_RUBRIC.md``."""

    error_count: int
    warning_count: int
    info_count: int
    penalty: int
    max_penalty: int
    score: float = Field(ge=0.0, le=100.0)
    grade: str
