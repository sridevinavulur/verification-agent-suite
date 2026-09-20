"""Typer CLI for the Testbench Recovery Agent: ``tb-recover``.

Commands:
* ``inspect``  - statically inspect a repo checkout -> JSON report (+ Markdown)
* ``summary``  - inspect a repo -> Markdown summary to stdout
* ``smoke``    - print the recommended minimal smoke-test command only
* ``schema``   - print the JSON Schema for the RecoveryReport contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import __version__
from .models import Provenance, RecoveryReport
from .recover import recover
from .report import render_markdown
from .serialize import report_to_json

app = typer.Typer(
    add_completion=False,
    help="Testbench Recovery Agent - statically recover build/run/analyze "
    "commands from a verification repo, with file+line evidence (v0.1).",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tb-recover {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Testbench Recovery Agent."""


def _check_repo(repo: Path) -> None:
    if not repo.is_dir():
        typer.echo(f"error: not a directory: {repo}", err=True)
        raise typer.Exit(code=2)


@app.command()
def inspect(
    repo: Path = typer.Argument(..., help="Path to the repository checkout."),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON report here (else stdout)."
    ),
    markdown: Path = typer.Option(
        None, "--markdown", "-m", help="Also write a Markdown summary here."
    ),
) -> None:
    """Statically inspect a repo and emit a JSON recovery report."""
    _check_repo(repo)
    command = f"tb-recover inspect {repo}"
    report = recover(repo, command=command)
    text = report_to_json(report)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"wrote report: {out}", err=True)
    else:
        sys.stdout.write(text)
    if markdown:
        markdown.write_text(render_markdown(report), encoding="utf-8")
        typer.echo(f"wrote summary: {markdown}", err=True)

    n_ex = sum(1 for c in report.candidate_commands
               if c.provenance is Provenance.EXTRACTED)
    n_hy = len(report.candidate_commands) - n_ex
    typer.echo(
        f"note: {n_ex} extracted + {n_hy} hypothesis command(s); "
        f"{len(report.setup_issues)} setup issue(s)",
        err=True,
    )


@app.command()
def summary(
    repo: Path = typer.Argument(..., help="Path to the repository checkout."),
) -> None:
    """Print a Markdown summary of the recovered flow to stdout."""
    _check_repo(repo)
    report = recover(repo, command=f"tb-recover summary {repo}")
    sys.stdout.write(render_markdown(report))


@app.command()
def smoke(
    repo: Path = typer.Argument(..., help="Path to the repository checkout."),
) -> None:
    """Print the recommended minimal smoke-test command (only)."""
    _check_repo(repo)
    report = recover(repo, command=f"tb-recover smoke {repo}")
    st = report.recommended_smoke_test
    if st is None:
        typer.echo("no evidence-backed smoke-test command could be recovered", err=True)
        raise typer.Exit(code=1)
    tag = "EXTRACTED" if st.provenance is Provenance.EXTRACTED else "HYPOTHESIS"
    if st.evidence:
        e = st.evidence[0]
        typer.echo(f"# {tag} from {e.file}:{e.line}", err=True)
    sys.stdout.write(st.command + "\n")


@app.command()
def schema(
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON Schema here (else stdout)."
    ),
) -> None:
    """Print the JSON Schema for the RecoveryReport contract."""
    js = json.dumps(RecoveryReport.model_json_schema(), indent=2, sort_keys=True) + "\n"
    if out:
        out.write_text(js, encoding="utf-8")
        typer.echo(f"wrote schema: {out}", err=True)
    else:
        sys.stdout.write(js)


def run() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
