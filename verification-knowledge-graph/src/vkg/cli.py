"""Typer CLI for the Verification Knowledge Graph.

Commands
--------
* ``vkg import <kind> <file> [--db PATH]`` -- import one artifact.
* ``vkg build-demo [--db PATH]``           -- import all bundled examples.
* ``vkg query <name> [arg] [--db PATH]``   -- run a working query.
* ``vkg export {json,dot} [--db PATH]``    -- export the graph.
* ``vkg stats [--db PATH]``                -- print node/edge counts.

The database defaults to an in-memory graph only for ``build-demo`` chained
with export/query in a single process; for persistence pass ``--db kg.db``.
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import typer

from .export import to_dot, to_json
from .graph import Graph
from .importers import IMPORTERS
from .models import QueryResult
from .queries import PARAMETRIC_QUERIES, QUERIES

app = typer.Typer(
    add_completion=False,
    help="Verification Knowledge Graph over verification artifacts.",
)

# Paths to bundled example artifacts (installed relative to package root).
_EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"

_DEMO_ORDER = [
    ("rtl", "rtl_intent_manifest.json"),
    ("sva", "sva_intent.json"),
    ("testplan", "test_plan.json"),
    ("coverage", "coverage_summary.json"),
    ("runledger", "run_ledger.json"),
    ("evidence", "evidence_claims.json"),
]


def _open(db: str) -> Graph:
    return Graph(db)


@app.command("import")
def import_cmd(
    kind: str = typer.Argument(..., help=f"One of: {', '.join(IMPORTERS)}"),
    path: Path = typer.Argument(..., exists=True, help="Artifact JSON file"),
    db: str = typer.Option("kg.db", help="SQLite database path"),
) -> None:
    """Import a single verification artifact into the graph."""
    if kind not in IMPORTERS:
        typer.echo(f"Unknown importer '{kind}'. Choose from: {', '.join(IMPORTERS)}")
        raise typer.Exit(code=2)
    g = _open(db)
    n = IMPORTERS[kind](g, path)
    typer.echo(f"Imported {kind} from {path}: {n} nodes touched. DB={db}")
    typer.echo(_json.dumps(g.stats(), indent=2))
    g.close()


@app.command("build-demo")
def build_demo(
    db: str = typer.Option("kg.db", help="SQLite database path"),
) -> None:
    """Import every bundled example artifact into one graph."""
    g = _open(db)
    total = 0
    for kind, fname in _DEMO_ORDER:
        fpath = _EXAMPLES / fname
        if not fpath.exists():
            typer.echo(f"WARNING: missing example {fpath}", err=True)
            continue
        total += IMPORTERS[kind](g, fpath)
    typer.echo(f"Built demo graph in {db}: {total} nodes touched.")
    typer.echo(_json.dumps(g.stats(), indent=2))
    g.close()


def _print_result(result: QueryResult, as_json: bool) -> None:
    if as_json:
        typer.echo(result.model_dump_json(indent=2))
        return
    typer.echo(f"# {result.description}")
    typer.echo(f"# matches: {result.count}")
    typer.echo(" | ".join(result.columns))
    typer.echo("-" * 60)
    for row in result.rows:
        typer.echo(" | ".join(row.fields.get(c, "") for c in result.columns))


@app.command("query")
def query_cmd(
    name: str = typer.Argument(..., help=f"One of: {', '.join(QUERIES)}"),
    arg: str = typer.Argument(None, help="Argument for parametric queries"),
    db: str = typer.Option("kg.db", help="SQLite database path"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """Run a working query against the graph."""
    if name not in QUERIES:
        typer.echo(f"Unknown query '{name}'. Choose from: {', '.join(QUERIES)}")
        raise typer.Exit(code=2)
    g = _open(db)
    fn = QUERIES[name]
    if name in PARAMETRIC_QUERIES:
        if not arg:
            typer.echo(f"Query '{name}' requires an argument.")
            raise typer.Exit(code=2)
        result = fn(g, arg)  # type: ignore[call-arg]
    else:
        result = fn(g)  # type: ignore[call-arg]
    _print_result(result, as_json)
    g.close()


@app.command("export")
def export_cmd(
    fmt: str = typer.Argument(..., help="json or dot"),
    db: str = typer.Option("kg.db", help="SQLite database path"),
    out: Path = typer.Option(None, "--out", help="Write to file instead of stdout"),
) -> None:
    """Export the whole graph as JSON or Graphviz DOT."""
    g = _open(db)
    if fmt == "json":
        text = to_json(g)
    elif fmt == "dot":
        text = to_dot(g)
    else:
        typer.echo("fmt must be 'json' or 'dot'")
        raise typer.Exit(code=2)
    if out:
        out.write_text(text)
        typer.echo(f"Wrote {fmt} export to {out}")
    else:
        sys.stdout.write(text)
    g.close()


@app.command("stats")
def stats_cmd(db: str = typer.Option("kg.db", help="SQLite database path")) -> None:
    """Print node/edge counts by type."""
    g = _open(db)
    typer.echo(_json.dumps(g.stats(), indent=2))
    g.close()


def main() -> None:  # pragma: no cover - thin entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
