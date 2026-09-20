"""Typed Pydantic v2 data contracts for the RTL Intent manifest.

Every model uses ``model_config = ConfigDict(extra="forbid")`` so the JSON
manifest is a strict, validated contract - not merely annotated. The manifest
is the deterministic output of the built-in parser and is the input contract
for downstream tools (SVA generation, formal partitioning, planning).

Nothing in this module performs interpretation with an LLM. Every field is
populated by deterministic extraction. Fields that are heuristic (for example
clock/reset candidate confidence) are labelled as such and carry an explicit
rationale string.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Bumped when the manifest layout changes in a backward-incompatible way.
MANIFEST_SCHEMA_VERSION = "0.1.0"


class _Strict(BaseModel):
    """Base model: forbid unknown keys so the contract stays tight."""

    model_config = ConfigDict(extra="forbid")


class SourceLocation(_Strict):
    """Byte- and line-accurate location of an extracted item.

    Lines and columns are 1-based. ``end_line``/``end_col`` are inclusive of
    the last token that produced the item.
    """

    file: str
    line: int = Field(ge=1)
    col: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=1)


class PortDirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class NetKind(StrEnum):
    WIRE = "wire"
    REG = "reg"
    LOGIC = "logic"


class ProcedureKind(StrEnum):
    """Classification of an ``always`` block based on its sensitivity list.

    The classification is structural (deterministic), not semantic:
    * ``always_ff``  - edge-sensitive (``posedge``/``negedge``)
    * ``always_comb`` - level-sensitive / ``@*`` / SV ``always_comb``
    * ``always``      - could not be classified confidently
    """

    ALWAYS_FF = "always_ff"
    ALWAYS_COMB = "always_comb"
    ALWAYS = "always"


class ResetPolarity(StrEnum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class ResetSync(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    UNKNOWN = "unknown"


class Range(_Strict):
    """A packed bit range ``[msb:lsb]`` captured verbatim as source text.

    The subset parser does not evaluate parameter arithmetic, so ``msb`` and
    ``lsb`` are the original expression strings (e.g. ``"WIDTH-1"``).
    """

    msb: str
    lsb: str


class Port(_Strict):
    name: str
    direction: PortDirection
    net_kind: NetKind | None = None
    range: Range | None = None
    location: SourceLocation


class Parameter(_Strict):
    name: str
    default: str | None = None
    is_localparam: bool = False
    location: SourceLocation


class Net(_Strict):
    """A ``wire``/``reg``/``logic`` declaration (not a port).

    ``unpacked_range`` is set for memory arrays such as
    ``reg [WIDTH-1:0] mem [0:DEPTH-1];`` (the ``[0:DEPTH-1]`` dimension).
    """

    name: str
    net_kind: NetKind
    range: Range | None = None
    unpacked_range: Range | None = None
    is_memory: bool = False
    location: SourceLocation


class Register(_Strict):
    """A signal assigned with ``<=`` inside an edge-sensitive block.

    This is the deterministic definition of a "register" used here: a target
    of a nonblocking assignment under a clock edge. It is a structural signal,
    not a formal state-element proof.
    """

    name: str
    driven_in_procedure_index: int = Field(ge=0)
    location: SourceLocation


class ContinuousAssign(_Strict):
    lhs: str
    rhs: str
    location: SourceLocation


class Assignment(_Strict):
    """A single assignment inside a procedural block."""

    lhs: str
    rhs: str
    nonblocking: bool
    location: SourceLocation


class SensitivityEntry(_Strict):
    signal: str
    edge: str | None = None  # "posedge" | "negedge" | None (level)


class Procedure(_Strict):
    """An ``always`` / ``always_ff`` / ``always_comb`` block summary."""

    index: int = Field(ge=0)
    kind: ProcedureKind
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)
    is_star_sensitivity: bool = False
    assignment_targets: list[str] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    # Identifiers appearing in if/case control conditions inside the block.
    # Used (heuristically) to detect synchronous resets referenced in the body
    # but not in the sensitivity list.
    condition_signals: list[str] = Field(default_factory=list)
    location: SourceLocation


class PortConnection(_Strict):
    """A single named or positional port connection on an instance."""

    formal: str | None = None  # None => positional
    actual: str
    location: SourceLocation


class Instance(_Strict):
    module: str
    name: str
    connections: list[PortConnection] = Field(default_factory=list)
    location: SourceLocation


class ClockCandidate(_Strict):
    """Heuristic clock candidate. ``confidence`` is a heuristic score."""

    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)
    location: SourceLocation | None = None


class ResetCandidate(_Strict):
    """Heuristic reset candidate with inferred polarity/sync (heuristic)."""

    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    polarity: ResetPolarity = ResetPolarity.UNKNOWN
    sync: ResetSync = ResetSync.UNKNOWN
    rationale: list[str] = Field(default_factory=list)
    location: SourceLocation | None = None


class UnresolvedConstruct(_Strict):
    """An input construct the subset parser did not fully understand.

    Making these explicit is a hard requirement of the spec: every unsupported
    construct must be visible in the output rather than silently dropped.
    """

    kind: str
    detail: str
    location: SourceLocation | None = None


class ProcedureSummary(_Strict):
    always_ff: int = 0
    always_comb: int = 0
    always_other: int = 0
    continuous_assigns: int = 0


class Module(_Strict):
    name: str
    location: SourceLocation
    parameters: list[Parameter] = Field(default_factory=list)
    ports: list[Port] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    registers: list[Register] = Field(default_factory=list)
    continuous_assigns: list[ContinuousAssign] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    instances: list[Instance] = Field(default_factory=list)
    clock_candidates: list[ClockCandidate] = Field(default_factory=list)
    reset_candidates: list[ResetCandidate] = Field(default_factory=list)
    procedure_summary: ProcedureSummary = Field(default_factory=ProcedureSummary)


class HierarchyEdge(_Strict):
    """A parent -> child edge in the instantiation hierarchy.

    ``child_module`` may reference a module not present in the input set
    (an external/black-box module); ``child_defined`` records that.
    """

    parent_module: str
    child_module: str
    instance_name: str
    child_defined: bool


class ParserInfo(_Strict):
    adapter: str
    adapter_version: str
    supported_constructs: list[str] = Field(default_factory=list)
    unsupported_constructs: list[str] = Field(default_factory=list)


class Provenance(_Strict):
    tool: str = "rtl-intent"
    tool_version: str
    schema_version: str = MANIFEST_SCHEMA_VERSION
    git_sha: str = "UNKNOWN"  # placeholder; filled by CI/release tooling
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)
    command: str = ""


class Manifest(_Strict):
    """Top-level normalized design-intelligence manifest."""

    schema_version: str = MANIFEST_SCHEMA_VERSION
    provenance: Provenance
    parser: ParserInfo
    top: str | None = None
    modules: list[Module] = Field(default_factory=list)
    hierarchy: list[HierarchyEdge] = Field(default_factory=list)
    unresolved: list[UnresolvedConstruct] = Field(default_factory=list)

    def module_names(self) -> list[str]:
        return [m.name for m in self.modules]

    def get_module(self, name: str) -> Module | None:
        for m in self.modules:
            if m.name == name:
                return m
        return None
