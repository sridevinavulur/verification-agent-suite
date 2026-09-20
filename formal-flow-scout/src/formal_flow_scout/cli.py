"""Typer CLI for FormalFlow-Scout.

Commands:
* ``analyze``    - run COI/partition analysis, emit JSON report + optional DOT.
* ``build-graph``- build and dump the dependency graph JSON only.
* ``schema``     - export the JSON Schema for the report contract.
* ``demo``       - run the bundled example end to end.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import typer

from . import __version__
from .analyzer import Analyzer
from .cpp_bridge import CppCoreUnavailable, coi_via_cpp
from .graph_builder import build_from_manifest, build_from_parse
from .models import (
    CoiReport,
    DependencyGraph,
    PropertySet,
    PropertySpec,
    Provenance,
)
from .reporting import to_dot, to_text_summary
from .verilog_parser import parse_verilog

app = typer.Typer(
    add_completion=False,
    help="RTL cone-of-influence and partition analysis (heuristic partitions).",
    no_args_is_help=True,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_graph(
    rtl: Path | None, manifest: Path | None, top: str | None
) -> tuple[DependencyGraph, dict[str, str], list[str]]:
    """Return (graph, input_sha256, input_files)."""
    hashes: dict[str, str] = {}
    files: list[str] = []
    if manifest is not None:
        data = json.loads(manifest.read_text())
        hashes[str(manifest)] = _sha256(manifest)
        files.append(str(manifest))
        return build_from_manifest(data, top=top), hashes, files
    if rtl is not None:
        text = rtl.read_text()
        hashes[str(rtl)] = _sha256(rtl)
        files.append(str(rtl))
        parse = parse_verilog(text, file=str(rtl))
        graph = build_from_parse(parse, top=top)
        return graph, hashes, files
    raise typer.BadParameter("provide either --rtl or --manifest")


def _load_property(prop_file: Path, name: str | None) -> PropertySpec:
    data = json.loads(prop_file.read_text())
    pset = PropertySet.model_validate(data)
    if not pset.properties:
        raise typer.BadParameter("property file has no properties")
    if name is None:
        return pset.properties[0]
    for p in pset.properties:
        if p.name == name:
            return p
    raise typer.BadParameter(f"property {name!r} not found in {prop_file}")


@app.command()
def analyze(
    property_file: Path = typer.Argument(..., help="Property set JSON (seeds)."),
    rtl: Path = typer.Option(None, "--rtl", help="Verilog source file."),
    manifest: Path = typer.Option(None, "--manifest", help="RTL Intent Manifest JSON."),
    top: str = typer.Option(None, "--top", help="Top module name."),
    property_name: str = typer.Option(None, "--property", help="Which property."),
    out: Path = typer.Option(None, "--out", "-o", help="Write report JSON here."),
    dot: Path = typer.Option(None, "--dot", help="Write Graphviz DOT here."),
    use_cpp: bool = typer.Option(
        False, "--use-cpp", help="Use the C++ core for COI if built."
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress text summary."),
) -> None:
    """Run COI + partition analysis and emit a report (+ optional DOT)."""
    graph, hashes, files = _load_graph(rtl, manifest, top)
    prop = _load_property(property_file, property_name)
    hashes[str(property_file)] = _sha256(property_file)
    files.append(str(property_file))

    analyzer = Analyzer(graph)
    core = "python"
    if use_cpp:
        try:
            # Validate the C++ core agrees with Python on the sequential COI.
            seeds, _ = analyzer._resolve_seeds(prop)
            cpp_coi = coi_via_cpp(analyzer.pg, seeds, combinational_only=False)
            py_coi = sorted(
                analyzer.pg.backward_coi(
                    seeds, combinational_only=False, include_control=True
                )
            )
            if cpp_coi == py_coi:
                core = "cpp"
            else:
                typer.echo(
                    "WARNING: C++ core disagreed with Python; using Python.",
                    err=True,
                )
        except CppCoreUnavailable as exc:
            typer.echo(f"C++ core unavailable ({exc}); using Python.", err=True)

    provenance = Provenance(
        tool_version=__version__,
        input_files=files,
        input_sha256=hashes,
        command="formal-flow-scout analyze " + " ".join(sys.argv[1:]),
        graph_core=core,
    )
    report = analyzer.analyze(prop, provenance)

    payload = report.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=False)
    if out is not None:
        out.write_text(text + "\n")
        typer.echo(f"wrote report: {out}", err=True)
    else:
        typer.echo(text)

    if dot is not None:
        dot.write_text(to_dot(report, analyzer.pg))
        typer.echo(f"wrote dot: {dot}", err=True)

    if not quiet:
        typer.echo(to_text_summary(report), err=True)


@app.command("build-graph")
def build_graph(
    rtl: Path = typer.Option(None, "--rtl", help="Verilog source file."),
    manifest: Path = typer.Option(None, "--manifest", help="RTL Intent Manifest JSON."),
    top: str = typer.Option(None, "--top", help="Top module name."),
    out: Path = typer.Option(None, "--out", "-o", help="Write graph JSON here."),
) -> None:
    """Build the dependency graph and dump it as JSON."""
    graph, _, _ = _load_graph(rtl, manifest, top)
    text = json.dumps(graph.model_dump(mode="json"), indent=2)
    if out is not None:
        out.write_text(text + "\n")
        typer.echo(f"wrote graph: {out}", err=True)
    else:
        typer.echo(text)


@app.command()
def schema(
    out: Path = typer.Option(None, "--out", "-o", help="Write JSON Schema here."),
) -> None:
    """Export the JSON Schema for the CoiReport contract."""
    text = json.dumps(CoiReport.model_json_schema(), indent=2)
    if out is not None:
        out.write_text(text + "\n")
        typer.echo(f"wrote schema: {out}", err=True)
    else:
        typer.echo(text)


@app.command()
def demo() -> None:
    """Run the bundled counter example end to end."""
    examples = Path(__file__).resolve().parent.parent.parent / "examples"
    rtl = examples / "fifo_ctrl.v"
    prop = examples / "fifo_property.json"
    graph, hashes, files = _load_graph(rtl, None, None)
    spec = _load_property(prop, None)
    analyzer = Analyzer(graph)
    provenance = Provenance(
        tool_version=__version__,
        input_files=files,
        input_sha256=hashes,
        command="formal-flow-scout demo",
    )
    report = analyzer.analyze(spec, provenance)
    typer.echo(to_text_summary(report))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
