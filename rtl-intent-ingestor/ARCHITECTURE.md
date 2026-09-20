# Architecture

RTL Intent Ingestor is a deterministic pipeline that turns constrained Verilog
source into a typed, normalized manifest. There is **no LLM** in v0.1; every
value is produced by parsing or an explicitly-labelled heuristic.

## Dataflow

```
 .sv files
    |
    v
[ lexer ]  ── tokenize() ─────────────► tokens (with line/col)
    |
    v
[ parser adapter ]  (builtin)  ───────► per-file: Modules + UnresolvedConstructs
    |                                    (ports, params, nets, procedures,
    |                                     continuous assigns, instances)
    v
[ heuristics ]  detect_clock_reset() ─► clock/reset candidates + confidence
    |
    v
[ manifest builder ]  ────────────────► hierarchy edges, top inference,
    |                                    provenance (hashes, command, version)
    v
[ serialize ] / [ report ]  ──────────► stable JSON manifest / Markdown summary
```

## Components and contracts

| Component | File | Input | Output |
| --- | --- | --- | --- |
| Lexer | `lexer.py` | source text | `list[Token]` |
| Adapter interface | `adapters/base.py` | text | `ParseResult` (modules + unresolved) |
| Built-in parser | `adapters/builtin.py` | text | `ParseResult` |
| Heuristics | `heuristics.py` | `Module` | mutates clock/reset candidates |
| Manifest builder | `manifest.py` | `{file: text}` | `Manifest` |
| Serializer | `serialize.py` | `Manifest` | stable JSON string |
| Reporter | `report.py` | `Manifest` | Markdown string |
| CLI | `cli.py` | argv | files / stdout |

All data contracts are Pydantic v2 models in `models.py` with
`extra="forbid"`, so the manifest is validated, not merely annotated. The
top-level contract is `Manifest`; its JSON Schema is exported to
`schemas/manifest.schema.json` and via `rtl-intent schema`.

## Parser-adapter interface

`ParserAdapter` (abstract) defines `parse_text(text, *, filename) -> ParseResult`
and `info() -> ParserInfo`. Adapters are registered in `adapters/__init__.py`.
This is the seam where a Slang / tree-sitter / Surelog-UHDM frontend can be
added later. v0.1 registers exactly one: `builtin`.

An adapter is responsible **only** for per-file syntactic extraction. Cross-module
concerns (hierarchy edges, top inference, clock/reset heuristics, provenance)
are assembled by `manifest.py` so every adapter yields a consistent manifest.

## Authority boundaries

- The tool performs **deterministic extraction and labelled heuristics only**.
- It does **not** modify RTL, infer semantics beyond the documented heuristics,
  or make formal claims about clocking, reset, or state.
- "Register", "clock candidate", and "reset candidate" are **structural /
  heuristic** notions defined in `models.py` docstrings, not formal conclusions.
- Every construct outside the supported subset is emitted in `Manifest.unresolved`
  rather than dropped, so a human/downstream tool can see the coverage gap.

## Determinism

Output is byte-stable given stable input ordering: dicts preserve insertion
order, candidate lists are sorted by `(-confidence, name)`, and JSON is dumped
with `sort_keys=True`. This is what makes the golden tests meaningful.
