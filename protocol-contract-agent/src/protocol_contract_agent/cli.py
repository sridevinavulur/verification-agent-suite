"""Typer CLI for the Protocol Contract Agent.

Commands:
    protocols       list supported protocols and their roles
    generate        request + manifest -> contract (JSON or Markdown or SVA)
    demo            run all bundled examples end to end
    export-schemas  export JSON Schema for the public contracts
    mutate          show property mutations for a generated contract (quality aid)

Deterministic; no LLM, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .generator import blocking_warnings, generate_contract
from .io_utils import load_manifest, load_request, sha256_file
from .mutation import mutate_all
from .report import render_markdown, render_sva_file
from .schema_export import export_all
from .templates import REQUIRED_ROLES

app = typer.Typer(
    add_completion=False,
    help="Generate reviewable interface contracts (candidate SVA) for RTL protocols.",
)

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES = _ROOT / "examples"


def _echo_json(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@app.command()
def protocols() -> None:
    """List supported protocols and their required/optional roles."""
    for proto, (req, opt) in REQUIRED_ROLES.items():
        typer.echo(f"{proto}:")
        typer.echo(f"    required: {', '.join(req)}")
        typer.echo(f"    optional: {', '.join(opt) if opt else '(none)'}")


@app.command()
def generate(
    request_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
    fmt: str = typer.Option("markdown", "--format", "-f",
                            help="markdown | json | sva"),
    out: Path | None = typer.Option(None, help="Write output to this path."),
) -> None:
    """Generate a protocol contract from a request + RTL manifest."""
    request = load_request(request_file)
    manifest = load_manifest(manifest_file)
    contract = generate_contract(
        request, manifest,
        command=f"generate {request_file.name} {manifest_file.name}",
    )
    contract.provenance.input_sha256 = {
        request_file.name: sha256_file(request_file),
        manifest_file.name: sha256_file(manifest_file),
    }

    if fmt == "json":
        payload = json.dumps(contract.model_dump(), indent=2, default=str)
    elif fmt == "sva":
        payload = render_sva_file(contract)
    elif fmt == "markdown":
        payload = render_markdown(contract)
    else:
        typer.echo(f"unknown format {fmt!r}", err=True)
        raise typer.Exit(2)

    if out:
        out.write_text(payload + "\n")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(payload)

    blockers = blocking_warnings(contract)
    if blockers:
        typer.echo(f"\n{len(blockers)} BLOCKING warning(s):", err=True)
        for w in blockers:
            typer.echo(f"  [{w.code}] {w.message}", err=True)


@app.command()
def demo() -> None:
    """Run every bundled example (request + matching manifest) end to end."""
    req_dir = _EXAMPLES / "specs"
    man_dir = _EXAMPLES / "rtl_manifests"
    reqs = sorted(req_dir.glob("*.json"))
    if not reqs:
        typer.echo("no bundled examples found", err=True)
        raise typer.Exit(1)

    total_props = 0
    for rf in reqs:
        request = load_request(rf)
        mf = man_dir / f"{rf.stem}.json"
        if not mf.exists():
            typer.echo(f"! no manifest for {rf.name}, skipping")
            continue
        manifest = load_manifest(mf)
        contract = generate_contract(request, manifest, command="demo")
        total_props += len(contract.properties)
        n_err = len(blocking_warnings(contract))
        typer.echo(f"=== {rf.stem} [{contract.protocol.value}] ===")
        typer.echo(
            f"  roles: {len(contract.signal_roles)}  "
            f"assumptions: {len(contract.assumptions)}  "
            f"guarantees: {len(contract.guarantees)}  "
            f"properties: {len(contract.properties)}  "
            f"negatives: {len(contract.negative_scenarios)}  "
            f"checklist: {len(contract.checklist)}  "
            f"blocking: {n_err}"
        )
        for p in contract.properties:
            typer.echo(f"    {p.name} [{p.property_kind.value}]")
        typer.echo("")
    typer.echo(f"TOTAL candidate properties: {total_props}")
    typer.echo("\nNON-CLAIMS:")
    typer.echo("  - Properties are CANDIDATES for human review, not verified.")
    typer.echo("  - Clock/reset polarity and cycle bounds are never invented.")
    typer.echo("  - Output signals are not silently constrained as env inputs.")


@app.command(name="export-schemas")
def export_schemas(out_dir: Path = typer.Argument(Path("schemas"))) -> None:
    """Export JSON Schema for the public Pydantic contracts."""
    for p in export_all(out_dir):
        typer.echo(f"wrote {p}")


@app.command()
def mutate(
    request_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
) -> None:
    """Show property mutations for the generated contract (quality aid).

    A property whose mutations are all identical to the original would be a red
    flag (nothing to mutate); this surfaces that for review."""
    request = load_request(request_file)
    manifest = load_manifest(manifest_file)
    contract = generate_contract(request, manifest, command="mutate")
    total = 0
    for p in contract.properties:
        muts = mutate_all(p.sva_text)
        total += len(muts)
        typer.echo(f"{p.name}: {len(muts)} mutant(s) -> "
                   f"{', '.join(m.operator for m in muts) or '(none applicable)'}")
    typer.echo(f"\nTOTAL mutants: {total}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
