"""Typer CLI for verification-agent-factory.

Commands (prompt pack 4.1):
- init-agent            scaffold a new agent repo from a manifest
- validate-manifest     validate a manifest file, print structured errors
- generate-schema       export the manifest JSON Schema
- generate-docs         render manifest -> README sections
- audit-public-release  secret / proprietary-name scan of a directory
- run-mock-demo         run the deterministic mock LLM adapter end-to-end
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import __version__
from .docgen import render_readme
from .mock_llm import MockLlmAdapter
from .models import VerificationAgentManifest
from .scaffold import scaffold
from .validators import audit_public_release, validate_manifest_file

app = typer.Typer(
    help="Generator for research-grade, verification-integrated agent repos.",
    no_args_is_help=True,
)


def _err(msg: str) -> None:
    # Reports go to stdout so they are captured together with normal output;
    # this is a reporting CLI, not a crashing program.
    typer.secho(msg, fg=typer.colors.RED)


def _ok(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.GREEN)


@app.command()
def version() -> None:
    """Print the factory version."""
    typer.echo(__version__)


@app.command("validate-manifest")
def validate_manifest(
    manifest: Path = typer.Argument(..., exists=True, help="Manifest JSON/YAML file."),
) -> None:
    """Validate a VerificationAgentManifest file."""
    result = validate_manifest_file(manifest)
    if result.ok:
        _ok(f"VALID: {manifest} -> agent_id '{result.manifest.agent_id}'")  # type: ignore[union-attr]
        return
    _err(f"INVALID: {manifest}")
    for e in result.errors:
        _err(f"  - {e}")
    raise typer.Exit(code=1)


@app.command("init-agent")
def init_agent(
    manifest: Path = typer.Argument(..., exists=True, help="Manifest JSON/YAML file."),
    dest: Path = typer.Option(..., "--dest", "-d", help="Destination directory."),
    overwrite: bool = typer.Option(False, help="Overwrite a non-empty destination."),
) -> None:
    """Scaffold a new agent repository from a manifest."""
    result = validate_manifest_file(manifest)
    if not result.ok:
        _err(f"Refusing to scaffold: manifest {manifest} is invalid:")
        for e in result.errors:
            _err(f"  - {e}")
        raise typer.Exit(code=1)
    assert result.manifest is not None
    try:
        out = scaffold(result.manifest, dest, overwrite=overwrite)
    except FileExistsError as exc:
        _err(str(exc))
        raise typer.Exit(code=1) from exc
    _ok(f"Scaffolded '{result.manifest.agent_id}' at {out.root} ({len(out.files)} files)")
    for f in out.files:
        typer.echo(f"  {f.relative_to(out.root)}")


@app.command("generate-schema")
def generate_schema(
    out: Path = typer.Option(None, "--out", "-o", help="Write schema to this file."),
) -> None:
    """Export the VerificationAgentManifest JSON Schema."""
    schema = VerificationAgentManifest.model_json_schema()
    text = json.dumps(schema, indent=2, sort_keys=True)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        _ok(f"Wrote schema to {out}")
    else:
        typer.echo(text)


@app.command("generate-docs")
def generate_docs(
    manifest: Path = typer.Argument(..., exists=True, help="Manifest JSON/YAML file."),
    out: Path = typer.Option(None, "--out", "-o", help="Write README to this file."),
) -> None:
    """Render manifest -> README/Markdown sections."""
    result = validate_manifest_file(manifest)
    if not result.ok:
        _err(f"INVALID manifest {manifest}:")
        for e in result.errors:
            _err(f"  - {e}")
        raise typer.Exit(code=1)
    assert result.manifest is not None
    readme = render_readme(result.manifest)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(readme, encoding="utf-8")
        _ok(f"Wrote docs to {out}")
    else:
        typer.echo(readme)


@app.command("audit-public-release")
def audit(
    root: Path = typer.Argument(..., exists=True, help="Directory to scan."),
    marker: list[str] = typer.Option(
        None, "--marker", "-m", help="Proprietary/internal marker to grep for (repeatable)."
    ),
) -> None:
    """Scan a directory for secrets and proprietary markers."""
    report = audit_public_release(root, proprietary_markers=marker or [])
    typer.echo(f"Scanned {report.files_scanned} files.")
    if report.blocking:
        _err(f"BLOCKING findings: {len(report.blocking)}")
        for f in report.blocking:
            _err(f"  [{f.rule}] {f.file}:{f.line}  {f.hint}")
    if report.warnings:
        typer.secho(f"Warnings: {len(report.warnings)}", fg=typer.colors.YELLOW)
        for f in report.warnings:
            typer.secho(f"  [{f.rule}] {f.file}:{f.line}  {f.hint}", fg=typer.colors.YELLOW)
    if report.clean:
        _ok("No blocking findings. Safe-to-release (pending human review of warnings).")
    else:
        raise typer.Exit(code=1)


@app.command("run-mock-demo")
def run_mock_demo(
    prompt: str = typer.Option(
        "Propose an SVA for: req -> gnt within 1..3 cycles", help="Prompt for the mock LLM."
    ),
    seed: int = typer.Option(0, help="Deterministic seed."),
) -> None:
    """Exercise the deterministic mock LLM adapter (no network)."""
    adapter = MockLlmAdapter(seed=seed)
    resp = adapter.complete(prompt)
    typer.echo(
        json.dumps(
            {
                "model": resp.model,
                "seed": resp.seed,
                "prompt_sha256": resp.prompt_sha256,
                "text": resp.text,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
