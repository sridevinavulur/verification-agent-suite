"""Typed data contracts for the Equivalence Triage Agent.

All contracts are Pydantic v2 models: they *validate* input, they do not just
annotate it. Two families of models live here:

* **Inputs** -- what an equivalence-checking (LEC/SEC) flow produces:
  :class:`EquivalenceLog`, :class:`MismatchPoint`, :class:`Counterexample`,
  :class:`SourceMap`, plus a light local mirror of the canonical RTL Intent
  Manifest (:class:`DesignManifest`).
* **Outputs** -- the evidence-grounded triage report:
  :class:`TriageReport` and its sub-parts.

Design rules enforced structurally here (see THREAT_MODEL.md):

* The report never *claims* equivalence/non-equivalence on its own. It only
  echoes the tool's own :class:`EquivalenceStatus` and always carries the
  supporting evidence (log path + line, CEX vectors) next to any statement.
* Likely-cause classifications are always tagged as ``heuristic`` and carry a
  bounded confidence in ``[0, 1]`` with an explicit rationale.
* Configuration/constraint differences between the two runs are surfaced in a
  dedicated, non-hideable field (:class:`ConfigDelta`).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """Base model: reject unknown keys so malformed inputs fail loudly."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Enumerations (fixed result vocabulary from BUILD_STANDARD.md)               #
# --------------------------------------------------------------------------- #


class EquivalenceStatus(StrEnum):
    """The equivalence-checker's own verdict. Echoed, never invented."""

    EQUIVALENT = "EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    INCONCLUSIVE = "INCONCLUSIVE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    ABORTED = "ABORTED"


class MismatchKind(StrEnum):
    """Structural classification of a mismatched compare point."""

    OUTPUT = "output"
    STATE = "state"
    CUTPOINT = "cutpoint"
    BLACKBOX = "blackbox"
    UNKNOWN = "unknown"


class CauseCategory(StrEnum):
    """Heuristic likely-cause categories called for by the spec."""

    WIDTH = "width"
    POLARITY = "polarity"
    GATING = "gating"
    STATE_ENCODING = "state_encoding"
    OPTIMIZATION = "optimization"
    RESET_INIT = "reset_init"
    CONFIG_CONSTRAINT = "config_constraint"
    UNKNOWN = "unknown"


class ResetPolarity(StrEnum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class ResetSync(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Shared value objects                                                         #
# --------------------------------------------------------------------------- #


class SourceLocation(_Strict):
    """1-based source location; mirrors the canonical manifest schema."""

    file: str
    line: int = Field(ge=1)
    col: int = Field(default=1, ge=1)


class SourceMapEntry(_Strict):
    """Maps a compare-point / signal name to a source location in a design."""

    signal: str
    design: str = Field(description="'reference' or 'revised'.")
    location: SourceLocation
    module: str | None = None


class SourceMap(_Strict):
    """Collection of signal -> source-location mappings."""

    entries: list[SourceMapEntry] = Field(default_factory=list)

    def lookup(self, signal: str, design: str) -> SourceMapEntry | None:
        for e in self.entries:
            if e.signal == signal and e.design == design:
                return e
        return None


# --------------------------------------------------------------------------- #
# Input contracts                                                             #
# --------------------------------------------------------------------------- #


class CexVector(_Strict):
    """One signal's value at one time step of a counterexample."""

    signal: str
    time: int = Field(ge=0)
    ref_value: str | None = None
    rev_value: str | None = None

    @property
    def differs(self) -> bool:
        return (
            self.ref_value is not None
            and self.rev_value is not None
            and self.ref_value != self.rev_value
        )


class Counterexample(_Strict):
    """A CEX witnessing a single compare-point mismatch."""

    compare_point: str
    first_diff_time: int | None = Field(default=None, ge=0)
    vectors: list[CexVector] = Field(default_factory=list)

    def diff_signals(self) -> list[str]:
        seen: list[str] = []
        for v in self.vectors:
            if v.differs and v.signal not in seen:
                seen.append(v.signal)
        return seen


class MismatchPoint(_Strict):
    """A single non-equivalent compare point reported by the tool."""

    name: str
    kind: MismatchKind = MismatchKind.UNKNOWN
    ref_signal: str | None = None
    rev_signal: str | None = None
    ref_width: int | None = Field(default=None, ge=0)
    rev_width: int | None = Field(default=None, ge=0)
    fanin_signals: list[str] = Field(
        default_factory=list,
        description="Support (cone-of-influence) signals from the tool report.",
    )
    counterexample: Counterexample | None = None


class ConfigDelta(_Strict):
    """A single configuration/constraint difference between the two runs.

    Surfacing these is mandatory (never conceal configuration differences).
    """

    key: str
    reference_value: str | None = None
    revised_value: str | None = None

    @property
    def differs(self) -> bool:
        return self.reference_value != self.revised_value


class EquivalenceLog(_Strict):
    """Parsed, normalized equivalence-checker log."""

    tool: str
    tool_version: str = "unknown"
    status: EquivalenceStatus
    reference_design: str
    revised_design: str
    compare_points_total: int = Field(default=0, ge=0)
    compare_points_matched: int = Field(default=0, ge=0)
    mismatches: list[MismatchPoint] = Field(default_factory=list)
    config_deltas: list[ConfigDelta] = Field(default_factory=list)
    raw_log_path: str | None = None
    messages: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# A light local mirror of the canonical RTL Intent Manifest                    #
# --------------------------------------------------------------------------- #


class ResetInfo(_Strict):
    """Reset/init behavior for one design (extracted from a manifest)."""

    signal: str | None = None
    polarity: ResetPolarity = ResetPolarity.UNKNOWN
    sync: ResetSync = ResetSync.UNKNOWN
    init_values: dict[str, str] = Field(default_factory=dict)


class DesignManifest(_Strict):
    """A minimal, validation-only mirror of the canonical manifest.

    We intentionally consume only the fields the triage needs and IGNORE the
    rest via ``model_validate`` with a permissive loader (see parser). This
    keeps interop with rtl-intent-ingestor without re-implementing its parser.
    """

    top: str | None = None
    signal_widths: dict[str, int] = Field(default_factory=dict)
    reset: ResetInfo = Field(default_factory=ResetInfo)
    state_encoding: dict[str, str] = Field(
        default_factory=dict,
        description="signal -> encoding style, e.g. 'onehot' / 'binary'.",
    )


# --------------------------------------------------------------------------- #
# Output contracts                                                            #
# --------------------------------------------------------------------------- #


class Provenance(_Strict):
    """Run provenance / ledger (BUILD_STANDARD requirement)."""

    tool: str = "eq-triage"
    tool_version: str
    schema_version: str = "0.1.0"
    command: str = ""
    git_sha: str = "UNKNOWN"
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)


class LikelyCause(_Strict):
    """A heuristic likely-cause hypothesis. HEURISTIC, not a proof."""

    category: CauseCategory
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)
    is_heuristic: bool = True
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Pointers to log/CEX/manifest evidence supporting this.",
    )


