"""Typer CLI for the Equivalence Triage Agent.

Commands:

* ``eq-triage triage``  -- run full triage; emit Markdown and/or JSON.
* ``eq-triage parse``   -- parse an equivalence log and print a summary.
* ``eq-triage demo``    -- run a bundled toy inequivalent benchmark end-to-end.
* ``eq-triage schema``  -- export JSON Schema for a data contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .llm import get_adapter
from .models import DesignManifest, EquivalenceLog, SourceMap, TriageReport
from .parser import load_equivalence_log, load_manifest
from .provenance import build_provenance
from .report import render_markdown
from .triage import TriageEngine

app = typer.Typer(
    add_completion=False,
    help="Deterministic, evidence-grounded equivalence-mismatch triage.",
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _run(
    log_path: Path,
    ref_manifest_path: Path | None,
    rev_manifest_path: Path | None,
    source_map_path: Path | None,
    command: str,
) -> TriageReport:
    log = load_equivalence_log(log_path)
    ref_manifest = load_manifest(ref_manifest_path) if ref_manifest_path else None
    rev_manifest = load_manifest(rev_manifest_path) if rev_manifest_path else None
    source_map = None
    if source_map_path:
        source_map = SourceMap.model_validate_json(source_map_path.read_text())

    inputs = [log_path]
    for p in (ref_manifest_path, rev_manifest_path, source_map_path):
        if p:
            inputs.append(p)

    provenance = build_provenance(command, inputs)
    engine = TriageEngine(log, ref_manifest, rev_manifest, source_map)
    return engine.run(
        provenance=provenance,
        repro_command=command,
        input_files=[str(p) for p in inputs],
    )


@app.command()
def triage(
    log: Path = typer.Option(..., exists=True, help="Equivalence log (EQLOG/1)."),
    ref_manifest: Path = typer.Option(
        None, exists=True, help="Reference design manifest JSON."
    ),
    rev_manifest: Path = typer.Option(
        None, exists=True, help="Revised design manifest JSON."
    ),
    source_map: Path = typer.Option(
        None, exists=True, help="SourceMap JSON (signal -> location)."
    ),
    out_json: Path = typer.Option(None, help="Write TriageReport JSON here."),
    out_md: Path = typer.Option(None, help="Write Markdown report here."),
    narrate: bool = typer.Option(
        False, help="Attach an offline mock-LLM advisory narrative to stdout."
    ),
) -> None:
    """Run full triage and emit an evidence-grounded report."""
    cmd = f"eq-triage triage --log {log}"
    if ref_manifest:
        cmd += f" --ref-manifest {ref_manifest}"
    if rev_manifest:
        cmd += f" --rev-manifest {rev_manifest}"
    if source_map:
        cmd += f" --source-map {source_map}"

    report = _run(log, ref_manifest, rev_manifest, source_map, cmd)
    md = render_markdown(report)

    if out_json:
        out_json.write_text(report.model_dump_json(indent=2))
        typer.echo(f"Wrote JSON report to {out_json}")
    if out_md:
        out_md.write_text(md)
        typer.echo(f"Wrote Markdown report to {out_md}")
    if not out_json and not out_md:
        typer.echo(md)
    if narrate:
        typer.echo("\n---\n" + get_adapter("mock").narrate(report))


@app.command()
def parse(
    log: Path = typer.Option(..., exists=True, help="Equivalence log (EQLOG/1)."),
) -> None:
    """Parse an equivalence log and print a deterministic summary."""
    parsed = load_equivalence_log(log)
    typer.echo(f"tool: {parsed.tool} v{parsed.tool_version}")
    typer.echo(f"status: {parsed.status.value}")
    typer.echo(f"reference: {parsed.reference_design}")
    typer.echo(f"revised: {parsed.revised_design}")
    typer.echo(
        f"compare_points: {parsed.compare_points_matched}/"
        f"{parsed.compare_points_total}"
    )
    typer.echo(f"mismatches: {len(parsed.mismatches)}")
    for mp in parsed.mismatches:
        cex = "" if mp.counterexample is None else " (cex)"
        typer.echo(f"  - {mp.name} [{mp.kind.value}]{cex}")
    if parsed.config_deltas:
        typer.echo("config_deltas:")
        for d in parsed.config_deltas:
            typer.echo(f"  - {d.key}: ref={d.reference_value} rev={d.revised_value}")


@app.command()
def demo(
    name: str = typer.Argument("toy_alu", help="Bundled example: toy_alu | toy_counter."),
    out_md: Path = typer.Option(None, help="Optional path to write the report."),
    narrate: bool = typer.Option(True, help="Attach the mock-LLM narrative."),
) -> None:
    """Run a bundled toy inequivalent benchmark end-to-end."""
    d = EXAMPLES_DIR / name
    if not d.exists():
        raise typer.BadParameter(f"No such example: {name} (looked in {d}).")
    ref_m = d / "ref_manifest.json"
    rev_m = d / "rev_manifest.json"
    smap = d / "source_map.json"
    report = _run(
        log_path=d / "equivalence.eqlog",
        ref_manifest_path=ref_m if ref_m.exists() else None,
        rev_manifest_path=rev_m if rev_m.exists() else None,
        source_map_path=smap if smap.exists() else None,
        command=f"eq-triage demo {name}",
    )
    md = render_markdown(report)
    if out_md:
        out_md.write_text(md)
        typer.echo(f"Wrote {out_md}")
    else:
        typer.echo(md)
    if narrate:
        typer.echo("\n---\n" + get_adapter("mock").narrate(report))


@app.command()
def schema(
    model: str = typer.Argument(
        "report", help="One of: report, log, manifest, source_map."
    ),
    out: Path = typer.Option(None, help="Write JSON Schema here."),
) -> None:
    """Export the JSON Schema of a data contract."""
    mapping = {
        "report": TriageReport,
        "log": EquivalenceLog,
        "manifest": DesignManifest,
        "source_map": SourceMap,
    }
    if model not in mapping:
        raise typer.BadParameter(
            f"Unknown model '{model}'. Choose from {list(mapping)}."
        )
    js = json.dumps(mapping[model].model_json_schema(), indent=2)
    if out:
        out.write_text(js)
        typer.echo(f"Wrote schema to {out}")
    else:
        typer.echo(js)


def main() -> None:  # pragma: no cover - thin entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
