"""Typer CLI for the CDC/RDC Triage Agent: ``cdc-rdc-triage``.

Commands:
* ``triage``  - read an RTL Intent Manifest -> JSON triage report (+ optional Markdown)
* ``report``  - read a manifest -> Markdown report to stdout
* ``schema``  - print the JSON Schema for the triage report contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import __version__
from .analyze import analyze_manifest
from .glossary import Glossary
from .report import render_markdown
from .report_models import TriageReport
from .serialize import load_manifest, report_to_json

app = typer.Typer(
    add_completion=False,
    help="CDC/RDC Triage Agent - deterministic STRUCTURAL, HEURISTIC triage of "
    "clock/reset-domain crossings from an RTL Intent Manifest. NOT a signoff tool.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cdc-rdc-triage {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """CDC/RDC Triage Agent."""


def _load(manifest: Path, glossary: Path | None) -> tuple:
    if not manifest.is_file():
        typer.echo(f"error: manifest not found: {manifest}", err=True)
        raise typer.Exit(code=2)
    gl = Glossary.empty()
    if glossary is not None:
        if not glossary.is_file():
            typer.echo(f"error: glossary not found: {glossary}", err=True)
            raise typer.Exit(code=2)
        gl = Glossary.load(glossary)
    m = load_manifest(manifest)
    return m, gl


@app.command()
def triage(
    manifest: Path = typer.Argument(..., help="RTL Intent Manifest JSON file."),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON triage report here (else stdout)."
    ),
    markdown: Path = typer.Option(
        None, "--markdown", "-m", help="Also write a Markdown report here."
    ),
    glossary: Path = typer.Option(
        None, "--glossary", "-g", help="Optional synchronizer-cell glossary JSON."
    ),
) -> None:
    """Analyze a manifest and emit a JSON triage report."""
    m, gl = _load(manifest, glossary)
    report = analyze_manifest(m, glossary=gl, tool_version=__version__)
    text = report_to_json(report)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"wrote triage report: {out}", err=True)
    else:
        sys.stdout.write(text)
    if markdown:
        markdown.write_text(render_markdown(report), encoding="utf-8")
        typer.echo(f"wrote markdown report: {markdown}", err=True)

    typer.echo(
        f"note: {report.summary.get('total_crossings', 0)} candidate crossing(s) "
        f"[{report.summary.get('high_severity', 0)} HIGH] -- HEURISTIC, not signoff",
        err=True,
    )


@app.command()
def report(
    manifest: Path = typer.Argument(..., help="RTL Intent Manifest JSON file."),
    glossary: Path = typer.Option(
        None, "--glossary", "-g", help="Optional synchronizer-cell glossary JSON."
    ),
) -> None:
    """Print a Markdown triage report to stdout."""
    m, gl = _load(manifest, glossary)
    rep = analyze_manifest(m, glossary=gl, tool_version=__version__)
    sys.stdout.write(render_markdown(rep))


@app.command()
def schema(
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON Schema here (else stdout)."
    ),
) -> None:
    """Print the JSON Schema for the triage report contract."""
    js = json.dumps(TriageReport.model_json_schema(), indent=2, sort_keys=True) + "\n"
    if out:
        out.write_text(js, encoding="utf-8")
        typer.echo(f"wrote schema: {out}", err=True)
    else:
        sys.stdout.write(js)


def run() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
