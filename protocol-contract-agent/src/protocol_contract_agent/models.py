"""Typed data contracts for the Protocol Contract Agent (Pydantic v2).

Two families of models:

1. A small *view* over the canonical RTL Intent Manifest
   (``rtl-intent-ingestor/schemas/manifest.schema.json``). We do NOT re-implement
   the whole manifest; we validate only the fields we consume (module, ports with
   direction/width, registers, clock/reset candidates, source locations) so a real
   manifest emitted by rtl-intent loads unchanged. ``extra="ignore"`` lets us
   ignore fields we don't use without breaking on real inputs.

2. The contract output models (roles, assumptions, guarantees, candidate
   properties, negative scenarios, dependencies, checklist, and the top-level
   ProtocolContract) that this tool produces.

Safety-relevant invariants are encoded in the types where possible:
* Every ``SignalRole`` carries a resolved ``symbol_id`` + source location, so no
  property can reference a symbol that is not grounded in the manifest.
* Every ``ContractProperty`` carries an explicit ``property_kind``
  (assert/assume/cover) and ``ownership`` note so an output signal is never
  silently constrained as an environment input.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class ResetPolarity(str, Enum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"
    UNKNOWN = "unknown"


class ResetSync(str, Enum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    UNKNOWN = "unknown"


class ProtocolKind(str, Enum):
    VALID_READY = "valid_ready"
    REQ_GRANT = "req_grant"
    FIFO = "fifo"
    INTERRUPT = "interrupt"
    CREDIT = "credit"


class PropertyKind(str, Enum):
    ASSERT = "assert"
    ASSUME = "assume"
    COVER = "cover"


class SignalOwnership(str, Enum):
    """Who drives a signal, from the DUT's point of view.

    ``env_input``  -> driven by the environment (an input port of the DUT).
    ``dut_output`` -> driven by the DUT (an output port).
    ``internal``   -> internal register/net.
    ``unknown``    -> could not be classified from the manifest.
    """

    ENV_INPUT = "env_input"
    DUT_OUTPUT = "dut_output"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# --------------------------------------------------------------------------- #
# Manifest view (subset of the canonical RTL Intent Manifest)
# --------------------------------------------------------------------------- #


class MSourceLocation(BaseModel):
    """Source location as emitted by rtl-intent (1-based)."""

    model_config = ConfigDict(extra="ignore")

    file: str
    line: int
    col: int = 1
    end_line: int | None = None
    end_col: int | None = None


class MRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    msb: str
    lsb: str


class MPort(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    direction: PortDirection
    net_kind: str | None = None
    range: MRange | None = None
    location: MSourceLocation | None = None


class MRegister(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    location: MSourceLocation | None = None


class MNet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    net_kind: str | None = None
    range: MRange | None = None
    location: MSourceLocation | None = None


class MClockCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal: str
    confidence: float = 0.0
    location: MSourceLocation | None = None
    rationale: list[str] = Field(default_factory=list)


class MResetCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal: str
    confidence: float = 0.0
    polarity: ResetPolarity = ResetPolarity.UNKNOWN
    sync: ResetSync = ResetSync.UNKNOWN
    location: MSourceLocation | None = None
    rationale: list[str] = Field(default_factory=list)


class MModule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    location: MSourceLocation | None = None
    ports: list[MPort] = Field(default_factory=list)
    nets: list[MNet] = Field(default_factory=list)
    registers: list[MRegister] = Field(default_factory=list)
    clock_candidates: list[MClockCandidate] = Field(default_factory=list)
    reset_candidates: list[MResetCandidate] = Field(default_factory=list)


class RtlManifest(BaseModel):
    """Validated subset of the canonical RTL Intent Manifest.

    Only the fields the contract generator consumes are modeled; all other
    fields present in a real manifest are ignored (not dropped from disk).
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "0.1.0"
    top: str | None = None
    modules: list[MModule] = Field(default_factory=list)

    def module(self, name: str) -> MModule | None:
        for m in self.modules:
            if m.name == name:
                return m
        return None


# --------------------------------------------------------------------------- #
# Grounded symbol reference
# --------------------------------------------------------------------------- #


