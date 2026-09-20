# security-property-agent

Transform **structured security requirements** into **reviewable candidate
verification artifacts** — candidate SystemVerilog Assertions (SVA) plus
mutation/fault examples — for a fixed set of hardware security check families.

This is a deterministic engineering tool. It does **not** prove anything. Every
artifact it emits is *candidate* material for human review and for a downstream
formal/simulation tool to actually evaluate.

## Scope (v0.1)

Supported security check families (spec 6.13):

| Category | Candidate property shape (example) |
|---|---|
| `access_control` | `action |-> grant` (a committed action implies it was granted) |
| `privilege_gating` | `secure_op |-> priv_mode` |
| `debug_lockout` | `dbg_locked |-> !dbg_enable` |
| `fault_response` | `fault_detected |-> ##[1:3] safe_halt` (bounded response) |
| `error_containment` | `ecc_error |-> !data_valid_out` |
| `lockstep_mismatch` | `core_a_result == core_b_result` |
| `information_flow_adjacent` | `!(sink == secret)` (structural adjacency only — **not** non-interference) |

Pipeline (all deterministic, no LLM, no network):

```
requirement set + RTL Intent Manifest
  -> decompose   (atomic clauses; requirement text preserved EXACTLY)
  -> ground      (map terms to RTL symbols using ONLY Manifest evidence)
  -> generate    (candidate SVA from a whitelisted set of property forms)
  -> mutate      (deliberately-broken should-fail witnesses)
  -> validate    (static/structural checks only)
  -> SecurityReviewReport (JSON: artifacts, checklist, non-claims, provenance)
```

## Interop

* **Input RTL evidence**: the canonical *RTL Intent Manifest* produced by the
  sibling `rtl-intent-ingestor`
  (`rtl-intent-ingestor/schemas/manifest.schema.json`). The bundled example
  manifest was produced by that tool from `examples/rtl/secure_soc.sv`.
* **Output SVA style**: candidate properties follow the `sva-intent-engine`
  convention — a rendered property carries a `status` of
  `candidate_rendered_offline`, **never** "verified".

## Install

```bash
python3 -m venv .venv           # python 3.11+ (3.13 tested)
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
security-property-agent run \
    examples/requirements/secure_soc.requirements.yaml \
    --manifest examples/rtl/secure_soc.manifest.json \
    --out report.json
```

Example summary (stderr):

```
[run-0001] requirements=8 candidates=7 mutations=10 with_errors=0
REMINDER: all output is CANDIDATE material for human review; no security property was proven.
```

Inspect just the decomposition + classification:

```bash
security-property-agent decompose examples/requirements/secure_soc.requirements.yaml
```

Export the public JSON contracts:

```bash
security-property-agent export-schemas --out-dir schemas
```

## Input format

A requirement set is YAML or JSON. Each requirement's `text` is preserved
**verbatim** (sha256-hashed for audit). `signals` are author hints that are
still checked against the Manifest before being trusted.

```yaml
requirements:
  - requirement_id: SEC-DBG-001
    category: debug_lockout
    text: "When dbg_locked is asserted, dbg_enable must never be high."
    signals: [dbg_locked, dbg_enable]
```

## What actually works

- Verbatim requirement decomposition with a **machine-checked** guarantee that
  every clause is a substring of the original (`DecompositionResult`
  validator).
- Three-way clause classification: **safety property** vs **environment
  assumption** vs **security test objective**, kept distinct as the spec
  requires. Environment assumptions are **never** emitted as `assert`.
- Evidence-based grounding against the canonical Manifest; unknown signals stay
  unresolved (never invented).
- Candidate SVA rendering through a token whitelist (`renderer.safe_expr`) that
  rejects `;`, `$`, macros, comments, division, etc.
- Mutation/fault synthesis producing should-fail witnesses (negate consequent,
  drop guard, weaken bound, break lockstep, flip never→always).
- Deterministic, JSON-serializable `SecurityReviewReport` with provenance,
  a human sign-off checklist, and an explicit non-claims block.
- Typer CLI (`run`, `decompose`, `export-schemas`, `version`).

## Non-claims (read this)

This tool:

1. **Does NOT prove** any security property. Output is candidate-only.
2. Treats rendering/compiling as **not** verification. No formal or simulation
   tool is run.
3. **Does NOT infer** threat models or trust boundaries. Boundary-dependent
   properties require an explicit human-declared boundary.
4. Marks heuristic (alias) symbol matches as **low confidence** for human
   confirmation.
5. Emits mutations as **should-fail witnesses**, not proof the original holds.
6. Provides only **structural** information-flow-adjacent checks — these are
   **not** non-interference proofs.

See `LIMITATIONS.md` and `THREAT_MODEL.md` for the full list, including the
known active-low reset (`disable iff`) polarity caveat.

## License

MIT. See `LICENSE`. Public toy content only; no proprietary material.
