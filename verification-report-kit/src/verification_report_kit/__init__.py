"""verification-report-kit — reusable, dependency-free verification reporting.

Public API::

    from verification_report_kit import (
        ReportModel, Section, Table, Finding, Stat, CoveragePoint,
        Provenance, Status, render_html, write_json, to_json, load_json,
    )

Build a :class:`ReportModel`, then call :func:`render_html` for a
self-contained HTML string or :func:`write_json` to persist the structured
report. No external runtime dependencies beyond pydantic (+ typer for the CLI).
"""
from __future__ import annotations

from .html_renderer import render_html
from .json_writer import load_json, to_json, write_json
from .models import (
    SCHEMA_VERSION,
    SEVERITY_ORDER,
    CoveragePoint,
    Finding,
    Provenance,
    ReportModel,
    Section,
    Stat,
    Status,
    Table,
)

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "SEVERITY_ORDER",
    "CoveragePoint",
    "Finding",
    "Provenance",
    "ReportModel",
    "Section",
    "Stat",
    "Status",
    "Table",
    "render_html",
    "write_json",
    "to_json",
    "load_json",
    "__version__",
]
