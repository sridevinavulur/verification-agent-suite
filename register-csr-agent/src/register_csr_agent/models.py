"""Typed data contracts for the CSR verification agent (Pydantic v2).

These models are the authority boundary of the tool. Access semantics
(``AccessType``) are a *closed enum*: the parsers must map source strings onto
these members, and the LLM adapter can never introduce new ones. Everything a
downstream consumer relies on (addresses, widths, reset values, access types,
signal mappings) is validated here, not merely annotated.
"""

from __future__ import annotations

import warnings
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Several output models carry a ``register`` attribute (the register a finding
# refers to). Pydantic 2.13 exposes a ``BaseModel.register`` helper, so it warns
# that the field name shadows it. The field is intentional and JSON-friendly;
# suppress the purely-cosmetic warning rather than rename the public contract.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "register" .*shadows an attribute',
    category=UserWarning,
)


class AccessType(str, Enum):
    """Closed set of supported field/register access semantics.

    The tool refuses to invent semantics; any source token that does not map
    onto one of these members is reported as an ``UNKNOWN_ACCESS`` discrepancy.
    """

    RO = "RO"  # read-only; writes ignored
    RW = "RW"  # read-write
    WO = "WO"  # write-only; reads return 0 (or undefined-but-declared)
    W1C = "W1C"  # write-1-to-clear
    W1S = "W1S"  # write-1-to-set
    RC = "RC"  # read-to-clear
    RESERVED = "RESERVED"  # reserved; reads 0, writes ignored


# Access types whose *stored* value is not simply the written value.
SPECIAL_WRITE_ACCESS = {AccessType.W1C, AccessType.W1S, AccessType.RC}
WRITABLE_ACCESS = {AccessType.RW, AccessType.WO, AccessType.W1C, AccessType.W1S}
READABLE_ACCESS = {AccessType.RO, AccessType.RW, AccessType.W1C, AccessType.W1S, AccessType.RC}


