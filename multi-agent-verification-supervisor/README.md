# Multi-Agent Verification Supervisor

A **state-machine workflow coordinator** for a formal-verification agent pipeline.
It orchestrates four specialist agents as *bounded tools* — not free-form
conversational handoffs:

1. **RTL Intent Ingestor** — extracts a normalized design manifest.
2. **SVA Intent Agent** — proposes candidate SystemVerilog Assertions.
3. **Formal Partition Agent** — computes COI / partition analysis.
4. **Formal Run Orchestrator** — runs the (mocked) formal experiment.

The supervisor is a **policy and workflow coordinator**. It coordinates work,
enforces safety gates, requires human approval where mandated, and assembles an
evidence packet. Each of the four agents currently has a deterministic **mock
backend** so the whole workflow is testable in CI before real integrations exist.

## What this tool will NOT do (non-claims)

- It does **not** independently declare an assertion valid.
- It does **not** declare a proof complete.
- It does **not** declare verification signoff achieved.
- A backend `PASS` is authoritative **only** for the exact recorded design,
  assumptions, property, tool version, and configuration — the supervisor never
  elevates it to signoff.
- The mock backends produce **illustrative** results, not real formal outcomes.
- Partition proposals are labeled **heuristic**, never "a proven formal reduction".

## Install

```bash
python3.11 -m venv .venv          # 3.11+ required
. .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Nominal happy path (clean req/grant property) -> DONE + evidence packet
mav-supervisor run --task-file examples/task_req_grant.json --artifact-root artifacts

# A task that changes the run budget REQUIRES human approval.
# Without --approve the supervisor BLOCKS execution and ends REJECTED:
mav-supervisor run --task-file examples/task_budget_change.json --artifact-root artifacts
# With approval it proceeds:
mav-supervisor run --task-file examples/task_budget_change.json --artifact-root artifacts --approve

# Inject a defective candidate to see a rejection gate fire (red-team from the CLI):
mav-supervisor run --sva-defect ungrounded  --artifact-root artifacts   # -> REJECTED
mav-supervisor run --sva-defect syntax      --artifact-root artifacts   # -> REJECTED
mav-supervisor run --sva-defect no_clock    --artifact-root artifacts   # -> REJECTED

# Make partitioning add unproven cut obligations -> forces the human gate:
mav-supervisor run --cut-assumptions --artifact-root artifacts          # -> REJECTED (no approval)

# Inspect the machine and the approved config catalog:
mav-supervisor show-states
mav-supervisor show-catalog

# Pretty-print a full evidence packet:
mav-supervisor demo --artifact-root artifacts
```

## Workflow state machine

```
CREATED -> RTL_INGESTION -> SVA_PROPOSAL -> PROPERTY_REVIEW
        -> PARTITION_ANALYSIS -> PLAN_EXPERIMENT
        -> [AWAITING_HUMAN_APPROVAL] -> EXECUTION
        -> EVIDENCE_ASSEMBLY -> DONE
```

- `PROPERTY_REVIEW` may **retry** back to `SVA_PROPOSAL` (bounded by
  `max_property_retries`) or **REJECT** (terminal).
- `PLAN_EXPERIMENT` routes through `AWAITING_HUMAN_APPROVAL` whenever the task
  affects assumptions / abstraction / budget / proof scope, or when partition
  cuts introduce unproven obligations.
- Terminal states: `DONE`, `REJECTED`, `FAILED`. No outgoing transitions.
- Any transition not in `ALLOWED_TRANSITIONS` raises `ProhibitedTransition`
  (`src/mav_supervisor/state_machine.py`). This is what blocks a jump straight to
  `EXECUTION`.

## Mandatory rejection gates

The supervisor **rejects** a candidate property (never executes it) when a
deterministic gate fires (`src/mav_supervisor/validators.py`):

| Gate | Rejects when |
| --- | --- |
| Grounding | any requirement term has no RTL symbol, or maps to a symbol absent from the manifest |
| Clock | temporal property has no clock, or the clock is not a manifest clock candidate |
| Reset | property references reset but reset signal is missing/unknown, or polarity is ambiguous |
| Syntax | unbalanced parens, dangling operator, or missing implication in a handshake assert |
| Review | review state is not `REVIEWED_OK` |

## Human-approval checkpoint

Human approval is **required before execution** when the task sets any of
`affects_assumptions`, `affects_abstraction`, `affects_budget`,
`affects_proof_scope`, or when the partition report contains `cut_assumptions`.
Without an approving `ApprovalDecision`, the supervisor moves to `REJECTED` and
**never dispatches execution**. Defense in depth: the orchestrator backend itself
refuses any `ExecutionRequest` with `approved=False` (`PermissionError`).

## Artifact-store layout

```
<artifact-root>/
  <task_id>/
    audit.jsonl           # append-only JSONL, one AuditEvent per line
    run_record.json       # provenance for the executed run (if any)
    evidence_packet.json  # the final evidence packet
```

## Audit-log schema (JSONL)

Each line is an `AuditEvent`: `seq` (monotonic from 0), `task_id`, `timestamp`,
`from_state`, `to_state`, `event`, `detail`, `actor`
(`supervisor|rtl_ingestor|sva_agent|partition_agent|orchestrator|human`).
Exported JSON Schema: `schemas/AuditEvent.schema.json`.

## Result vocabulary

`PASS` / `FAIL` / `TIMEOUT` / `ERROR` / `UNKNOWN`, plus `COMPILED` (syntax-only,
**never** a run outcome — the `RunRecord` validator forbids it). A `TIMEOUT`,
`ERROR`, or `UNKNOWN` is never reported as a `PASS`.

## Scope / limitations

- **v0.1, mock backends only.** No real RTL parsing, SVA compilation, or formal
  tool is invoked. Real integrations plug into the `Protocol` interfaces in
  `src/mav_supervisor/backends.py`.
- The syntax gate is a conservative smoke check, not a SystemVerilog parser.
- The config catalog (`src/mav_supervisor/catalog.py`) is fixed and versioned;
  adaptive policy selection is future work.

## Data policy

Public toy content only. No proprietary RTL, customer/employer names, internal
tool names, credentials, or private paths. See `THREAT_MODEL.md`.

## License

MIT (placeholder) — see `LICENSE`.
