"""Pydantic models mirroring the subset of the canonical RTL Intent Manifest
schema that the CDC/RDC triage tool consumes.

The authoritative schema lives in the ``rtl-intent-ingestor`` repo at
``schemas/manifest.schema.json``.  We deliberately model only the fields this
tool reads and set ``model_config = ConfigDict(extra="ignore")`` so that a
richer manifest (extra fields, future schema versions) still loads.  These
models *validate* the input rather than merely annotate it, per the build
standard.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SourceLocation(_Base):
    file: str
    line: int = Field(ge=1)
    col: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=1)


class NetKind(StrEnum):
    wire = "wire"
    reg = "reg"
    logic = "logic"


class Range(_Base):
    msb: str
    lsb: str


class Net(_Base):
    name: str
    net_kind: NetKind
    location: SourceLocation
    is_memory: bool = False
    range: Range | None = None
    unpacked_range: Range | None = None


class PortDirection(StrEnum):
    input = "input"
    output = "output"
    inout = "inout"


class Port(_Base):
    name: str
    direction: PortDirection
    location: SourceLocation
    net_kind: NetKind | None = None
    range: Range | None = None


class Assignment(_Base):
    lhs: str
    rhs: str
    nonblocking: bool
    location: SourceLocation


class SensitivityEntry(_Base):
    signal: str
    edge: str | None = None


class ProcedureKind(StrEnum):
    always_ff = "always_ff"
    always_comb = "always_comb"
    always = "always"


class Procedure(_Base):
    index: int = Field(ge=0)
    kind: ProcedureKind
    location: SourceLocation
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)
    condition_signals: list[str] = Field(default_factory=list)
    assignment_targets: list[str] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    is_star_sensitivity: bool = False


class ContinuousAssign(_Base):
    lhs: str
    rhs: str
    location: SourceLocation


class Register(_Base):
    name: str
    driven_in_procedure_index: int = Field(ge=0)
    location: SourceLocation


class ClockCandidate(_Base):
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    location: SourceLocation | None = None
    rationale: list[str] = Field(default_factory=list)


class ResetPolarity(StrEnum):
    active_high = "active_high"
    active_low = "active_low"
    unknown = "unknown"


class ResetSync(StrEnum):
    synchronous = "synchronous"
    asynchronous = "asynchronous"
    unknown = "unknown"


class ResetCandidate(_Base):
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    location: SourceLocation | None = None
    polarity: ResetPolarity = ResetPolarity.unknown
    sync: ResetSync = ResetSync.unknown
    rationale: list[str] = Field(default_factory=list)


class PortConnection(_Base):
    actual: str
    formal: str | None = None
    location: SourceLocation


class Instance(_Base):
    module: str
    name: str
    location: SourceLocation
    connections: list[PortConnection] = Field(default_factory=list)


class Module(_Base):
    name: str
    location: SourceLocation
    ports: list[Port] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    continuous_assigns: list[ContinuousAssign] = Field(default_factory=list)
    registers: list[Register] = Field(default_factory=list)
    instances: list[Instance] = Field(default_factory=list)
    clock_candidates: list[ClockCandidate] = Field(default_factory=list)
    reset_candidates: list[ResetCandidate] = Field(default_factory=list)


class HierarchyEdge(_Base):
    parent_module: str
    child_module: str
    instance_name: str
    child_defined: bool


class Manifest(_Base):
    schema_version: str = "0.1.0"
    top: str | None = None
    modules: list[Module] = Field(default_factory=list)
    hierarchy: list[HierarchyEdge] = Field(default_factory=list)

    def module_by_name(self, name: str) -> Module | None:
        for m in self.modules:
            if m.name == name:
                return m
        return None
