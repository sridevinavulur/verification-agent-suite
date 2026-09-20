"""Typer CLI for security-property-agent."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from . import __version__
from .io_utils import dump_report, load_requirement_set, write_report
from .manifest import load_manifest
from .pipeline import run_pipeline
from .schema_export import export_all
from .util import git_sha, sha256_file

app = typer.Typer(
    add_completion=False,
    help="Transform structured security requirements into reviewable candidate SVA.",
)


@app.command()
def run(
    requirements: Path = typer.Argument(..., help="Requirement set YAML/JSON."),
    manifest: Path = typer.Option(..., "--manifest", "-m", help="RTL Intent Manifest JSON."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write report JSON here."),
    run_id: str = typer.Option("run-0001", "--run-id", help="Run identifier."),
) -> None:
    """Run the full pipeline and emit a SecurityReviewReport."""
    if not requirements.exists():
        typer.secho(f"requirements not found: {requirements}", fg="red", err=True)
        raise typer.Exit(2)
    if not manifest.exists():
        typer.secho(f"manifest not found: {manifest}", fg="red", err=True)
        raise typer.Exit(2)

    reqset = load_requirement_set(requirements)
    view = load_manifest(manifest)
    input_hashes = {
        str(requirements): sha256_file(requirements),
        str(manifest): sha256_file(manifest),
    }
    report = run_pipeline(
        reqset,
        view,
        run_id=run_id,
        git_sha=git_sha(Path(__file__).parent),
        command=" ".join(sys.argv),
        input_hashes=input_hashes,
    )

    if out:
        write_report(report, out)
        typer.secho(f"wrote {out}", fg="green")

    # Human-readable summary to stderr; JSON to stdout for piping.
    n_cand = sum(len(a.candidates) for a in report.artifacts)
    n_mut = sum(len(a.mutations) for a in report.artifacts)
    n_err = sum(1 for a in report.artifacts if a.has_errors)
    typer.secho(
        f"[{report.run_id}] requirements={len(report.artifacts)} "
        f"candidates={n_cand} mutations={n_mut} with_errors={n_err}",
        fg="cyan",
        err=True,
    )
    typer.secho(
        "REMINDER: all output is CANDIDATE material for human review; "
        "no security property was proven.",
        fg="yellow",
        err=True,
    )
    if not out:
        typer.echo(dump_report(report))


@app.command()
def decompose(
    requirements: Path = typer.Argument(..., help="Requirement set YAML/JSON."),
) -> None:
    """Show requirement decomposition only (no grounding/generation)."""
    from .decompose import decompose as _decompose

    reqset = load_requirement_set(requirements)
    for req in reqset.requirements:
        result = _decompose(req, git_sha=git_sha(Path(__file__).parent))
        typer.secho(f"\n# {req.requirement_id} [{req.category.value}]", fg="cyan")
        typer.echo(f"  sha256={result.original_text_sha256[:16]}...")
        for c in result.clauses:
            typer.echo(f"  - [{c.kind.value}] {c.text!r}")
        for a in result.ambiguities:
            typer.secho(f"  ! {a}", fg="yellow")


@app.command("export-schemas")
def export_schemas(
    out_dir: Path = typer.Option(Path("schemas"), "--out-dir", "-o"),
) -> None:
    """Export JSON Schema for the public contracts."""
    for p in export_all(out_dir):
        typer.secho(f"wrote {p}", fg="green")


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


def main() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
