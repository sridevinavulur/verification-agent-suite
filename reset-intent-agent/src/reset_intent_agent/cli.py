"""Typer CLI for the Reset Intent Agent.

Commands:
  * ``analyze``      — analyze RTL or an RTL Intent Manifest, emit reset manifest
  * ``graph``        — emit the reset graph as Graphviz DOT
  * ``report``       — emit a Markdown report
  * ``sva``          — print candidate reset-behavior SVA
  * ``mutate``       — generate reset-defect mutants of an RTL file
  * ``schema``       — export the ResetIntentManifest JSON Schema
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import __version__, agent
from .graph import to_dot
from .models import ResetIntentManifest
from .mutations import generate_mutants
from .report import render_markdown

app = typer.Typer(add_completion=False, help="Reset Intent Agent — reset topology & candidate SVA.")


def _load(input_path: Path, as_manifest: bool, command: str) -> ResetIntentManifest:
    if as_manifest or input_path.suffix == ".json":
        return agent.analyze_manifest_file(input_path, command=command)
    return agent.analyze_rtl_file(input_path, command=command)


@app.command()
def analyze(
    input_path: Path = typer.Argument(..., help="RTL file (.v/.sv) or RTL Intent Manifest (.json)"),
    manifest: bool = typer.Option(
        False, "--manifest", help="Force treating input as an RTL Intent Manifest"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write JSON here (default stdout)"
    ),
) -> None:
    """Analyze RTL/manifest and emit the reset intent manifest as JSON."""
    result = _load(input_path, manifest, command=f"analyze {input_path}")
    js = result.model_dump_json(indent=2)
    if output:
        output.write_text(js + "\n")
        typer.echo(f"wrote {output}")
    else:
        typer.echo(js)


@app.command()
def graph(
    input_path: Path = typer.Argument(...),
    manifest: bool = typer.Option(False, "--manifest"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write DOT here"),
) -> None:
    """Emit the reset graph as Graphviz DOT."""
    result = _load(input_path, manifest, command=f"graph {input_path}")
    dot = to_dot(result.reset_graph, name=(result.design_top or "reset_graph").replace("-", "_"))
    if output:
        output.write_text(dot)
        typer.echo(f"wrote {output}")
    else:
        typer.echo(dot)


@app.command()
def report(
    input_path: Path = typer.Argument(...),
    manifest: bool = typer.Option(False, "--manifest"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write Markdown here"),
) -> None:
    """Emit a Markdown reset-intent report."""
    result = _load(input_path, manifest, command=f"report {input_path}")
    md = render_markdown(result)
    if output:
        output.write_text(md)
        typer.echo(f"wrote {output}")
    else:
        typer.echo(md)


@app.command()
def sva(
    input_path: Path = typer.Argument(...),
    manifest: bool = typer.Option(False, "--manifest"),
) -> None:
    """Print candidate reset-behavior SVA (status: candidate)."""
    result = _load(input_path, manifest, command=f"sva {input_path}")
    if not result.candidate_sva:
        typer.echo("// no candidate SVA generated")
        return
    for p in result.candidate_sva:
        typer.echo(f"// {p.property_id} status={p.status.value} polarity={p.reset_polarity.value}")
        typer.echo(p.sva_text)
        typer.echo("")


@app.command()
def mutate(
    input_path: Path = typer.Argument(..., help="RTL file to inject reset defects into"),
    operator: list[str] = typer.Option(None, "--operator", help="Restrict to operators"),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Write each mutant source here"
    ),
) -> None:
    """Generate reset-defect mutants (polarity flip, value change, removal)."""
    source = Path(input_path).read_text()
    mutants = generate_mutants(source, operators=operator or None)
    typer.echo(f"generated {len(mutants)} mutant(s)")
    for mut in mutants:
        typer.echo(f"- {mut.mutant_id} [{mut.operator}] {mut.description}")
        typer.echo(f"    {mut.original_line!r} -> {mut.mutated_line!r}")
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(input_path).stem
            path = output_dir / f"{stem}_{mut.mutant_id}.sv"
            path.write_text(mut.mutated_source)


@app.command()
def schema(
    output: Path | None = typer.Option(None, "--output", "-o", help="Write schema here"),
) -> None:
    """Export the ResetIntentManifest JSON Schema."""
    js = json.dumps(ResetIntentManifest.model_json_schema(), indent=2)
    if output:
        output.write_text(js + "\n")
        typer.echo(f"wrote {output}")
    else:
        typer.echo(js)


@app.command()
def version() -> None:
    """Print the tool version."""
    typer.echo(__version__)


def main() -> None:
    try:
        app()
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
