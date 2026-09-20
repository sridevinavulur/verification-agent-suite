# Constraint Hygiene Agent

Static, deterministic hygiene review of SystemVerilog Assertions (SVA)
**assumptions / assertions / covers** against an **RTL Intent Manifest** and
formal configuration. It flags constraint-set problems that silently produce
vacuous or overconstrained formal proofs.

Spec: section 6.10 of the Verification Agent prompt pack. Built to the shared
`BUILD_STANDARD.md`.

## What it does (real, working)

Given an SVA file (and, optionally, an RTL Intent Manifest), it deterministically
produces:

- **Assumption inventory** — every parsed `assume`, with signals and expression.
- **Signal ownership classification** — each referenced signal bucketed as
  `environment_input`, `dut_output`, `internal_state`, or `unknown`, grounded in
  the **manifest port directions** of the top module.
- **Contradiction candidates** — e.g. `assume x` vs `assume !x`, or
  `assume mode==1` vs `assume mode==2` (constant conflict).
- **Unused assumption candidates** — assumptions whose signals no assertion or
  cover references.
- **Output / internal-state constraint warnings** — assumptions illegally
  constraining a **DUT output** (overconstraint) or **internal state**
  (white-box overconstraint), or an **unknown** signal.
- **Property dependency map** — for each assert/cover, which signals it depends
  on and which assumptions constrain those signals.
- **Vacuity / reachability recommendations** — e.g. assertions with no paired
  cover; global vacuity risk when contradictions exist.
- **Human-review queue** — prioritized (P1–P3) work list; the human-approval
  gate is concrete.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate   # python3.13 works too
pip install -e ".[dev]"
```

## Quickstart

```bash
# Clean corpus (passes hygiene):
constraint-hygiene review examples/good/good_constraints.sva \
    --manifest examples/dut_manifest.json

# Bad corpus (every anti-pattern flagged):
constraint-hygiene review examples/bad/bad_constraints.sva \
    --manifest examples/dut_manifest.json

# JSON output + CI gate (non-zero exit on any error-severity finding):
constraint-hygiene review examples/bad/bad_constraints.sva \
    -m examples/dut_manifest.json -f json --fail-on error

# Export the report JSON Schema:
constraint-hygiene schema
```

Without `--manifest`, ownership degrades to `unknown` for every signal (and the
tool says so) rather than guessing.

## Scope (v0.1) and non-claims

This is a **static structural** tool. It reads a constrained subset of SVA
directive forms (concurrent `assume/assert/cover property (...)`, named
`property ... endproperty` blocks, and immediate `assume(...)`), extracts
top-level conjunct facts, and applies deterministic hygiene checks.

**Non-claims (read these):**

- It **never** concludes a proof is valid, sound, consistent, or non-vacuous.
  An empty finding list means "no static suspicion found", nothing more.
- All findings are labelled **static suspicion** — never formal evidence. Two
  assumptions the tool calls contradictory could apply under different
  clock/reset regimes; a "contradiction candidate" is a prompt for a formal
  vacuity check, not a verdict.
- It **never modifies** assumptions, RTL, proof scope, or signoff. Every
  actionable finding is routed to the **human-review queue**; changing an
  assumption requires human approval.
- Unused-assumption findings are candidates only: a signal may still matter
  through RTL fan-in the SVA text does not show.

### Not yet (roadmap / stubbed)

- Full SVA temporal-operator semantics (sequences, `##`, `throughout`, etc.) —
  currently only structural signal/fact extraction.
- Parsing of vendor formal-config files (a future input); today the "formal
  configuration" is represented by the manifest + CLI options.
- Consuming actual formal coverage/reachability result files to upgrade
  recommendations into evidence-backed findings.

## Corpus & golden reports

- `examples/good/` — patterns that pass hygiene.
- `examples/bad/` — one file exercising every anti-pattern.
- `examples/expected/` — golden JSON + Markdown reports, checked in tests.

See `ARCHITECTURE.md`, `THREAT_MODEL.md`, and `EVIDENCE.md` for the full
contract, risk analysis, and claim-to-test traceability.

## License

MIT (placeholder). Public, non-proprietary example content only.