class RankedLocation(_Strict):
    """A source location ranked for engineer review."""

    signal: str
    design: str
    location: SourceLocation | None = None
    module: str | None = None
    score: float = Field(ge=0.0)
    reasons: list[str] = Field(default_factory=list)


class MismatchGroup(_Strict):
    """A group of duplicate mismatch signatures + their triage."""

    signature: str
    members: list[str] = Field(
        default_factory=list, description="compare-point names in this group."
    )
    kind: MismatchKind = MismatchKind.UNKNOWN
    cone_signals: list[str] = Field(default_factory=list)
    width_ref: int | None = None
    width_rev: int | None = None
    likely_causes: list[LikelyCause] = Field(default_factory=list)
    ranked_locations: list[RankedLocation] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.members)


class ResetComparison(_Strict):
    """Reset/init behavior comparison between reference and revised."""

    reference: ResetInfo = Field(default_factory=ResetInfo)
    revised: ResetInfo = Field(default_factory=ResetInfo)
    polarity_differs: bool = False
    sync_differs: bool = False
    init_value_diffs: dict[str, str] = Field(
        default_factory=dict,
        description="signal -> 'ref!=rev' human-readable diff.",
    )
    notes: list[str] = Field(default_factory=list)


class DebugPacket(_Strict):
    """A reproducible debug packet for one investigation."""

    repro_command: str
    input_files: list[str] = Field(default_factory=list)
    focus_compare_points: list[str] = Field(default_factory=list)
    focus_signals: list[str] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)


class TriageReport(_Strict):
    """Top-level evidence-grounded mismatch-localization report."""

    provenance: Provenance
    reported_status: EquivalenceStatus = Field(
        description="Echoed verbatim from the tool log. Never inferred."
    )
    status_evidence: list[str] = Field(
        default_factory=list,
        description="Where in the log the status came from.",
    )
    reference_design: str
    revised_design: str
    compare_points_total: int = 0
    compare_points_matched: int = 0
    mismatch_count: int = 0
    config_deltas: list[ConfigDelta] = Field(default_factory=list)
    reset_comparison: ResetComparison = Field(default_factory=ResetComparison)
    groups: list[MismatchGroup] = Field(default_factory=list)
    debug_packet: DebugPacket | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def has_config_differences(self) -> bool:
        return any(d.differs for d in self.config_deltas)
