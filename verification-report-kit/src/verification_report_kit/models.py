"""Stable Pydantic v2 input contract for verification reports.

This is the public data contract that every bounded verification tool can
target when it wants a final HTML/JSON report. It is intentionally *generic*:
it carries no coupling to any specific pipeline (coverage-closure,
formal-run-orchestrator, mutation, triage, supervisor, section-6 agents, ...).

Design goal: a tool builds a :class:`ReportModel`, hands it to
``render_html`` / ``write_json``, and gets a self-contained, deterministic
report. The schema is the compatibility surface, so keep additions
backwards-compatible (add optional fields; do not rename/remove).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

# Consistent result / severity vocabulary (matches BUILD_STANDARD.md).
Severity = str  # one of the values in SEVERITY_ORDER, validated leniently below


class Status(StrEnum):
    """Result vocabulary for findings and section outcomes."""

    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"
    INCONCLUSIVE = "INCONCLUSIVE"
    COMPILED = "COMPILED"  # "property compiled" — syntax only, not proven
    WARN = "WARN"
    SKIP = "SKIP"
    INFO = "INFO"


# Ordered from most to least severe, used to sort/color findings.
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


class Provenance(BaseModel):
    """Run provenance / reproducibility ledger.

    Records enough to reproduce and audit a run. All fields optional so a
    minimal report is still valid, but tools SHOULD populate what they can.
    """

    model_config = ConfigDict(extra="forbid")

    tool: str | None = Field(default=None, description="Producing tool name")
    tool_version: str | None = Field(default=None)
    git_sha: str | None = Field(default=None, description="Source revision")
    command: str | None = Field(default=None, description="Invocation command")
    seed: int | str | None = Field(default=None)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    runtime_seconds: float | None = Field(default=None, ge=0)
    peak_memory_mb: float | None = Field(default=None, ge=0)
    status: Status | None = Field(default=None)
    timestamp: str | None = Field(
        default=None,
        description="ISO-8601 string. Left to the caller so rendering stays "
        "deterministic (no implicit now()).",
    )
    extra: dict[str, Any] = Field(default_factory=dict)


class Stat(BaseModel):
    """A single labelled key/value statistic shown as a headline tile."""

    model_config = ConfigDict(extra="forbid")

    label: str
    value: str | int | float
    unit: str | None = Field(default=None, description="e.g. '%', 'ms'")
    status: Status | None = Field(
        default=None, description="Optional accent for the tile"
    )


class Table(BaseModel):
    """A generic table: headers + rows of cell strings."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None)
    columns: list[str]
    rows: list[list[str | int | float | None]] = Field(default_factory=list)
    note: str | None = Field(default=None, description="Caption below table")


class Finding(BaseModel):
    """A single finding/bug/issue with a severity classification."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    severity: str = Field(
        default="info",
        description="One of: " + ", ".join(SEVERITY_ORDER),
    )
    status: Status | None = Field(default=None)
    category: str | None = Field(default=None)
    description: str | None = Field(default=None)
    suggested_fix: str | None = Field(default=None)
    location: str | None = Field(default=None, description="File/signal/scope")
    heuristic: bool = Field(
        default=False,
        description="True if produced by a heuristic (not sound/formal).",
    )


class CoveragePoint(BaseModel):
    """One row of a coverage-over-time history."""

    model_config = ConfigDict(extra="forbid")

    label: str | int = Field(description="Iteration index or timestamp")
    metrics: dict[str, float] = Field(
        description="metric name -> percent (0..100), e.g. {'line': 92.3}"
    )


class Section(BaseModel):
    """A free-form content section: prose + optional tables/stats.

    Sections let arbitrary tools express their own structure without changing
    the schema. Order is preserved in rendering.
    """

    model_config = ConfigDict(extra="forbid")

    heading: str
    status: Status | None = Field(default=None)
    body: str | None = Field(
        default=None, description="Plain text (rendered as escaped paragraphs)"
    )
    bullets: list[str] = Field(default_factory=list)
    stats: list[Stat] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)


class ReportModel(BaseModel):
    """Top-level, stable report contract.

    A tool populates the fields it has; everything except ``title`` is
    optional. Renderers must tolerate empty collections gracefully.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION)
    title: str
    subtitle: str | None = Field(default=None)
    provenance: Provenance = Field(default_factory=Provenance)
    stats: list[Stat] = Field(
        default_factory=list, description="Headline key/value tiles"
    )
    sections: list[Section] = Field(default_factory=list)
    tables: list[Table] = Field(
        default_factory=list, description="Top-level tables (outside sections)"
    )
    findings: list[Finding] = Field(default_factory=list)
    coverage_history: list[CoveragePoint] = Field(default_factory=list)

    def sorted_findings(self) -> list[Finding]:
        """Findings sorted by severity (most severe first, stable)."""

        def key(f: Finding) -> int:
            sev = (f.severity or "info").lower()
            return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else len(
                SEVERITY_ORDER
            )

        return sorted(self.findings, key=key)
