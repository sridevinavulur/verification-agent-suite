"""Typer CLI for the Assertion Review Agent."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .llm import annotate_report
from .models import ReviewReport, Severity
from .review import review_file

app = typer.Typer(
    add_completion=False,
    help="Deterministic static review of SystemVerilog Assertions (SVA).",
    no_args_is_help=True,
)

_SEV_MARK = {Severity.ERROR: "E", Severity.WARNING: "W", Severity.INFO: "I"}


def _print_text_report(report: ReviewReport, show_explanations: bool) -> None:
    counts = report.counts()
    typer.echo(f"Assertion Review: {report.source_file}")
    if report.manifest_top:
        typer.echo(f"  manifest top : {report.manifest_top}")
    typer.echo(f"  properties   : {report.property_count}")
    typer.echo(
        f"  findings     : {counts['ERROR']} ERROR, "
        f"{counts['WARNING']} WARNING, {counts['INFO']} INFO"
    )
    typer.echo("")

    if not report.findings:
        typer.echo("  No findings.")
    for f in report.findings:
        mark = _SEV_MARK[f.severity]
        heur = " [heuristic]" if f.heuristic else ""
        name = f.property_name or "(unnamed)"
        typer.echo(
            f"  {mark} {f.location.file}:{f.location.line}  "
            f"[{f.check_id.value}] {name}{heur}"
        )
        typer.echo(f"      {f.message}")
        if f.recommendation:
            typer.echo(f"      -> {f.recommendation}")
        if show_explanations and f.explanation:
            typer.echo(f"      (why) {f.explanation}")

    typer.echo("")
    score = report.score()
    typer.echo(
        f"  review score : {score.score}/100  grade {score.grade}  "
        f"(penalty {score.penalty}/{score.max_penalty})"
    )
    typer.echo("")
    typer.echo("  Reviewer checklist:")
    for item in report.checklist:
        typer.echo(f"    {item}")


@app.command()
def review(
    sva_file: Path = typer.Argument(..., exists=True, readable=True, help="SVA source file."),
    manifest: Path | None = typer.Option(
        None, "--manifest", "-m", exists=True, readable=True,
        help="RTL Intent Manifest JSON (canonical rtl-intent-ingestor output "
        "or this reviewer's fixture format).",
    ),
    manifest_format: str = typer.Option(
        "auto", "--manifest-format",
        help="Manifest format: auto | canonical | fixture.",
    ),
    requirements: Path | None = typer.Option(
        None, "--requirements", "-r", exists=True, readable=True,
        help="JSON file: list of known requirement IDs.",
    ),
    fmt: str = typer.Option("text", "--format", "-f", help="Output: text | json"),
    explain: bool = typer.Option(
        False, "--explain", help="Attach mock-LLM explanations to findings."
    ),
    fail_on: str = typer.Option(
        "error", "--fail-on", help="Exit non-zero if findings at/above: error|warning|none",
    ),
) -> None:
    """Review one SVA file and print an issue list, score, and checklist."""
    req_ids: set[str] | None = None
    if requirements is not None:
        data = json.loads(requirements.read_text())
        req_ids = set(data if isinstance(data, list) else data.get("requirements", []))

    report = review_file(
        sva_file,
        manifest_path=manifest,
        requirement_ids=req_ids,
        manifest_format=manifest_format,
    )
    if explain:
        report = annotate_report(report)

    if fmt == "json":
        typer.echo(report.model_dump_json(indent=2))
    else:
        _print_text_report(report, show_explanations=explain)

    counts = report.counts()
    threshold = fail_on.lower()
    if threshold == "error" and counts["ERROR"] > 0:
        raise typer.Exit(code=1)
    if threshold == "warning" and (counts["ERROR"] > 0 or counts["WARNING"] > 0):
        raise typer.Exit(code=1)


@app.command()
def schema(
    out_dir: Path = typer.Option(
        Path("schemas"), "--out", help="Directory to write JSON Schema files."
    ),
) -> None:
    """Export JSON Schema for the main Pydantic contracts."""
    from .models import ReviewReport as _RR
    from .models import RtlIntentManifest as _M

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "review_report.schema.json").write_text(
        json.dumps(_RR.model_json_schema(), indent=2)
    )
    (out_dir / "rtl_intent_manifest.schema.json").write_text(
        json.dumps(_M.model_json_schema(), indent=2)
    )
    typer.echo(f"Wrote schemas to {out_dir}/")


@app.command()
def demo() -> None:
    """Run the reviewer on the bundled bad example (self-contained smoke test)."""
    here = Path(__file__).resolve().parent
    root = here.parent.parent  # repo root (…/src/assertion_review -> repo)
    bad = root / "examples" / "bad" / "handshake_bad.sv"
    man = root / "examples" / "manifests" / "handshake.manifest.json"
    if not bad.exists():
        typer.echo("Bundled example not found; run from a source checkout.")
        raise typer.Exit(code=2)
    report = review_file(bad, manifest_path=man if man.exists() else None)
    _print_text_report(report, show_explanations=False)


if __name__ == "__main__":
    app()
