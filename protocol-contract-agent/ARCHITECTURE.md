# Architecture

## Dataflow

```
ContractRequest (JSON/YAML)         RTL Intent Manifest (canonical, JSON)
   role -> signal bindings              modules/ports/registers/clock+reset
        |                                        |
        +---------------+------------------------+
                        v
                 io_utils.load_*                 (Pydantic v2 validation)
                        v
                 grounding.py                     resolve role -> GroundedSymbol
                   - port direction -> ownership  (env_input/dut_output/internal)
                   - clock/reset resolution       (never infer polarity by name)
                        v
                 templates.py                     per-protocol deterministic
                   - assumptions / guarantees     property construction
                   - covers / negatives
                   - checklist / warnings
                        v
                 sva.py                           safe SVA rendering (whitelist)
                        v
                 generator.py                     assemble ProtocolContract
                        v
       report.py (markdown / sva)  |  model_dump (json)  |  schema_export.py
```

## Components and contracts

| Module | Responsibility | Key input → output |
|--------|----------------|--------------------|
| `models.py` | Pydantic v2 contracts: manifest view, request, and all output models | dict → validated models |
| `io_utils.py` | Load JSON/YAML, sha256 provenance | path → `RtlManifest` / `ContractRequest` |
| `grounding.py` | Resolve signals; classify ownership; resolve clock/reset | `MModule` + name → `GroundedSymbol` |
| `templates.py` | Deterministic, parameterized per-protocol property templates | `_Ctx` → `_Result` |
| `sva.py` | Whitelist-checked SVA fragment/property rendering | expr + clock/reset → SVA text |
| `generator.py` | Orchestrate grounding + template into a full contract | request + manifest → `ProtocolContract` |
| `mutation.py` | Property-mutation operators (quality aid) | SVA text → `[Mutant]` |
| `report.py` | Human-readable Markdown + SVA-only output | contract → str |
| `schema_export.py` | Export JSON Schema for public contracts | out dir → files |
| `cli.py` | Typer CLI (`protocols`, `generate`, `demo`, `mutate`, `export-schemas`) | argv → stdout/files |

## Typed input/output boundary

- **Input:** `RtlManifest` is a *view* over the canonical manifest with
  `extra="ignore"`; it consumes only the fields needed and never mutates the
  source file. `ContractRequest` uses `extra="forbid"` so typos in role names or
  fields fail loudly.
- **Output:** `ProtocolContract` (and its parts) use `extra="forbid"`. Every
  property references only `GroundedSymbol`s (non-empty `symbol_id`).

## Authority boundary

- The tool **proposes** contracts and candidate properties. It has **no
  authority** to declare anything verified, to modify RTL, or to change
  assumptions/scope.
- Deterministic layer only: there is **no LLM and no network** in this repo. All
  outputs are reproducible from the inputs. (Role-*binding* is where human/LLM
  judgment would enter upstream; that judgment is an input here, not a claim.)
- Every safety-relevant decision that could hide a defect (assume-on-output,
  unknown reset polarity, missing occupancy signal, missing cycle bound) is
  surfaced as a `Warning` and/or `ChecklistItem`, never silently resolved.

## Determinism

Given identical inputs, output bytes are identical: property names are derived
from `module` + fixed suffixes, symbol IDs are `module.signal`, and JSON schema
export is sorted. Golden `.sva` files under `examples/golden_contracts/` are
regression-tested in `tests/test_golden_and_cli.py`.
