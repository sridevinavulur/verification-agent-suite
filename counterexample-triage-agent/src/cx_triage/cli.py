"""Typer CLI for the Counterexample Triage Agent.

Commands:

* ``cx-triage triage``   -- run full triage; emit Markdown and/or JSON.
* ``cx-triage parse``    -- parse a trace and print a signal summary.
* ``cx-triage demo``     -- run the bundled toy_counter benchmark end-to-end.
* ``cx-triage schema``   -- export JSON Schema for the report/inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .compose import compose_report
from .executor import get_executor
from .llm import get_adapter
from .manifest_adapter import load_manifest
from .models import AssertionFailure, RTLIntentManifest, TriageReport
from .parser import load_json_trace, parse_vcd_file
from .paths import portable_path
from .report import render_markdown
from .triage import TriageEngine

app = typer.Typer(
    add_completion=False,
    help="Deterministic, evidence-grounded counterexample triage.",
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_trace(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".vcd":
        return parse_vcd_file(path)
    if suffix == ".json":
        return load_json_trace(path)
    raise typer.BadParameter(f"Unsupported trace type: {suffix} (use .vcd or .json)")


def _run(
    trace_path: Path,
    failure_path: Path,
    manifest_path: Path | None,
    repro: str,
    narrate: bool,
    reproduce: bool = False,
) -> TriageReport:
    trace = _load_trace(trace_path)
    failure = AssertionFailure.model_validate_json(failure_path.read_text())
    manifest = None
    if manifest_path is not None:
        # Accepts both the repo-native fixture and the canonical RTL Intent
        # Manifest schema (auto-detected); see manifest_adapter.load_manifest.
        manifest = load_manifest(manifest_path)

    # Emit artifact paths relative to the current working directory so reports
    # are portable (no machine-specific absolute paths) and golden-stable.
    artifacts = [portable_path(trace_path), portable_path(failure_path)]
    if manifest_path is not None:
        artifacts.append(portable_path(manifest_path))

    engine = TriageEngine(trace, failure, manifest)
    report = engine.run(repro_command=repro, artifacts=artifacts)

    if reproduce:
        # Default deterministic reproduction: confirms captured artifacts without
        # running a simulator. Advisory context only; never re-ranks hypotheses.
        result = get_executor(
            "deterministic",
            trace_path=trace_path,
            failure_path=failure_path,
            trace_signal_count=len(trace.signals),
        ).reproduce()
        compose_report(report, repro=result)

    if narrate:
        report.llm_narrative = get_adapter("mock").narrate(report)
    return report


@app.command()
def triage(
    trace: Path = typer.Option(..., exists=True, help="Trace file (.vcd or .json)."),
    failure: Path = typer.Option(..., exists=True, help="AssertionFailure JSON."),
    manifest: Path = typer.Option(
        None, exists=True, help="Optional RTL Intent Manifest JSON."
    ),
    out_json: Path = typer.Option(None, help="Write TriageReport JSON here."),
    out_md: Path = typer.Option(None, help="Write Markdown report here."),
    narrate: bool = typer.Option(
        False, help="Attach an offline mock-LLM advisory narrative."
    ),
    reproduce: bool = typer.Option(
        False,
        help="Attach an advisory reproduction outcome (deterministic re-check).",
    ),
) -> None:
    """Run full triage and emit a report."""
    repro_cmd = (
        f"cx-triage triage --trace {portable_path(trace)}"
        f" --failure {portable_path(failure)}"
        + (f" --manifest {portable_path(manifest)}" if manifest else "")
    )
    report = _run(trace, failure, manifest, repro_cmd, narrate, reproduce=reproduce)

    md = render_markdown(report)
    if out_json:
        out_json.write_text(report.model_dump_json(indent=2))
        typer.echo(f"Wrote JSON report to {out_json}")
    if out_md:
        out_md.write_text(md)
        typer.echo(f"Wrote Markdown report to {out_md}")
    if not out_json and not out_md:
        typer.echo(md)


@app.command()
def parse(
    trace: Path = typer.Option(..., exists=True, help="Trace file (.vcd or .json)."),
) -> None:
    """Parse a trace and print a deterministic signal summary."""
    wt = _load_trace(trace)
    typer.echo(f"timescale: {wt.timescale}")
    typer.echo(f"end_time: {wt.end_time}")
    typer.echo(f"signals: {len(wt.signals)}")
    for name in sorted(wt.signals):
        sig = wt.signals[name]
        typer.echo(f"  {name} (w{sig.width}): {len(sig.samples)} changes")


@app.command()
def demo(
    out_md: Path = typer.Option(None, help="Optional path to write the report."),
    narrate: bool = typer.Option(True, help="Attach the mock-LLM narrative."),
) -> None:
    """Run the bundled toy_counter benchmark end-to-end."""
    d = EXAMPLES_DIR / "toy_counter"
    report = _run(
        trace_path=d / "counter_fail.vcd",
        failure_path=d / "failure.json",
        manifest_path=d / "manifest.json",
        repro="cx-triage demo",
        narrate=narrate,
    )
    md = render_markdown(report)
    if out_md:
        out_md.write_text(md)
        typer.echo(f"Wrote {out_md}")
    else:
        typer.echo(md)


@app.command()
def schema(
    model: str = typer.Argument(
        "report", help="One of: report, failure, manifest."
    ),
    out: Path = typer.Option(None, help="Write JSON Schema here."),
) -> None:
    """Export the JSON Schema of a data contract."""
    mapping = {
        "report": TriageReport,
        "failure": AssertionFailure,
        "manifest": RTLIntentManifest,
    }
    if model not in mapping:
        raise typer.BadParameter(f"Unknown model '{model}'. Choose from {list(mapping)}.")
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
