# Architecture

## Overview

`security-property-agent` is a deterministic, layered pipeline. The **LLM layer
does not exist** in v0.1: every stage is a pure function of its inputs. This is
intentional — the BUILD_STANDARD requires that deterministic tools validate
syntax/symbols/constraints, and there is nothing here that needs a language
model to be correct.

```
                 +-----------------------------+
  requirement    |  decompose.py               |  verbatim clauses +
  set (YAML/JSON)| (split + classify)          |  classification
                 +--------------+--------------+
                                v
  RTL Intent     +-----------------------------+
  Manifest ----->|  manifest.py + grounding.py |  evidence-based symbol refs
  (JSON)         | (Manifest is only evidence) |
                 +--------------+--------------+
                                v
                 +-----------------------------+
                 |  generate.py + renderer.py  |  candidate SVA (whitelisted)
                 |  (per-category templates)   |  + mutation examples
                 +--------------+--------------+
                                v
                 +-----------------------------+
                 |  validate.py                |  static/structural checks
                 +--------------+--------------+
                                v
                 +-----------------------------+
                 |  pipeline.py -> models.py   |  SecurityReviewReport (JSON)
                 +-----------------------------+
```

## Components and typed contracts

All contracts are Pydantic v2 models in `models.py` (validate, not annotate;
`extra="forbid"`).

| Module | Responsibility | Key input -> output |
|---|---|---|
| `models.py` | Typed data contracts + machine-checked invariants | — |
| `manifest.py` | Load + flatten canonical Manifest into a queryable view | Manifest JSON -> `ManifestView` |
| `decompose.py` | Verbatim clause split + 3-way classification | `SecurityRequirement` -> `DecompositionResult` |
| `grounding.py` | Evidence-based term→symbol mapping | `SecurityRequirement` + `ManifestView` -> `GroundingResult` |
| `renderer.py` | Whitelisted SVA rendering (`safe_expr`) | expr strings -> SVA text (or `RenderError`) |
| `generate.py` | Per-category candidate + mutation synthesis | clauses + grounding -> `CandidateProperty[]`, `MutationExample[]` |
| `validate.py` | Static/structural checks | `CandidateProperty` -> `ValidationCheck[]` |
| `pipeline.py` | Orchestration + report assembly | `RequirementSet` + `ManifestView` -> `SecurityReviewReport` |
| `cli.py` | Typer CLI | files -> report / stdout |
| `schema_export.py` | Export JSON Schema for public contracts | — |

## Authority boundaries (who is allowed to decide what)

* **The requirement author** is authoritative for requirement text and any
  declared trust boundary. The tool never rewrites the text (enforced by the
  `DecompositionResult._clauses_are_verbatim` validator) and never fabricates a
  boundary.
* **The Manifest** is the only authority for RTL symbols. If a symbol is not in
  the Manifest, grounding leaves it unresolved. The tool cannot invent a signal.
* **The tool** is authoritative only for producing *candidate* artifacts and
  *static* checks. It has no authority to declare anything proven, and the
  `status` field / non-claims block encode that.
* **The human reviewer** is the sign-off authority. The `checklist` in every
  report is the gate; nothing downstream should treat a candidate as verified
  until a formal/simulation tool produces evidence.

## Determinism

For a fixed `(requirement set, manifest, git_sha, run_id)` the report bytes are
identical (`test_report_is_json_serializable_and_deterministic`). Ordering is
insertion-ordered; no sets leak into serialized output.

## Safety separation (per BUILD_STANDARD)

The "propose" and "validate" layers are separate modules: `generate.py`
proposes candidate mappings/properties; `validate.py` and `renderer.safe_expr`
perform the deterministic checks. A candidate is never labelled correct because
it rendered — `status` is always `candidate_rendered_offline`.
