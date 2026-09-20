"""Typer CLI for the RTL Intent Ingestor: ``rtl-intent``.

Commands:
* ``ingest``   - parse RTL files -> JSON manifest (+ optional Markdown)
* ``summary``  - parse RTL files -> Markdown summary to stdout
* ``adapters`` - list available parser adapters
* ``schema``   - print the JSON Schema for the manifest contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import __version__
from .adapters import available_adapters
from .manifest import build_manifest_from_files
from .models import Manifest
from .report import render_markdown
from .serialize import manifest_to_json

app = typer.Typer(
    add_completion=False,
    help="RTL Intent Ingestor - normalized design-intelligence manifests "
    "from a constrained Verilog subset (v0.1, no LLM).",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"rtl-intent {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """RTL Intent Ingestor."""


@app.command()
def ingest(
    files: list[Path] = typer.Argument(..., help="Verilog/SV source files."),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON manifest to this path (else stdout)."
    ),
    markdown: Path = typer.Option(
        None, "--markdown", "-m", help="Also write a Markdown summary here."
    ),
    top: str = typer.Option(None, "--top", help="Explicit top module name."),
    adapter: str = typer.Option(
        "builtin", "--adapter", help="Parser adapter to use."
    ),
) -> None:
    """Parse RTL and emit a JSON manifest."""
    _check_files(files)
    command = "rtl-intent ingest " + " ".join(str(f) for f in files)
    manifest = build_manifest_from_files(
        files, adapter_name=adapter, top=top, command=command
    )
    text = manifest_to_json(manifest)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"wrote manifest: {out}", err=True)
    else:
        sys.stdout.write(text)
    if markdown:
        markdown.write_text(render_markdown(manifest), encoding="utf-8")
        typer.echo(f"wrote summary: {markdown}", err=True)

    # Always surface unresolved-construct count to stderr for visibility.
    if manifest.unresolved:
        typer.echo(
            f"note: {len(manifest.unresolved)} unresolved construct(s) - "
            "see manifest 'unresolved' section",
            err=True,
        )


@app.command()
def summary(
    files: list[Path] = typer.Argument(..., help="Verilog/SV source files."),
    top: str = typer.Option(None, "--top", help="Explicit top module name."),
    adapter: str = typer.Option("builtin", "--adapter", help="Parser adapter."),
) -> None:
    """Print a Markdown summary of the parsed design to stdout."""
    _check_files(files)
    command = "rtl-intent summary " + " ".join(str(f) for f in files)
    manifest = build_manifest_from_files(
        files, adapter_name=adapter, top=top, command=command
    )
    sys.stdout.write(render_markdown(manifest))


@app.command()
def adapters() -> None:
    """List available parser adapters."""
    for name in available_adapters():
        typer.echo(name)


@app.command()
def schema(
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON Schema here (else stdout)."
    ),
) -> None:
    """Print the JSON Schema for the manifest contract."""
    js = json.dumps(Manifest.model_json_schema(), indent=2, sort_keys=True) + "\n"
    if out:
        out.write_text(js, encoding="utf-8")
        typer.echo(f"wrote schema: {out}", err=True)
    else:
        sys.stdout.write(js)


def _check_files(files: list[Path]) -> None:
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        typer.echo(f"error: file(s) not found: {', '.join(missing)}", err=True)
        raise typer.Exit(code=2)


def run() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
