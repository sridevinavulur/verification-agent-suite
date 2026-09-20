# Architecture

## Pipeline

```
             ┌──────────────────┐
 RTL (.sv) ─▶│  rtl_parser.py   │─┐
             │  subset parser   │ │  ParsedModule (dataclasses)
             └──────────────────┘ │
                                   ├─▶┌──────────────┐   ResetIntentManifest
 RTL Intent  ┌──────────────────┐ │  │ analyzer.py  │──▶ (Pydantic v2 models)
 Manifest ──▶│manifest_adapter  │─┘  │ deterministic│        │
 (.json)     │  (INTEROP)       │    │  + heuristic │        │
             └──────────────────┘    └──────────────┘        │
                                            │                 │
                        ┌───────────────────┼─────────────────┼─────────────┐
                        ▼                    ▼                 ▼             ▼
                  generate_candidate    graph.py (DOT)    report.py      cli.py (Typer)
                  _sva (sva-intent                        (Markdown)
                  style, candidate)
```

`mutations.py` is a standalone defect injector (reset polarity flip, reset-value
change, reset removal) used to sanity-check that the generated checks and
recommendations would surface classic reset bugs.

## Components & contracts

| Module | Responsibility | Input | Output |
|---|---|---|---|
| `rtl_parser.py` | Constrained Verilog/SV subset parse; **structural only** | source text | `ParsedModule` (ports, always blocks, nonblocking assigns, reset guards) |
| `manifest_adapter.py` | Map canonical RTL Intent Manifest onto `ParsedModule` | manifest dict | `list[ParsedModule]` |
| `analyzer.py` | Reset topology, polarity **voting**, domains, RDC, risks, SVA | `ParsedModule` | `ResetIntentManifest` |
| `models.py` | Typed Pydantic v2 contracts (validate, not annotate) | — | schema |
| `graph.py` | Deterministic Graphviz DOT | `ResetGraph` | DOT string |
| `report.py` | Human-readable Markdown | `ResetIntentManifest` | Markdown |
| `mutations.py` | Reset-defect source injectors | source text | `list[Mutant]` |
| `cli.py` | Typer CLI (`analyze/graph/report/sva/mutate/schema`) | files | files/stdout |
| `agent.py` | Orchestration + provenance (input hashes) | files | `ResetIntentManifest` |

## Deterministic vs heuristic (authority boundary)

**Deterministic / structural** (reproducible, evidence-backed):

- reset candidate presence (edge sensitivity or guard position)
- sync vs async classification (edge-list vs body-guard)
- reset values (constant RHS in the reset branch)
- polarity **votes** from edge, guard form, and name convention

**Heuristic** (labelled `heuristic=True`, requires human review):

- reset-**domain** grouping by shared reset signal
- reset-**domain crossings** (register in domain A feeding domain B)
- reset-candidate confidence scores

**Never inferred silently:**

- **Polarity.** Conflicting or absent evidence → `unknown` + an `Ambiguity`.
  Candidate SVA for an unknown-polarity reset emits a `/* REVIEW */` placeholder
  rather than a guessed active expression.

## Polarity voting

`_vote_polarity` aggregates `PolarityEvidence` records:

- `edge`: `negedge` → active-low, `posedge` → active-high (async resets)
- `guard_expr`: `!rst` / `~rst` / `== 0` → active-low; bare / `== 1` → active-high
- `name_suffix`: `_n` → active-low (weak)

If all non-unknown votes agree → that polarity. If they conflict → `unknown`.
If there are none → `unknown`. Every vote is preserved on the candidate for
review, so the decision is auditable.

## Candidate SVA style

Emitted per reset target as an `assert property` with `status = candidate`
(sva-intent-engine convention). No property is ever called verified. The clock is
selected structurally from the edge-sensitive block; the reset-active expression
is derived from the voted polarity or left as an explicit review placeholder.

## Determinism

- All collections are sorted before emission (candidates, targets, domains,
  crossings) so JSON/DOT/Markdown are stable and diffable.
- Provenance records input SHA-256 hashes and the invoking command.
