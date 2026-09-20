"""Typed data contracts for the Counterexample Triage Agent.

All input/output artifacts are Pydantic v2 models so that they validate at
runtime, not merely annotate. The triage report is fully deterministic; the
optional LLM narrative is carried in a separate, clearly labeled field.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Trace / waveform model (the common, deterministic subset)
# ---------------------------------------------------------------------------


class WaveValue(BaseModel):
    """A single (time, value) sample for one signal.

    ``value`` is kept as a normalized string. Scalars are ``"0"``, ``"1"``,
    ``"x"``, ``"z"``. Vectors are binary strings such as ``"0011"`` (MSB first,
    matching VCD ``b<bits>`` dumps).
    """

    time: int = Field(..., ge=0, description="Simulation time (ticks) of this sample.")
    value: str = Field(..., min_length=1, description="Normalized signal value.")


class SignalTrace(BaseModel):
    """The full value history of one signal across the trace."""

    name: str = Field(..., description="Hierarchical signal name, e.g. dut.count.")
    width: int = Field(1, ge=1, description="Bit width; 1 for scalars.")
    samples: list[WaveValue] = Field(
        default_factory=list,
        description="Value changes, ordered by ascending time.",
    )

    def value_at(self, time: int) -> str | None:
        """Return the held value at ``time`` (last change at or before ``time``)."""
        held: str | None = None
        for s in self.samples:
            if s.time <= time:
                held = s.value
            else:
                break
        return held


class WaveTrace(BaseModel):
    """A parsed waveform: a set of signals plus the timescale and time axis."""

    timescale: str = Field("1ns", description="Human-readable timescale string.")
    signals: dict[str, SignalTrace] = Field(default_factory=dict)
    end_time: int = Field(0, ge=0, description="Largest observed time in the trace.")

    def signal(self, name: str) -> SignalTrace | None:
        return self.signals.get(name)

    def all_times(self) -> list[int]:
        """Sorted, de-duplicated list of every time at which any signal changes."""
        times: set[int] = set()
        for sig in self.signals.values():
            for s in sig.samples:
                times.add(s.time)
        return sorted(times)


# ---------------------------------------------------------------------------
# Assertion-failure record (input from a formal/sim tool)
# ---------------------------------------------------------------------------


class ImplicationStyle(StrEnum):
    OVERLAPPING = "overlapping"  # |->
    NON_OVERLAPPING = "non_overlapping"  # |=>


class AssertionFailure(BaseModel):
    """A structured record of an assertion failure emitted by a backend tool.

    The clock/reset/antecedent/consequent fields are *signal names* that must be
    resolvable against the trace. They are how we deterministically find the
    antecedent-activation cycle and the failure cycle.
    """

    property_name: str = Field(..., description="Name of the failing property.")
    property_text: str = Field("", description="Source SVA / property text, verbatim.")
    source_file: str = Field(..., description="RTL/property source file path.")
    source_line: int = Field(..., ge=1, description="1-based source line of the property.")
    clock: str = Field(..., description="Clock signal name.")
    clock_edge: str = Field("posedge", description="posedge or negedge.")
    reset: str | None = Field(None, description="Reset signal name, if any.")
    reset_active_high: bool = Field(True, description="Reset polarity.")
    antecedent_signal: str | None = Field(
        None, description="Signal whose truth activates the antecedent."
    )
    consequent_signal: str | None = Field(
        None, description="Signal that must hold for the consequent."
    )
    implication: ImplicationStyle = Field(ImplicationStyle.NON_OVERLAPPING)
    delay_min: int = Field(1, ge=0, description="Min cycles from antecedent to consequent.")
    delay_max: int = Field(1, ge=0, description="Max cycles from antecedent to consequent.")
    failure_time: int | None = Field(
        None, ge=0, description="Tool-reported failure time, if provided."
    )

    @field_validator("clock_edge")
    @classmethod
    def _valid_edge(cls, v: str) -> str:
        if v not in ("posedge", "negedge"):
            raise ValueError("clock_edge must be 'posedge' or 'negedge'")
        return v

    @field_validator("delay_max")
    @classmethod
    def _delay_range(cls, v: int, info) -> int:
        dmin = info.data.get("delay_min", 0)
        if v < dmin:
            raise ValueError("delay_max must be >= delay_min")
        return v


# ---------------------------------------------------------------------------
# RTL Intent Manifest fixture (subset used for cone extraction + citations)
# ---------------------------------------------------------------------------


class SourceLocation(BaseModel):
    file: str
    line: int = Field(..., ge=1)


class RTLSymbol(BaseModel):
    """One net/register/port in the design, with dependency + source info."""

    name: str
    kind: str = Field(..., description="port_in|port_out|reg|wire|const")
    width: int = Field(1, ge=1)
    location: SourceLocation
    drivers: list[str] = Field(
        default_factory=list,
        description="Names of symbols in this symbol's combinational/sequential fan-in.",
    )
    is_reset: bool = False
    is_clock: bool = False


class RTLIntentManifest(BaseModel):
    """Minimal RTL Intent Manifest fixture consumed for cone-of-influence."""

    design_top: str
    symbols: dict[str, RTLSymbol] = Field(default_factory=dict)

    def symbol(self, name: str) -> RTLSymbol | None:
        return self.symbols.get(name)


# ---------------------------------------------------------------------------
# Triage report (deterministic output)
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    """One cycle-linked event in the reconstructed timeline."""

    cycle: int = Field(..., ge=0, description="Clock cycle index (0-based).")
    time: int = Field(..., ge=0, description="Simulation time of the clock edge.")
    kind: str = Field(..., description="reset|antecedent|consequent|divergence|failure|sample")
    description: str
    signals: dict[str, str] = Field(
        default_factory=dict, description="Signal values sampled at this cycle."
    )


class SourceCitation(BaseModel):
    file: str
    line: int = Field(..., ge=1)
    symbol: str | None = None
    reason: str


class HypothesisCategory(StrEnum):
    DESIGN_BUG = "design_bug"
    PROPERTY_ISSUE = "property_issue"
    ENVIRONMENT_ISSUE = "environment_issue"
    RESET_ISSUE = "reset_issue"
    MODELING_ISSUE = "modeling_issue"


class RootCauseHypothesis(BaseModel):
    category: HypothesisCategory
    statement: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(
        default_factory=list,
        description="Concrete, trace-grounded evidence lines. Never empty for a"
        " design_bug hypothesis.",
    )

    @field_validator("evidence")
    @classmethod
    def _bug_needs_evidence(cls, v: list[str], info) -> list[str]:
        cat = info.data.get("category")
        if cat == HypothesisCategory.DESIGN_BUG and not v:
            raise ValueError(
                "A design_bug hypothesis must not be emitted without evidence."
            )
        return v


class ReproInfo(BaseModel):
    command: str
    artifacts: list[str] = Field(default_factory=list)


class ReproAttempt(BaseModel):
    """Advisory record of an optional real-simulation reproduction attempt.

    This is *context*, never evidence: a reproduction outcome can nudge the
    displayed confidence in the deterministic hypotheses but is not itself a
    source of any hypothesis' evidence, and never upgrades a hypothesis to a
    conclusion. A TIMEOUT/ERROR/SKIPPED outcome is never treated as a pass.
    """

    status: str = Field(
        ...,
        description="reproduced|not_reproduced|skipped|timeout|error.",
    )
    adapter: str = Field(..., description="Executor adapter name/version.")
    summary: str = ""
    exit_code: int | None = None
    duration_s: float = 0.0
    notes: list[str] = Field(default_factory=list)


class TriageReport(BaseModel):
    """The complete deterministic triage output."""

    property_name: str
    property_text: str
    property_location: SourceLocation
    clock: str
    reset: str | None

    antecedent_cycle: int | None = Field(
        None, description="First cycle the antecedent activated, if determinable."
    )
    antecedent_time: int | None = None
    first_divergence_cycle: int | None = Field(
        None, description="First cycle the consequent failed to hold as required."
    )
    first_divergence_time: int | None = None

    timeline: list[TimelineEvent] = Field(default_factory=list)
    rtl_cone: list[str] = Field(
        default_factory=list, description="Symbols in the property's cone of influence."
    )
    citations: list[SourceCitation] = Field(default_factory=list)
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    reproduction: ReproInfo

    # Optional, advisory real-simulation reproduction outcome (never evidence).
    reproduction_attempt: ReproAttempt | None = Field(
        None,
        description="Optional real-repro outcome. Advisory context only; not evidence.",
    )

    # Clearly separated, optional, non-authoritative narrative.
    llm_narrative: str | None = Field(
        None,
        description="Optional LLM-authored prose. Advisory only; not evidence.",
    )

    def top_hypothesis(self) -> RootCauseHypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None
