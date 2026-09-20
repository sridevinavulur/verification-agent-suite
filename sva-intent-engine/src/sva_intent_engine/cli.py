"""Typer CLI for sva-intent-engine.

Commands:
    ingest        decompose a requirement file into atomic clauses
    ground        ground a decomposed requirement against an RTL manifest
    generate      build temporal intents and render candidate SVA
    validate      run static validation on a rendered/intent artifact
    review-report full run -> review packet (JSON)
    demo          run the bundled examples end to end

The deterministic path requires no LLM and no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .grounding import grounding_report
from .io_utils import load_manifest, load_requirement
from .models import Severity
from .pipeline import run_full
from .schema_export import export_all

app = typer.Typer(
    add_completion=False,
    help="Evidence-grounded candidate-SVA generation and review (deterministic).",
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _echo_json(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@app.command()
def ingest(
    requirement_file: Path = typer.Argument(..., exists=True),
    json_out: bool = typer.Option(True, help="Emit JSON (else human summary)."),
) -> None:
    """Decompose a requirement into classified atomic clauses (spec 5.4)."""
    from .decompose import decompose

    req = load_requirement(requirement_file)
    result = decompose(req)
    if json_out:
        _echo_json(result.model_dump())
        return
    typer.echo(f"Requirement {req.requirement_id}: {len(result.clauses)} clause(s)")
    for c in result.clauses:
        typer.echo(f"  [{c.kind.value}] {c.source_span.text}")
        if c.vague_terms:
            typer.echo(f"      vague: {', '.join(c.vague_terms)}")


@app.command()
def ground(
    requirement_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
    json_out: bool = typer.Option(False, help="Emit JSON (else report)."),
    manifest_format: str = typer.Option(
        "auto", "--manifest-format", help="Manifest format: auto | canonical | fixture."
    ),
) -> None:
    """Ground requirement terms against an RTL manifest (spec 5.5)."""
    from .decompose import decompose
    from .grounding import ground_clause

    req = load_requirement(requirement_file)
    manifest = load_manifest(manifest_file, manifest_format=manifest_format)
    decomp = decompose(req)
    results = [ground_clause(c, manifest) for c in decomp.clauses]
    if json_out:
        _echo_json([r.model_dump() for r in results])
        return
    for r in results:
        typer.echo(grounding_report(r))
        typer.echo("")


@app.command()
def generate(
    requirement_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
    json_out: bool = typer.Option(False, help="Emit full JSON review report."),
    manifest_format: str = typer.Option(
        "auto", "--manifest-format", help="Manifest format: auto | canonical | fixture."
    ),
) -> None:
    """Generate candidate SVA end to end (ingest->ground->intent->render)."""
    req = load_requirement(requirement_file)
    manifest = load_manifest(manifest_file, manifest_format=manifest_format)
    report = run_full(req, manifest, command="generate")
    if json_out:
        _echo_json(report.model_dump())
        return
    _print_candidates(report)


@app.command()
def validate(
    requirement_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
    manifest_format: str = typer.Option(
        "auto", "--manifest-format", help="Manifest format: auto | canonical | fixture."
    ),
) -> None:
    """Run static validation and report emitted vs blocked properties."""
    req = load_requirement(requirement_file)
    manifest = load_manifest(manifest_file, manifest_format=manifest_format)
    report = run_full(req, manifest, command="validate")
    emitted = 0
    for v in report.validations:
        status = "EMITTED" if v.emitted else "BLOCKED"
        emitted += int(v.emitted)
        typer.echo(f"{v.clause_id}: {status}")
        for chk in v.checks:
            mark = "ok" if chk.passed else ("FAIL" if chk.severity == Severity.ERROR else "warn")
            typer.echo(f"    [{mark}] {chk.check}"
                       + (f" -- {chk.detail}" if chk.detail else ""))
    typer.echo(f"\n{emitted}/{len(report.validations)} candidate propert(ies) emitted.")


@app.command(name="review-report")
def review_report(
    requirement_file: Path = typer.Argument(..., exists=True),
    manifest_file: Path = typer.Argument(..., exists=True),
    out: Path | None = typer.Option(None, help="Write JSON report to this path."),
    manifest_format: str = typer.Option(
        "auto", "--manifest-format", help="Manifest format: auto | canonical | fixture."
    ),
) -> None:
    """Produce a full JSON review packet for a run."""
    req = load_requirement(requirement_file)
    manifest = load_manifest(manifest_file, manifest_format=manifest_format)
    report = run_full(req, manifest, command="review-report")
    payload = json.dumps(report.model_dump(), indent=2, default=str)
    if out:
        out.write_text(payload + "\n")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(payload)


@app.command(name="export-schemas")
def export_schemas(
    out_dir: Path = typer.Argument(Path("schemas")),
) -> None:
    """Export JSON Schema for all public Pydantic contracts."""
    written = export_all(out_dir)
    for p in written:
        typer.echo(f"wrote {p}")


@app.command()
def demo() -> None:
    """Run all bundled examples end to end and print a summary."""
    manifest_dir = _EXAMPLES / "rtl_manifests"
    reqs = sorted((_EXAMPLES / "requirements").glob("*.md"))
    if not reqs:
        typer.echo("no bundled examples found", err=True)
        raise typer.Exit(1)

    total_emitted = 0
    for rf in reqs:
        # convention: example req 'foo.md' pairs with manifest 'foo.json'
        mf = manifest_dir / f"{rf.stem}.json"
        if not mf.exists():
            typer.echo(f"! no manifest for {rf.name}, skipping")
            continue
        req = load_requirement(rf)
        manifest = load_manifest(mf)
        report = run_full(req, manifest, command="demo")
        emitted = sum(1 for v in report.validations if v.emitted)
        total_emitted += emitted
        typer.echo(f"=== {rf.stem} ===")
        typer.echo(f"  clauses: {len(report.decomposition.clauses)}  "
                   f"intents: {len(report.intents)}  emitted: {emitted}")
        _print_candidates(report, indent="  ")
        typer.echo("")
    typer.echo(f"TOTAL candidate properties emitted: {total_emitted}")
    typer.echo("\nNON-CLAIMS:")
    for nc in [
        "A rendered property is a CANDIDATE, not a verified property.",
        "Clock/reset/bounds are never inferred.",
    ]:
        typer.echo(f"  - {nc}")


def _print_candidates(report, indent: str = "") -> None:
    for v in report.validations:
        if v.emitted and v.candidate:
            typer.echo(f"{indent}{v.candidate.property_name} "
                       f"[{v.candidate.property_form.value}]")
            for line in v.candidate.sva_text.splitlines():
                typer.echo(f"{indent}  {line}")
        elif not v.emitted:
            reasons = [c.detail for c in v.checks
                       if not c.passed and c.severity == Severity.ERROR and c.detail]
            typer.echo(f"{indent}{v.clause_id}: BLOCKED "
                       f"({'; '.join(reasons) if reasons else 'checks failed'})")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
