"""Typer CLI for the Coverage Closure Agent.

Commands
--------
* ``triage``   -- run the deterministic classifier on an inputs bundle, emit the
  JSON report (and optional Markdown).
* ``metrics``  -- run triage plus score against a labelled sample.
* ``schema``   -- export JSON Schema for the input and output contracts.
* ``demo``     -- run the bundled toy benchmark end-to-end and print a summary.
* ``ingest-real`` -- OPTIONAL: normalize real Verilator ``.dat`` + lcov ``.info``
  into the mock-cov inputs bundle so ``triage`` can consume it.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .io import load_inputs, load_labels
from .models import TriageInputs, TriageReport
from .real_coverage import ingest_real_inputs
from .report import render_markdown
from .triage import TriageEngine, compute_metrics

app = typer.Typer(
    add_completion=False,
    help="Deterministic coverage-hole triage and ranked next-action recommendations.",
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@app.command()
def triage(
    inputs: Path = typer.Argument(..., help="Path to the JSON inputs bundle."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write JSON report to this path."),
    markdown: Path | None = typer.Option(
        None, "--markdown", "-m", help="Also write a Markdown report to this path."
    ),
    seed: int = typer.Option(0, "--seed", help="Seed recorded in provenance."),
) -> None:
    """Run the deterministic triage engine on an inputs bundle."""
    data = load_inputs(inputs)
    report = TriageEngine(seed=seed).run(data)
    _emit(report, out, markdown)


@app.command()
def metrics(
    inputs: Path = typer.Argument(..., help="Path to the JSON inputs bundle."),
    labels: Path = typer.Argument(..., help="Path to the ground-truth sample labels JSON."),
    seed: int = typer.Option(0, "--seed"),
) -> None:
    """Run triage and score it against a labelled sample."""
    data = load_inputs(inputs)
    report = TriageEngine(seed=seed).run(data)
    sample = load_labels(labels)
    scored = compute_metrics(report.classifications, sample=sample)
    typer.echo(json.dumps(scored.model_dump(mode="json"), indent=2))


@app.command()
def schema(
    out_dir: Path = typer.Option(
        Path("schemas"), "--out-dir", "-d", help="Directory to write JSON Schema files."
    ),
) -> None:
    """Export JSON Schema for the input and output contracts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "triage_inputs.schema.json").write_text(
        json.dumps(TriageInputs.model_json_schema(), indent=2)
    )
    (out_dir / "triage_report.schema.json").write_text(
        json.dumps(TriageReport.model_json_schema(), indent=2)
    )
    typer.echo(f"Wrote schemas to {out_dir}")


@app.command()
def demo(
    seed: int = typer.Option(0, "--seed"),
) -> None:
    """Run the bundled toy benchmark end-to-end and print a summary."""
    inputs_path = _EXAMPLES / "toy_benchmark.json"
    labels_path = _EXAMPLES / "toy_labels.json"
    data = load_inputs(inputs_path)
    report = TriageEngine(seed=seed).run(data)
    sample = load_labels(labels_path)
    scored = compute_metrics(report.classifications, sample=sample)

    typer.echo(render_markdown(report))
    typer.echo("")
    typer.echo("## Sample-scored metrics")
    typer.echo(json.dumps(scored.model_dump(mode="json"), indent=2))


@app.command("ingest-real")
def ingest_real(
    dat: Path | None = typer.Option(
        None, "--dat", help="Path to a real Verilator coverage.dat file."
    ),
    lcov: Path | None = typer.Option(
        None, "--lcov", help="Path to a real lcov .info file."
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Write the normalized inputs bundle JSON here."
    ),
    triage_now: bool = typer.Option(
        False,
        "--triage",
        help="Also run triage on the normalized bundle and print the JSON report.",
    ),
    seed: int = typer.Option(0, "--seed", help="Seed recorded in provenance."),
) -> None:
    """OPTIONAL real-coverage path: normalize Verilator .dat + lcov .info.

    Emits a full ``TriageInputs`` bundle in the normalized mock-cov shape that the
    ``triage`` command consumes. The default hand-authored mock pipeline is
    unaffected. Unreachability hints applied during ingest are HEURISTIC only.
    """
    if dat is None and lcov is None:
        raise typer.BadParameter("Provide at least one of --dat or --lcov.")
    data = ingest_real_inputs(dat_path=dat, lcov_path=lcov)
    bundle_json = json.dumps(data.model_dump(mode="json"), indent=2)
    if out is not None:
        out.write_text(bundle_json)
        typer.echo(f"Wrote normalized inputs bundle to {out}")
    else:
        typer.echo(bundle_json)

    if triage_now:
        report = TriageEngine(seed=seed).run(data)
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


def _emit(report: TriageReport, out: Path | None, markdown: Path | None) -> None:
    payload = json.dumps(report.model_dump(mode="json"), indent=2)
    if out is not None:
        out.write_text(payload)
        typer.echo(f"Wrote JSON report to {out}")
    else:
        typer.echo(payload)
    if markdown is not None:
        markdown.write_text(render_markdown(report))
        typer.echo(f"Wrote Markdown report to {markdown}")


if __name__ == "__main__":
    app()
