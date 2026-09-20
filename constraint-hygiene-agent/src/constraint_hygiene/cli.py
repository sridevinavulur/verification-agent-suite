"""Typer CLI for the Constraint Hygiene Agent."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import __version__
from .engine import analyze_files
from .models import HygieneReport, Severity
from .report import render_markdown

app = typer.Typer(
    add_completion=False,
    help="Static constraint-hygiene review for SVA assumptions/assertions/covers.",
    no_args_is_help=True,
)


@app.command()
def review(
    sva: Path = typer.Argument(..., exists=True, readable=True, help="SVA file to review."),
    manifest: Path = typer.Option(
        None,
        "--manifest",
        "-m",
        exists=True,
        readable=True,
        help="RTL Intent Manifest JSON (for signal-ownership classification).",
    ),
    fmt: str = typer.Option("md", "--format", "-f", help="Output format: md | json."),
    out: Path = typer.Option(None, "--out", "-o", help="Write output to this file."),
    fail_on: str = typer.Option(
        "none",
        "--fail-on",
        help="Exit non-zero if any finding at/above this severity: error | warning | none.",
    ),
) -> None:
    """Review SVA constraints for hygiene problems (static, human-gated)."""
    command = f"constraint-hygiene review {sva}" + (f" --manifest {manifest}" if manifest else "")
    report = analyze_files(sva, manifest, command=command)

    if fmt == "json":
        text = report.model_dump_json(indent=2)
    elif fmt == "md":
        text = render_markdown(report)
    else:
        raise typer.BadParameter("format must be 'md' or 'json'")

    if out:
        out.write_text(text)
        typer.echo(f"Wrote {fmt} report to {out}")
    else:
        typer.echo(text)

    code = _exit_code(report, fail_on)
    if code:
        raise typer.Exit(code)


@app.command()
def schema() -> None:
    """Print the JSON Schema for the HygieneReport contract."""
    typer.echo(json.dumps(HygieneReport.model_json_schema(), indent=2))


@app.command()
def version() -> None:
    """Print the tool version."""
    typer.echo(__version__)


def _exit_code(report: HygieneReport, fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = {"warning": {Severity.WARNING, Severity.ERROR}, "error": {Severity.ERROR}}
    wanted = threshold.get(fail_on)
    if wanted is None:
        raise typer.BadParameter("fail-on must be error | warning | none")
    all_findings = (
        report.contradiction_candidates
        + report.unused_assumption_candidates
        + report.output_constraint_warnings
        + report.vacuity_recommendations
    )
    return 1 if any(f.severity in wanted for f in all_findings) else 0


def run() -> None:
    app()


if __name__ == "__main__":
    run()
