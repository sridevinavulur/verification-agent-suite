# Architecture

## Data flow

```
register map (json/yaml/csv/md) ──▶ parsers.load_register_map ──▶ RegisterMap
RTL symbols (json / intent manifest) ─▶ rtl_symbols.load_rtl_symbols ─▶ RtlSymbolTable
                                            │
        RegisterMap ─────────────┬──────────┘
                                 ▼
                        grounding.ground ──▶ GroundingReport
                                 │
                     checks.run_all_checks ──▶ [Discrepancy]  (deterministic, authoritative)
                                 │
                 llm_adapter.annotate_discrepancies (explanation prose only)
                                 │
              generators (SVA / tests / coverage / checklist)
                                 ▼
                        pipeline.build_package ──▶ VerificationPackage
                                 ▼
                 renderer.* + cli package  ──▶ files on disk
```

## Components and typed contracts

| module | responsibility | key input -> output |
|---|---|---|
| `models.py` | Pydantic v2 contracts + closed enums (`AccessType`, `Privilege`, `Severity`) | validation authority |
| `parsers.py` | JSON/YAML/CSV/Markdown front ends | `str/path` -> `RegisterMap` |
| `rtl_symbols.py` | simple export + RTL Intent Manifest ingest | `path` -> `RtlSymbolTable` |
| `grounding.py` | lexical name mapping | `RegisterMap, RtlSymbolTable` -> `GroundingReport` |
| `checks.py` | deterministic defect checks | `RegisterMap[, RTL, grounding]` -> `[Discrepancy]` |
| `generators.py` | SVA / directed tests / coverage / checklist | `RegisterMap` -> candidates |
| `llm_adapter.py` | deterministic mock explainer | `Discrepancy` -> `explanation` prose |
| `pipeline.py` | orchestration + provenance | `paths` -> `VerificationPackage` |
| `renderer.py` | human-facing text/markdown | `VerificationPackage` -> `str` |
| `cli.py` | Typer CLI | argv -> stdout/files/exit code |
| `schema_export.py` | JSON Schema export | models -> `schemas/*.json` |

## Authority boundaries

1. **Parsers own normalization.** Access tokens are mapped onto the closed
   `AccessType` enum via `ACCESS_ALIASES`; an unknown token raises `ParseError`.
2. **Checks own defect classification.** Every finding is a `Discrepancy` with a
   stable `code` and `severity`. Checks never emit a PASS; a clean run is an
   empty list. `ERROR` findings drive CLI exit code 1.
3. **Grounding owns signal mapping.** Only exact or normalized-name matches;
   never inferred from value similarity; unmatched names surfaced.
4. **LLM owns nothing structural.** `annotate_discrepancies` mutates only the
   `explanation` field. Enforced by unit tests.

## Result vocabulary

Candidate SVA carries `status="candidate"` and is never upgraded by any
deterministic code path. The tool performs no proof; there is no PASS/PROVEN
result produced for assertions.

## Determinism / reproducibility

- No network or real LLM calls anywhere (mock adapter only).
- Discrepancies are sorted (severity, code, register, field, message) for stable
  output; golden-file tests pin the rendered artifacts.
- `Provenance` records tool version, command, input files, and input SHA-256.
