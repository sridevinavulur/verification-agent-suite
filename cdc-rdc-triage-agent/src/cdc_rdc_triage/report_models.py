"""Typed output contract for the CDC/RDC triage report.

Every finding produced by this tool is STRUCTURAL and HEURISTIC.  The models
below encode that explicitly:

* ``Evidence.proven`` is always ``False`` for this tool -- we do a structural
  triage, never a formal CDC/RDC proof.  The field exists so a downstream tool
  that *does* prove something can flip it.
* ``Severity`` / ``risk_score`` are heuristic priorities for human review, not
  signoff verdicts.

The report never says "CDC clean" or "RDC clean"; the top-level ``disclaimer``
and ``non_claims`` fields make the authority boundary machine-readable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .manifest_models import SourceLocation


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Severity(StrEnum):
    """Heuristic review priority -- NOT a signoff verdict."""

    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"
    info = "INFO"


class CrossingKind(StrEnum):
    cdc = "CDC"
    rdc = "RDC"


class SyncEvidence(StrEnum):
    """What structural synchronizer evidence, if any, was found on a crossing."""

    two_ff_candidate = "two_ff_synchronizer_candidate"
    multi_ff_candidate = "multi_ff_synchronizer_candidate"
    glossary_cell = "synchronizer_cell_from_glossary"
    none_found = "no_synchronizer_evidence"
    not_applicable = "not_applicable"


class Domain(_Base):
    """A structural clock (or reset) domain identity for a signal/register."""

    clock: str | None = None
    reset: str | None = None

    def label(self) -> str:
        clk = self.clock or "?"
        rst = self.reset or "-"
        return f"clk={clk};rst={rst}"


class Crossing(_Base):
    """A single candidate clock- or reset-domain crossing.

    All fields are structural observations.  ``heuristic`` is always True.
    """

    kind: CrossingKind
    module: str
    src_signal: str
    dst_signal: str
    src_domain: Domain
    dst_domain: Domain
    width_bits: int | None = None
    multi_bit: bool = False
    sync_evidence: SyncEvidence
    sync_depth: int | None = None
    severity: Severity
    risk_score: int = Field(ge=0, le=100)
    heuristic: bool = True
    rationale: list[str] = Field(default_factory=list)
    src_location: SourceLocation | None = None
    dst_location: SourceLocation | None = None


class ModuleTriage(_Base):
    module: str
    clock_domains: list[str] = Field(default_factory=list)
    reset_domains: list[str] = Field(default_factory=list)
    crossings: list[Crossing] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TriageReport(_Base):
    tool: str = "cdc-rdc-triage-agent"
    tool_version: str
    disclaimer: str = (
        "STRUCTURAL HEURISTIC TRIAGE ONLY. This is NOT a CDC/RDC signoff tool "
        "and does not prove any crossing safe or unsafe. Use commercial "
        "CDC/RDC signoff for verification-quality results."
    )
    non_claims: list[str] = Field(
        default_factory=lambda: [
            "Does NOT claim the design is CDC clean.",
            "Does NOT claim the design is RDC clean.",
            "Does NOT claim any synchronizer is correct.",
            "Does NOT prove metastability is handled.",
            "Findings are heuristic and may contain false positives and false negatives.",
        ]
    )
    top: str | None = None
    summary: dict[str, int] = Field(default_factory=dict)
    modules: list[ModuleTriage] = Field(default_factory=list)
    reviewer_checklist: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def all_crossings(self) -> list[Crossing]:
        out: list[Crossing] = []
        for m in self.modules:
            out.extend(m.crossings)
        return out
