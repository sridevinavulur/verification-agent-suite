"""Typer CLI for the Performance Regression Agent."""

from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .benchmark import build_dataset
from .detector import analyze
from .io_utils import load_dataset, write_report_json
from .models import DetectionConfig, TelemetryDataset
from .renderer import render_markdown
from .schema_export import export_all

app = typer.Typer(
    add_completion=False,
    help="Detect and explain performance regressions across commits/configs/platforms.",
)


def _make_config(
    min_pct: float,
    robust_z: float,
    min_samples: int,
) -> DetectionConfig:
    return DetectionConfig(
        min_pct_change=min_pct,
        robust_z_threshold=robust_z,
        min_samples_for_confident=min_samples,
    )


def _emit(dataset: TelemetryDataset, cfg: DetectionConfig,
          json_out: Path | None, md_out: Path | None,
          quiet: bool) -> int:
    report = analyze(dataset, cfg)

    if json_out:
        write_report_json(report, json_out)
        if not quiet:
            typer.echo(f"Wrote JSON report: {json_out}")
    if md_out:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(report), encoding="utf-8")
        if not quiet:
            typer.echo(f"Wrote Markdown report: {md_out}")

    if not quiet:
        typer.echo(
            f"Runs={report.n_runs} comparisons={report.n_comparisons} "
            f"regressions={report.n_regressions}"
        )
        for f in report.regressions():
            typer.echo(
                f"  REGRESSION {f.metric.value} [{f.config}/{f.workload}] "
                f"{f.delta_pct:+.1f}% (robust z={f.robust_z:+.2f}, "
                f"confidence={f.confidence:.2f})"
            )

    # Non-zero exit when regressions are present (useful as a CI gate).
    return 1 if report.n_regressions > 0 else 0


@app.command()
def version() -> None:
    """Print the tool version."""
    typer.echo(__version__)


@app.command(name="analyze")
def analyze_cmd(
    dataset_path: Path = typer.Argument(..., help="Path to telemetry dataset JSON"),
    json_out: Path | None = typer.Option(None, "--json", help="Write JSON report here"),
    md_out: Path | None = typer.Option(None, "--md", help="Write Markdown report here"),
    min_pct: float = typer.Option(5.0, help="Minimum |Δ%| to flag"),
    robust_z: float = typer.Option(3.5, help="Robust z threshold"),
    min_samples: int = typer.Option(3, help="Min samples for confident verdict"),
    fail_on_regression: bool = typer.Option(
        False, help="Exit non-zero if any regression is found"
    ),
    quiet: bool = typer.Option(False, help="Suppress stdout summary"),
) -> None:
    """Analyze a telemetry dataset and report regressions."""
    dataset = load_dataset(dataset_path)
    cfg = _make_config(min_pct, robust_z, min_samples)
    code = _emit(dataset, cfg, json_out, md_out, quiet)
    if fail_on_regression and code != 0:
        raise typer.Exit(code=code)


@app.command()
def gen_benchmark(
    out: Path = typer.Argument(..., help="Where to write the benchmark dataset JSON"),
) -> None:
    """Generate the deterministic public mock-telemetry benchmark."""
    dataset = build_dataset()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote benchmark ({len(dataset.runs)} runs): {out}")


@app.command()
def demo(
    json_out: Path | None = typer.Option(None, "--json", help="Write JSON report here"),
    md_out: Path | None = typer.Option(None, "--md", help="Write Markdown report here"),
) -> None:
    """Run the detector on the built-in benchmark and print a summary."""
    dataset = build_dataset()
    cfg = DetectionConfig()
    _emit(dataset, cfg, json_out, md_out, quiet=False)


@app.command()
def export_schemas(
    out_dir: Path = typer.Argument(..., help="Directory to write JSON Schema files"),
) -> None:
    """Export JSON Schema for the public Pydantic contracts."""
    written = export_all(out_dir)
    for p in written:
        typer.echo(f"Wrote {p}")


@app.command()
def show_report(
    dataset_path: Path = typer.Argument(..., help="Path to telemetry dataset JSON"),
) -> None:
    """Print the Markdown report to stdout (no files written)."""
    dataset = load_dataset(dataset_path)
    report = analyze(dataset, DetectionConfig())
    typer.echo(render_markdown(report))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
