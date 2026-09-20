# Architecture

## Overview

```
 equivalence log (EQLOG/1) ─┐
 ref/rev manifests ─────────┼─► parser.py ──► typed inputs ──► triage.py ──► TriageReport
 source map ────────────────┘   (validate)   (EquivalenceLog,   (engine)      │
                                              DesignManifest,                  ├─► report.py  (Markdown)
                                              SourceMap)                       ├─► model_dump_json (JSON)
                                                                              └─► llm.py (advisory narrative)
```

Two layers are kept strictly separate (per BUILD_STANDARD):

- **Deterministic authority** — `parser.py`, `triage.py`, `report.py`,
  `provenance.py`. These parse, validate, group, compare, classify, rank, and
  render. They are the sole source of every verdict-adjacent statement.
- **LLM (advisory only)** — `llm.py` is an offline, templated *narrator*. It
  makes no network calls and produces no evidence; it only restates what the
  deterministic layer already computed, with explicit "hypothesis, not a proof"
  language.

## Components

| Module | Responsibility |
| --- | --- |
| `models.py` | All Pydantic v2 contracts (inputs + outputs). `extra="forbid"` so malformed input fails loudly. |
| `parser.py` | `EQLOG/1` log parser (mock tool adapter) + manifest normalizer (canonical RTL Intent Manifest or compact local form). |
| `triage.py` | `TriageEngine`: signature grouping, cone union, reset comparison, cause heuristics, location ranking, debug packet. Deterministic. |
| `report.py` | Pure Markdown renderer of a `TriageReport`. |
| `provenance.py` | Input SHA-256 hashing, git SHA, tool version → `Provenance`. |
| `llm.py` | Offline mock-LLM narrator (advisory). |
| `cli.py` | Typer CLI: `triage`, `parse`, `demo`, `schema`. |

## Typed input contracts

- **`EquivalenceLog`** — `tool`, `tool_version`, `status` (`EquivalenceStatus`),
  `reference_design`, `revised_design`, compare-point counts, `mismatches`
  (`MismatchPoint[]`), `config_deltas` (`ConfigDelta[]`), `messages`.
- **`MismatchPoint`** — `name`, `kind` (`MismatchKind`), ref/rev signal + width,
  `fanin_signals`, optional `Counterexample` (`CexVector[]`).
- **`DesignManifest`** — `top`, `signal_widths`, `reset` (`ResetInfo`),
  `state_encoding`. Populated either directly or from the canonical manifest.
- **`SourceMap`** — `SourceMapEntry[]` mapping (signal, design) → `SourceLocation`.

## Typed output contract

- **`TriageReport`** — `provenance`, `reported_status` (echoed) + `status_evidence`,
  compare-point counts, `config_deltas`, `reset_comparison` (`ResetComparison`),
  `groups` (`MismatchGroup[]`), `debug_packet` (`DebugPacket`), `warnings`.
- **`MismatchGroup`** — `signature`, `members`, `kind`, `cone_signals`,
  widths, `likely_causes` (`LikelyCause[]`), `ranked_locations` (`RankedLocation[]`).
- **`LikelyCause`** — `category` (`CauseCategory`), `confidence` ∈ [0,1],
  `rationale`, `is_heuristic=True`, `evidence_refs`.

## Deterministic algorithms

- **Signature grouping** (`TriageEngine.signature`): a key of
  `kind | width-relation | base-name | sorted CEX-diff signals | sorted cone`.
  Bit indices (`out[7]`) are stripped so slices of one bug collapse. Groups are
  sorted largest-first, then by signature.
- **Cone identification**: union of tool-reported `fanin_signals` and CEX
  differing signals, in first-seen order.
- **Reset comparison**: polarity/sync/init-value diffs between the two manifests'
  `ResetInfo` (only flags a difference when both sides are known).
- **Cause heuristics** (`classify_causes`): ordered rules for width, polarity
  (CEX inversion or reset-polarity + reset-in-cone), gating (enable-like signal
  in cone), reset/init, state-encoding (manifest encoding diff), config/constraint
  (any real `config_delta`), and an optimization fallback for unexplained
  state/cutpoint mismatches. Each emits a bounded confidence + rationale +
  evidence refs. Sorted by confidence.
- **Location ranking** (`rank_locations`): score = 3.0 (direct compare point) +
  1.0 (in cone) + 0.5 (implicated by a cause), resolved against the source map.
  Sorted by score, then design, then signal.

## Authority boundaries

- The engine **never** sets or overrides `reported_status`; it copies it from the
  parsed log and records where it came from (`status_evidence`).
- Non-conclusive statuses add a warning and do **not** produce a non-equivalence
  claim.
- `config_deltas` are always carried through to the report and, when any differ,
  raise a warning and a `config_constraint` cause and reorder debug steps to
  reconcile config first.
- No component writes to or mutates any design/manifest input.
