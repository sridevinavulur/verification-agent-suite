"""Typer CLI for the Formal Regression Intelligence Agent.

Commands:
  analyze   Ingest a run ledger and emit the full JSON RegressionReport.
  report    Ingest a run ledger and emit a Markdown report (optional --explain).
  queue     Print just the prioritized investigation queue.
  explain   Print mock-LLM explanations for the findings.
  schema    Export the JSON Schema for the report / run-record contracts.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import BaseModel

from .analysis import Thresholds, analyze
from .explain import MockLLM, explain_findings
from .ledger import load_ledger
from .models import RegressionReport, RunRecord
from .report import render_markdown

app = typer.Typer(
    add_completion=False,
    help="Deterministic regression intelligence over formal-run ledgers (heuristic).",
)


def _load_and_analyze(ledger: Path) -> RegressionReport:
    led = load_ledger(ledger)
    return analyze(led.records, Thresholds())


@app.command(name="analyze")
def analyze_ledger(
    ledger: Path = typer.Argument(..., exists=True, readable=True, help="Run ledger."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write JSON report here."),
) -> None:
    """Ingest a run ledger and emit the full RegressionReport as JSON."""
    rep = _load_and_analyze(ledger)
    payload = rep.model_dump_json(indent=2)
    if out is not None:
        out.write_text(payload + "\n")
        typer.echo(f"wrote {out} ({len(rep.findings)} findings)")
    else:
        typer.echo(payload)


@app.command()
def report(
    ledger: Path = typer.Argument(..., exists=True, readable=True, help="Run ledger."),
    explain: bool = typer.Option(False, "--explain", help="Include mock-LLM explanations."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write Markdown here."),
) -> None:
    """Ingest a run ledger and emit a Markdown regression report."""
    rep = _load_and_analyze(ledger)
    md = render_markdown(rep, explain=explain, adapter=MockLLM() if explain else None)
    if out is not None:
        out.write_text(md)
        typer.echo(f"wrote {out}")
    else:
        typer.echo(md)


@app.command()
def queue(
    ledger: Path = typer.Argument(..., exists=True, readable=True, help="Run ledger."),
) -> None:
    """Print the prioritized investigation queue."""
    rep = _load_and_analyze(ledger)
    if not rep.investigation_queue:
        typer.echo("No findings.")
        return
    for item in rep.investigation_queue:
        typer.echo(
            f"#{item.rank:<2} [{item.severity.value:>6}] {item.kind.value:<24} "
            f"score={item.priority_score:6.1f}  {item.title}"
        )


@app.command()
def explain(
    ledger: Path = typer.Argument(..., exists=True, readable=True, help="Run ledger."),
) -> None:
    """Print mock-LLM (deterministic) explanations for each finding."""
    rep = _load_and_analyze(ledger)
    texts = explain_findings(rep.findings, MockLLM())
    for f in rep.findings:
        typer.echo(f"== {f.finding_id} ==")
        typer.echo(texts[f.finding_id])
        typer.echo("")


@app.command()
def schema(
    which: str = typer.Argument("report", help="'report' or 'run-record'."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write schema JSON here."),
) -> None:
    """Export the JSON Schema for a contract."""
    models: dict[str, type[BaseModel]] = {
        "report": RegressionReport,
        "run-record": RunRecord,
    }
    model = models.get(which)
    if model is None:
        raise typer.BadParameter("which must be 'report' or 'run-record'")
    payload = json.dumps(model.model_json_schema(), indent=2)
    if out is not None:
        out.write_text(payload + "\n")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(payload)


if __name__ == "__main__":
    app()
