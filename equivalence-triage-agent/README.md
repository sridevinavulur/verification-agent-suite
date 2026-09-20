# Equivalence Triage Agent

Deterministic, evidence-grounded triage of RTL **equivalence-checking** (LEC/SEC)
mismatch results. Given an equivalence log, mismatch points, counterexamples,
reference/revised design manifests, and a source map, it produces a
mismatch-localization report that:

- **groups duplicate mismatch signatures** (bit-slices of one bug collapse together),
- **identifies each mismatch cone** (fan-in / differing-signal union),
- **compares reset/initialization behavior** across the two designs,
- **classifies likely causes** — width, polarity, gating, state-encoding,
  optimization, reset/init, config/constraint — as **heuristics with confidence**,
- **ranks source locations** for engineer review, and
- emits a **reproducible debug packet**.

This is a **narrow-but-real** tool (per the shared build standard): the log
parser, signature grouping, reset comparison, cause heuristics, and location
ranking all actually run and correctly localize the seeded bugs in the bundled
toy designs.

## Non-claims (read this first)

- It **never** claims equivalence or non-equivalence on its own. It only
  **echoes** the equivalence tool's own status (`EQUIVALENT` / `NOT_EQUIVALENT`
  / `INCONCLUSIVE` / `TIMEOUT` / `ERROR` / `ABORTED`) and always carries the
  supporting log evidence beside it.
- All likely-cause classifications are **heuristic** (`is_heuristic: true`,
  bounded confidence, explicit rationale) — never presented as sound/formal.
- It **never modifies designs**, constraints, or the tool verdict.
- Configuration/constraint differences between the two runs are **surfaced in a
  dedicated `config_deltas` field and in warnings** — never concealed.
- `TIMEOUT` / `INCONCLUSIVE` / `ERROR` / `ABORTED` are **never** treated as a
  non-equivalence proof; the report adds an advisory warning instead.

## Install

```bash
python3.13 -m venv .venv      # 3.11+ works; 3.13 tested
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Run the bundled toy ALU (seeded width + polarity + config bugs):
eq-triage demo toy_alu

# Run the toy FSM (seeded state-encoding + gating + width bugs):
eq-triage demo toy_counter

# Full triage on your own inputs:
eq-triage triage \
    --log examples/toy_alu/equivalence.eqlog \
    --ref-manifest examples/toy_alu/ref_manifest.json \
    --rev-manifest examples/toy_alu/rev_manifest.json \
    --source-map examples/toy_alu/source_map.json \
    --out-md report.md --out-json report.json

# Just parse a log:
eq-triage parse --log examples/toy_alu/equivalence.eqlog

# Export a JSON Schema:
eq-triage schema report
```

## Inputs

| Input | Format | Purpose |
| --- | --- | --- |
| Equivalence log | `EQLOG/1` text (see `parser.py` docstring) | tool status, mismatch points, CEX vectors, config deltas |
| Reference / revised manifest | canonical RTL Intent Manifest JSON **or** compact `DesignManifest` JSON | widths, reset polarity/sync, init values, state encoding |
| Source map | `SourceMap` JSON | signal → source location for ranking |

The manifest loader **interops with the canonical RTL Intent Manifest**
(`rtl-intent-ingestor/schemas/manifest.schema.json`): if a manifest has
`modules`/`parser` keys it is normalized (port/net widths, highest-confidence
reset candidate) into the internal `DesignManifest`; otherwise the compact local
form is validated directly. See `parser.normalize_manifest`.

## The `EQLOG/1` mock adapter

`parser.parse_equivalence_log` is a **real** line-oriented parser for a small,
documented, synthetic-but-representative equivalence-report format. It is
"mocked" only in that it targets a public synthetic format rather than any
proprietary tool — the parsing/validation logic is genuine and rejects malformed
input loudly (`LogParseError`). Swapping in a real tool adapter means writing a
new parser that emits the same `EquivalenceLog` Pydantic model.

## Toy designs (intentional inequivalences)

- `examples/toy_alu/` — `ref_alu.v` vs `rev_alu.v`: **width** bug (8→4-bit
  result) + **polarity** bug (active-low async → active-high sync reset) +
  a surfaced **config** delta (`reset_polarity`).
- `examples/toy_counter/` — `ref_fsm.v` vs `rev_fsm.v`: **state-encoding** bug
  (binary → one-hot) + **gating** bug (dropped `en`) + **width** bug (2→3-bit
  state).

The triage report localizes each seeded bug to the right cause category and the
right source location. Golden outputs live in `tests/golden/`.

## Output

Markdown (human) and JSON (`TriageReport`, machine). Both are deterministic —
same input yields byte-identical output (covered by golden tests). The JSON
schema is exported under `schemas/`.

## Development

```bash
ruff check .          # lint (clean)
pytest                # tests (green)
python tests/regenerate_golden.py   # refresh golden files after intended changes
```

## Roadmap / out of scope (stubbed for later phases)

- Parsing real vendor LEC/SEC log formats (only `EQLOG/1` today).
- Deriving cones from a netlist graph rather than tool-reported fan-in.
- Automatic bit-index-range collapsing beyond the current signature scheme.
- Cross-referencing manifest assignment ASTs to pinpoint the exact operator.

## License

MIT (placeholder) — see `LICENSE`.
