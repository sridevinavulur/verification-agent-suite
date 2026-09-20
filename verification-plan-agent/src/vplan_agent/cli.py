"""Typer CLI for the Verification Plan Agent: ``vplan``.

Commands:
* ``plan``     - spec + interface (+ manifest, + existing testplan) -> plan JSON/MD
* ``report``   - render an existing plan JSON to Markdown
* ``approve``  - apply a human decisions file to a plan JSON
* ``schema``   - print the JSON Schema for the VerificationPlan contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import __version__
from .approval import apply_decisions, load_decisions
from .engine import build_plan
from .ingest import (
    load_existing_testplan,
    load_interface,
    load_manifest_view,
    load_spec,
    sha256_files,
)
from .llm import get_adapter
from .models import Provenance, VerificationPlan
from .report import render_markdown
from .serialize import plan_from_json, plan_to_json

app = typer.Typer(
    add_completion=False,
    help="Verification Plan Agent - reviewable verification-plan drafts with "
    "traceability from a structured spec + interface + RTL Intent Manifest "
    "(v0.1, mock LLM only).",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"vplan {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Verification Plan Agent."""


@app.command()
def plan(
    spec: Path = typer.Option(..., "--spec", "-s", help="Structured spec JSON."),
    interface: Path = typer.Option(
        ..., "--interface", "-i", help="Interface glossary JSON."
    ),
    manifest: Path = typer.Option(
        None, "--manifest", "-m",
        help="RTL Intent Manifest JSON (canonical schema).",
    ),
    existing: Path = typer.Option(
        None, "--existing", "-e", help="Existing testplan items JSON."
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write plan JSON here (else stdout)."
    ),
    markdown: Path = typer.Option(
        None, "--markdown", help="Also write a Markdown report here."
    ),
    llm: str = typer.Option("mock", "--llm", help="LLM adapter (only 'mock')."),
) -> None:
    """Generate a verification-plan draft."""
    spec_doc = load_spec(spec)
    glossary = load_interface(interface)
    manifest_view = load_manifest_view(manifest)
    existing_tp = load_existing_testplan(existing)
    adapter = get_adapter(llm)

    input_files = [spec, interface]
    if manifest is not None:
        input_files.append(manifest)
    if existing is not None:
        input_files.append(existing)

    prov = Provenance(
        command=" ".join(sys.argv[1:]),
        llm_adapter=llm,
        input_files=[f.name for f in input_files],
        input_sha256=sha256_files(input_files),
    )

    result = build_plan(
        spec_doc, glossary, manifest_view, existing_tp, prov, adapter
    )
    _emit(result, out, markdown)


@app.command()
def report(
    plan_json: Path = typer.Argument(..., help="Plan JSON produced by 'plan'."),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write Markdown here (else stdout)."
    ),
) -> None:
    """Render an existing plan JSON to a Markdown report."""
    result = plan_from_json(plan_json.read_text(encoding="utf-8"))
    md = render_markdown(result)
    if out is not None:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(md)


@app.command()
def approve(
    plan_json: Path = typer.Argument(..., help="Plan JSON to update."),
    decisions: Path = typer.Option(
        ..., "--decisions", "-d", help="Human decisions JSON (list)."
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Write updated plan JSON here (else stdout)."
    ),
    markdown: Path = typer.Option(
        None, "--markdown", help="Also write a Markdown report here."
    ),
) -> None:
    """Apply a human approval-decisions file to a plan (approval workflow)."""
    result = plan_from_json(plan_json.read_text(encoding="utf-8"))
    decs = load_decisions(decisions)
    updated, applied, unmatched = apply_decisions(result, decs)
    typer.echo(
        f"Applied {len(applied)} decision(s); {len(unmatched)} unmatched.",
        err=True,
    )
    if unmatched:
        typer.echo(f"Unmatched ids: {', '.join(unmatched)}", err=True)
    _emit(updated, out, markdown)


@app.command()
def schema(
    out: Path = typer.Option(
        None, "--out", "-o", help="Write JSON Schema here (else stdout)."
    ),
) -> None:
    """Print the JSON Schema for the VerificationPlan contract."""
    text = json.dumps(VerificationPlan.model_json_schema(), indent=2, sort_keys=True)
    if out is not None:
        out.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(text)


def _emit(result: VerificationPlan, out: Path | None, markdown: Path | None) -> None:
    text = plan_to_json(result)
    if out is not None:
        out.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Wrote {out}", err=True)
    else:
        typer.echo(text)
    if markdown is not None:
        markdown.write_text(render_markdown(result), encoding="utf-8")
        typer.echo(f"Wrote {markdown}", err=True)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
