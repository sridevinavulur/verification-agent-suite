"""Typer CLI for verification-report-kit.

Commands::

    vrk render --in report.json --out report.html
    vrk validate --in report.json
    vrk schema --out report.schema.json
    vrk demo --kind coverage --out demo.html
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from . import __version__
from .html_renderer import render_html
from .json_writer import load_json, write_json
from .models import ReportModel

app = typer.Typer(
    add_completion=False,
    help="verification-report-kit: render verification reports to self-contained HTML/JSON.",
)


@app.command()
def render(
    in_: Path = typer.Option(..., "--in", "-i", help="Input report JSON."),
    out: Path = typer.Option(..., "--out", "-o", help="Output HTML file."),
) -> None:
    """Render a report JSON to a self-contained HTML file."""
    report = load_json(in_)
    html = render_html(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    typer.echo(f"Rendered {in_} -> {out} ({len(html)} bytes)")


@app.command()
def validate(
    in_: Path = typer.Option(..., "--in", "-i", help="Report JSON to validate."),
) -> None:
    """Validate a report JSON against the ReportModel contract."""
    report = load_json(in_)
    typer.echo(
        f"OK: '{report.title}' — schema v{report.schema_version}, "
        f"{len(report.sections)} section(s), {len(report.findings)} finding(s)."
    )


@app.command()
def schema(
    out: Path = typer.Option(..., "--out", "-o", help="Where to write JSON Schema."),
) -> None:
    """Export the ReportModel JSON Schema."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ReportModel.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote schema -> {out}")


@app.command()
def demo(
    kind: str = typer.Option("coverage", "--kind", "-k", help="coverage | findings"),
    out: Path = typer.Option(Path("demo.html"), "--out", "-o"),
    json_out: Path = typer.Option(None, "--json-out", help="Also write the report JSON."),
) -> None:
    """Render a built-in demo report (coverage or findings style)."""
    from .examples_data import coverage_report, findings_report

    if kind == "coverage":
        report = coverage_report()
    elif kind == "findings":
        report = findings_report()
    else:
        raise typer.BadParameter("kind must be 'coverage' or 'findings'")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(report), encoding="utf-8")
    typer.echo(f"Wrote demo ({kind}) -> {out}")
    if json_out is not None:
        write_json(report, json_out)
        typer.echo(f"Wrote demo JSON -> {json_out}")


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


def main() -> None:  # pragma: no cover - entry point wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
