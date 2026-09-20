"""Typer CLI for the Assertion Mutation Agent."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .agent import render_markdown, run_mutation_analysis
from .models import MutationOperator
from .operators import generate_mutants
from .sva import parse_properties

app = typer.Typer(
    add_completion=False,
    help="Assertion Mutation Agent - source-mutation-based SVA quality scoring.",
)


def _read(path: Path) -> str:
    if not path.exists():
        raise typer.BadParameter(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


@app.command()
def mutate(
    rtl: Path = typer.Argument(..., help="RTL (.v/.sv) file to mutate."),
    module: str = typer.Option(None, help="Module name (defaults to file stem)."),
    operator: list[str] = typer.Option(
        None, "--operator", "-o", help="Restrict to operator(s). Repeatable."
    ),
) -> None:
    """List the mutants that would be generated for an RTL file (no execution)."""
    source = _read(rtl)
    mod = module or rtl.stem
    ops = [MutationOperator(o) for o in operator] if operator else None
    mutants = generate_mutants(mod, source, ops)
    typer.echo(f"{len(mutants)} mutant(s) for module '{mod}':")
    for m in mutants:
        typer.echo(f"  [{m.mutant_id}] {m.operator.value}: {m.description}")
        typer.echo(f"      {m.diff.original_line.strip()}")
        typer.echo(f"   -> {m.diff.mutated_line.strip()}")


@app.command()
def properties(
    sva: Path = typer.Argument(..., help="SVA property file."),
) -> None:
    """Parse an SVA file and show properties + referenced signals."""
    text = _read(sva)
    props = parse_properties(text)
    typer.echo(f"{len(props)} propertie(s) in {sva}:")
    for p in props:
        typer.echo(f"  {p.name}: {', '.join(p.referenced_signals) or '(none)'}")


@app.command()
def run(
    rtl: Path = typer.Argument(..., help="RTL (.v/.sv) file to mutate."),
    sva: list[Path] = typer.Argument(..., help="One or more SVA property files."),
    module: str = typer.Option(None, help="Module name (defaults to file stem)."),
    executor: str = typer.Option(
        "mock",
        help=(
            "Executor adapter: 'mock' (default, deterministic, no simulator) or "
            "'verilator' (optional real simulator; requires the verilator binary)."
        ),
    ),
    operator: list[str] = typer.Option(
        None, "--operator", "-o", help="Restrict to operator(s). Repeatable."
    ),
    json_out: Path = typer.Option(
        None, "--json-out", help="Write the JSON report to this path."
    ),
    md_out: Path = typer.Option(
        None, "--md-out", help="Write a Markdown report to this path."
    ),
) -> None:
    """Run mutation analysis and print / write the mutation report."""
    source = _read(rtl)
    mod = module or rtl.stem
    ops = [MutationOperator(o) for o in operator] if operator else None
    property_texts = {str(p): _read(p) for p in sva}

    if executor == "verilator":
        from .verilator_executor import verilator_available

        if not verilator_available():
            typer.echo(
                "WARNING: executor 'verilator' selected but the verilator binary "
                "was not found on PATH. Every mutant will be reported as ERROR "
                "(never a fake PASS). Install verilator or use --executor mock.",
                err=True,
            )

    report = run_mutation_analysis(
        module=mod,
        rtl_source=source,
        rtl_file=str(rtl),
        property_texts=property_texts,
        operators=ops,
        executor_name=executor,
    )

    if json_out:
        json_out.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        typer.echo(f"Wrote JSON report -> {json_out}")
    if md_out:
        md_out.write_text(render_markdown(report), encoding="utf-8")
        typer.echo(f"Wrote Markdown report -> {md_out}")

    s = report.score
    typer.echo("")
    typer.echo(f"Module: {mod}   Executor: {executor}")
    typer.echo(
        f"Mutation score: {s.mutation_score:.2%}  "
        f"({s.detected} detected / {s.scored} scored)"
    )
    typer.echo(
        f"total={s.total} detected={s.detected} survived={s.survived} "
        f"invalid={s.invalid} timeout={s.timeout} error={s.error} "
        f"inconclusive={s.inconclusive}"
    )
    if report.surviving_by_operator:
        typer.echo("Surviving by operator:")
        for op, ids in sorted(report.surviving_by_operator.items()):
            typer.echo(f"  {op}: {len(ids)}")


@app.command()
def demo() -> None:
    """Run the bundled toy benchmark and print the report."""
    root = Path(__file__).resolve().parent.parent.parent
    examples = root / "examples"
    rtl = examples / "counter.v"
    sva_files = [examples / "counter.sva"]
    if not rtl.exists():
        raise typer.BadParameter(
            f"Bundled example not found at {rtl}. Run from a source checkout."
        )
    source = rtl.read_text(encoding="utf-8")
    property_texts = {str(p): p.read_text(encoding="utf-8") for p in sva_files}
    report = run_mutation_analysis(
        module="counter",
        rtl_source=source,
        rtl_file=str(rtl),
        property_texts=property_texts,
    )
    typer.echo(render_markdown(report))


def main() -> None:  # pragma: no cover - entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