class Privilege(str, Enum):
    """Optional access-privilege annotation for security-sensitive registers."""

    USER = "USER"
    SUPERVISOR = "SUPERVISOR"
    MACHINE = "MACHINE"
    SECURE = "SECURE"
    ANY = "ANY"


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class Field_(BaseModel):
    """A named bit field inside a register.

    ``bit_offset``/``bit_width`` are the normalized bit range. Source formats
    that give ``[msb:lsb]`` are converted to offset/width by the parser.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    bit_offset: int = Field(ge=0)
    bit_width: int = Field(ge=1)
    access: AccessType
    reset_value: int = Field(ge=0)
    description: str = ""
    # Optional semantic annotations (never invented; only used when present in source).
    side_effect: str = ""  # free-text note, e.g. "start_dma", "clears FIFO"
    interrupt_related: bool = False  # part of an interrupt/status handshake
    privilege: Privilege = Privilege.ANY

    @property
    def msb(self) -> int:
        return self.bit_offset + self.bit_width - 1

    @property
    def lsb(self) -> int:
        return self.bit_offset

    @property
    def mask(self) -> int:
        return ((1 << self.bit_width) - 1) << self.bit_offset

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field name must be non-empty")
        return v.strip()

    @model_validator(mode="after")
    def _reset_fits(self) -> Field_:
        if self.reset_value >> self.bit_width:
            raise ValueError(
                f"field {self.name!r} reset_value 0x{self.reset_value:x} does not fit "
                f"in {self.bit_width} bit(s)"
            )
        return self


class Register(BaseModel):
    """A single addressable register."""

    model_config = ConfigDict(extra="forbid")

    name: str
    address: int = Field(ge=0)
    width_bits: int = Field(ge=1)
    access: AccessType = AccessType.RW
    reset_value: int = Field(ge=0)
    description: str = ""
    fields: list[Field_] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("register name must be non-empty")
        return v.strip()

    @property
    def byte_size(self) -> int:
        return (self.width_bits + 7) // 8


class RegisterMap(BaseModel):
    """Normalized register manifest (the tool's canonical intermediate form)."""

    model_config = ConfigDict(extra="forbid")

    name: str = "csr_block"
    data_width_bits: int = Field(default=32, ge=1)
    address_unit_bytes: int = Field(default=1, ge=1)  # bytes per address increment
    registers: list[Register] = Field(default_factory=list)
    source_format: str = "unknown"
    source_file: str = ""


class SymbolKind(str, Enum):
    REGISTER = "register"
    FIELD = "field"
    SIGNAL = "signal"


class RtlSymbol(BaseModel):
    """An RTL symbol (register/field/signal) extracted from an RTL export.

    Signal mappings are grounded against these symbols only. The tool never
    fabricates a symbol that is absent from this list.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: SymbolKind = SymbolKind.SIGNAL
    width_bits: int | None = None
    reset_value: int | None = None
    access: AccessType | None = None
    module: str = ""


class RtlSymbolTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = ""
    symbols: list[RtlSymbol] = Field(default_factory=list)
    source_file: str = ""

    def by_name(self) -> dict[str, RtlSymbol]:
        return {s.name: s for s in self.symbols}


class Discrepancy(BaseModel):
    """A deterministic finding. Never a PASS; always something to review/fix."""

    model_config = ConfigDict(extra="forbid")

    code: str  # stable machine code, e.g. "ADDR_OVERLAP"
    severity: Severity
    register: str = Field(default="")
    field: str = ""
    message: str
    detail: str = ""
    explanation: str = ""  # optional LLM-provided prose; deterministic message stays authoritative

    def key(self) -> tuple[str, str, str, str]:
        return (self.code, self.register, self.field, self.message)


class GroundingResult(BaseModel):
    """Result of mapping one manifest register/field onto an RTL symbol."""

    model_config = ConfigDict(extra="forbid")

    manifest_name: str
    rtl_symbol: str | None = None
    matched: bool = False
    match_kind: str = "none"  # exact | normalized | none
    notes: str = ""


class GroundingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[GroundingResult] = Field(default_factory=list)
    matched_count: int = 0
    total_count: int = 0
    unmatched_manifest: list[str] = Field(default_factory=list)
    unmatched_rtl: list[str] = Field(default_factory=list)


class CandidateSVA(BaseModel):
    """A candidate assertion. Always ``candidate`` — never proven/verified."""

    model_config = ConfigDict(extra="forbid")

    name: str
    register: str = Field(default="")
    field: str = ""
    check: str  # which check family motivated this, e.g. "reset_value"
    sva: str  # rendered SystemVerilog assertion text
    status: str = "candidate"  # constant; deterministic tools never upgrade this
    rationale: str = ""


class DirectedTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    register: str = Field(default="")
    check: str
    steps: list[str] = Field(default_factory=list)
    expected: str = ""


class CoverageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register: str = Field(...)
    field: str = ""
    access: str = ""
    checks_covered: list[str] = Field(default_factory=list)
    sva_count: int = 0
    test_count: int = 0


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str
    why: str
    resolved: bool = False


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = "register-csr-agent"
    tool_version: str = "0.1.0"
    schema_version: str = "0.1.0"
    command: str = ""
    git_sha: str = "UNKNOWN"
    input_files: list[str] = Field(default_factory=list)
    input_sha256: dict[str, str] = Field(default_factory=dict)


class VerificationPackage(BaseModel):
    """Top-level reviewable output artifact."""

    model_config = ConfigDict(extra="forbid")

    provenance: Provenance
    register_map: RegisterMap
    grounding: GroundingReport
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    candidate_sva: list[CandidateSVA] = Field(default_factory=list)
    directed_tests: list[DirectedTest] = Field(default_factory=list)
    coverage: list[CoverageRow] = Field(default_factory=list)
    review_checklist: list[ReviewItem] = Field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.discrepancies if d.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.discrepancies if d.severity == Severity.WARNING)