class GroundedSymbol(BaseModel):
    """A symbol that has been resolved to a manifest entry.

    A property may only reference GroundedSymbols; this is how we enforce
    "every property is grounded to RTL symbols".
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    symbol_id: str
    ownership: SignalOwnership
    direction: PortDirection | None = None
    width_msb: str | None = None
    width_lsb: str | None = None
    file: str | None = None
    line: int | None = None

    @property
    def is_multibit(self) -> bool:
        # A packed range that is not exactly [0:0] / [x:x] is treated as multi-bit.
        if self.width_msb is None or self.width_lsb is None:
            return False
        return self.width_msb.strip() != self.width_lsb.strip()


# --------------------------------------------------------------------------- #
# Contract sub-parts
# --------------------------------------------------------------------------- #


class SignalRole(BaseModel):
    """Maps a protocol role (e.g. ``valid``) to a grounded RTL symbol."""

    model_config = ConfigDict(extra="forbid")

    role: str
    symbol: GroundedSymbol
    required: bool = True
    note: str | None = None


class ClockResetMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clock: GroundedSymbol | None = None
    reset: GroundedSymbol | None = None
    reset_polarity: ResetPolarity = ResetPolarity.UNKNOWN
    reset_sync: ResetSync = ResetSync.UNKNOWN
    # Explicit, human-readable statement of the reset behavior used by properties.
    reset_behavior: str = "UNSPECIFIED - reset behavior must be reviewed."


class Assumption(BaseModel):
    """An environmental assumption. These constrain *environment inputs* only.

    ``ownership_ok`` is False when the assumption would constrain a DUT output or
    internal signal; such assumptions are surfaced for review instead of being
    silently added.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    sva: str
    property_kind: PropertyKind = PropertyKind.ASSUME
    referenced_symbols: list[GroundedSymbol] = Field(default_factory=list)
    ownership_ok: bool = True
    review_reason: str | None = None


class Guarantee(BaseModel):
    """A design guarantee (assert). Constrains DUT outputs / internal state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    sva: str
    property_kind: PropertyKind = PropertyKind.ASSERT
    referenced_symbols: list[GroundedSymbol] = Field(default_factory=list)


class ContractProperty(BaseModel):
    """A named candidate SVA property (assert / assume / cover).

    ``sva_text`` is a full, deterministically formatted, *candidate* property
    block. It is compiled offline elsewhere and is never labeled verified.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    property_kind: PropertyKind
    role: str  # 'guarantee' | 'assumption' | 'cover' | 'negative'
    description: str
    sva_text: str
    referenced_symbols: list[GroundedSymbol] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class NegativeScenario(BaseModel):
    """A scenario that MUST NOT happen, expressed as an assertion of its negation
    (or as a cover of the bad condition, flagged for review)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    sva: str
    property_kind: PropertyKind = PropertyKind.ASSERT
    referenced_symbols: list[GroundedSymbol] = Field(default_factory=list)


class PropertyDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_name: str
    depends_on: list[str] = Field(default_factory=list)
    rationale: str | None = None


class ChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    severity: Severity = Severity.INFO
    auto_status: str = "REVIEW"  # REVIEW | OK | WARN | FAIL (heuristic pre-fill)
    detail: str | None = None


class Warning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Severity = Severity.WARNING


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = "protocol-contract-agent"
    tool_version: str = "0.1.0"
    schema_version: str = "0.1.0"
    git_sha: str = "UNKNOWN"
    command: str | None = None
    manifest_module: str | None = None
    protocol: ProtocolKind | None = None
    input_sha256: dict[str, str] = Field(default_factory=dict)


class ProtocolContract(BaseModel):
    """Top-level reviewable interface contract for a single protocol instance."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    protocol: ProtocolKind
    module: str
    instance_label: str | None = None
    signal_roles: list[SignalRole] = Field(default_factory=list)
    clock_reset: ClockResetMapping = Field(default_factory=ClockResetMapping)
    assumptions: list[Assumption] = Field(default_factory=list)
    guarantees: list[Guarantee] = Field(default_factory=list)
    properties: list[ContractProperty] = Field(default_factory=list)
    negative_scenarios: list[NegativeScenario] = Field(default_factory=list)
    dependencies: list[PropertyDependency] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)


# --------------------------------------------------------------------------- #
# Contract request (spec: how the user names roles for an instance)
# --------------------------------------------------------------------------- #


class ContractRequest(BaseModel):
    """User-supplied binding of protocol roles to RTL signal names.

    We never guess a role binding: the user (or a reviewed upstream tool) must
    say which manifest signal plays which role. Unbound optional roles are simply
    absent; unbound *required* roles produce a blocking warning.
    """

    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    module: str
    instance_label: str | None = None
    # role -> signal name in the manifest module
    roles: dict[str, str] = Field(default_factory=dict)
    clock: str | None = None
    reset: str | None = None
    # Optional explicit reset semantics override (still reviewed).
    reset_polarity: ResetPolarity | None = None
    # For FIFO / credit: declare depth so outstanding-count logic is explicit.
    depth: int | None = None
    max_credits: int | None = None
    # bounded-response window for req/grant and interrupt latency, if specified.
    min_delay: int | None = None
    max_delay: int | None = None
