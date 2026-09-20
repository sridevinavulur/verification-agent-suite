"""Typer CLI for register-csr-agent.

Commands:
    normalize   parse a register map (JSON/YAML/CSV/Markdown) -> normalized manifest JSON
    ground      map a manifest onto RTL symbols -> grounding report
    check       run deterministic checks -> discrepancy report (exit 1 if any ERROR)
    generate    render candidate SVA + directed tests
    package     full run -> verification package (JSON) + rendered artifacts on disk
    demo        run the bundled examples end to end
    export-schema  write JSON Schema for the Pydantic contracts

Deterministic path: no LLM, no network. The mock explainer only annotates.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .parsers import ParseError, load_register_map
from .pipeline import build_package, run_from_files
from .renderer import (
    render_checklist,
    render_coverage_matrix,
    render_discrepancy_report,
    render_grounding_report,
    render_sva_file,
)
from .schema_export import export_all

app = typer.Typer(
    add_completion=False,
    help="Deterministic CSR/register-map verification package builder.",
)

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES = _ROOT / "examples"


def _echo_json(obj: object) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@app.command()
def normalize(
    map_file: Path = typer.Argument(..., help="register map file (json/yaml/csv/md)"),
    fmt: str | None = typer.Option(None, "--format", help="override format detection"),
) -> None:
    """Parse and normalize a register map, printing the manifest JSON."""
    try:
        rmap = load_register_map(map_file, fmt)
    except ParseError as exc:
        typer.echo(f"parse error: {exc}", err=True)
        raise typer.Exit(2) from exc
    _echo_json(rmap.model_dump())


@app.command()
def ground(
    map_file: Path = typer.Argument(...),
    rtl_file: Path = typer.Argument(..., help="RTL symbol export or intent manifest JSON"),
    fmt: str | None = typer.Option(None, "--format"),
) -> None:
    """Map a register map onto RTL symbols."""
    pkg = run_from_files(map_file, rtl_file, fmt=fmt, command="ground")
    typer.echo(render_grounding_report(pkg))


@app.command()
def check(
    map_file: Path = typer.Argument(...),
    rtl_file: Path | None = typer.Argument(None),
    fmt: str | None = typer.Option(None, "--format"),
    as_json: bool = typer.Option(False, "--json", help="emit discrepancies as JSON"),
) -> None:
    """Run deterministic checks. Exits 1 if any ERROR-severity discrepancy exists."""
    pkg = run_from_files(map_file, rtl_file, fmt=fmt, command="check")
    if as_json:
        _echo_json([d.model_dump() for d in pkg.discrepancies])
    else:
        typer.echo(render_discrepancy_report(pkg))
    if pkg.error_count:
        raise typer.Exit(1)


@app.command()
def generate(
    map_file: Path = typer.Argument(...),
    fmt: str | None = typer.Option(None, "--format"),
) -> None:
    """Render candidate SVA and directed tests to stdout."""
    rmap = load_register_map(map_file, fmt)
    pkg = build_package(rmap)
    typer.echo(render_sva_file(pkg))


@app.command()
def package(
    map_file: Path = typer.Argument(...),
    rtl_file: Path | None = typer.Argument(None),
    out_dir: Path = typer.Option(Path("csr_package"), "--out", help="output directory"),
    fmt: str | None = typer.Option(None, "--format"),
) -> None:
    """Full run: write package.json plus rendered artifacts into --out."""
    pkg = run_from_files(map_file, rtl_file, fmt=fmt, command="package")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "package.json").write_text(
        json.dumps(pkg.model_dump(), indent=2, default=str) + "\n", encoding="utf-8"
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(pkg.register_map.model_dump(), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (out_dir / "candidate.sva").write_text(render_sva_file(pkg), encoding="utf-8")
    (out_dir / "discrepancies.md").write_text(
        render_discrepancy_report(pkg), encoding="utf-8"
    )
    (out_dir / "coverage.md").write_text(render_coverage_matrix(pkg), encoding="utf-8")
    (out_dir / "grounding.md").write_text(render_grounding_report(pkg), encoding="utf-8")
    (out_dir / "review_checklist.md").write_text(render_checklist(pkg), encoding="utf-8")
    typer.echo(
        f"wrote package to {out_dir}/ "
        f"(errors={pkg.error_count}, warnings={pkg.warning_count}, "
        f"sva={len(pkg.candidate_sva)}, tests={len(pkg.directed_tests)})"
    )
    if pkg.error_count:
        raise typer.Exit(1)


@app.command()
def demo() -> None:
    """Run the bundled examples end to end and summarize."""
    good = _EXAMPLES / "register_maps" / "timer_block.yaml"
    rtl = _EXAMPLES / "rtl_symbols" / "timer_block.json"
    bad = _EXAMPLES / "register_maps" / "buggy_block.json"
    for label, mf, rf in (("clean", good, rtl), ("buggy", bad, None)):
        pkg = run_from_files(mf, rf, command="demo")
        typer.echo(
            f"[{label}] {mf.name}: registers={len(pkg.register_map.registers)} "
            f"errors={pkg.error_count} warnings={pkg.warning_count} "
            f"sva={len(pkg.candidate_sva)} tests={len(pkg.directed_tests)}"
        )


@app.command("export-schema")
def export_schema(
    out_dir: Path = typer.Option(_ROOT / "schemas", "--out"),
) -> None:
    """Write JSON Schema for the Pydantic contracts."""
    written = export_all(out_dir)
    for p in written:
        typer.echo(f"wrote {p}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
