# Architecture

## Design principle

The supervisor is a **manager coordinating specialist agents as bounded tools**
via an explicit state machine — not an LLM performing unconstrained conversational
handoffs. Every step is a typed request/response and every transition is checked
against an allow-list.

## Components

| Module | Responsibility |
| --- | --- |
| `models.py` | All Pydantic v2 typed contracts (messages, states, audit, evidence). Validation is enforced (`extra="forbid"`, field constraints, a `RunRecord` result validator). |
| `state_machine.py` | `ALLOWED_TRANSITIONS` allow-list + `assert_transition`. Single source of truth for legal vs prohibited moves. |
| `validators.py` | Deterministic (non-LLM) rejection gates: grounding, clock/reset, syntax, review. |
| `catalog.py` | Finite, versioned approved experiment-config catalog. Selecting outside it raises. |
| `backends.py` | `Protocol` interfaces + deterministic **mock** implementations of the four agents. |
| `audit.py` | Append-only JSONL `AuditLog` and `ArtifactStore` layout. |
| `supervisor.py` | The state-machine driver: stages, gates, human-approval checkpoint, evidence assembly. |
| `cli.py` | Typer CLI: `run`, `demo`, `show-states`, `show-catalog`. |

## Dataflow (happy path)

```
VerificationTask
  -> RtlIngestRequest  -> [RTL Ingestor]  -> RtlManifest
  -> SvaProposalRequest -> [SVA Agent]    -> CandidateProperty
       -> validators.validate_property(candidate, manifest)   (GATE)
  -> PartitionRequest  -> [Partition Agent] -> PartitionReport
  -> ExperimentPlan (config from approved catalog)
       -> human-approval checkpoint (if required)             (GATE)
  -> ExecutionRequest(approved=...) -> [Orchestrator] -> RunRecord
  -> EvidencePacket
```

## Typed input/output contracts

Each agent has an explicit request and response model (see `models.py`):

- RTL Ingestor: `RtlIngestRequest` -> `RtlManifest`
- SVA Agent: `SvaProposalRequest` -> `CandidateProperty`
- Partition Agent: `PartitionRequest` -> `PartitionReport`
- Orchestrator: `ExecutionRequest` -> `RunRecord`

Cross-cutting: `ExperimentPlan`, `ApprovalDecision`, `AuditEvent`,
`EvidencePacket`. JSON Schemas are exported under `schemas/`
(regenerate with `python scripts/export_schemas.py`).

## Authority boundaries

- **LLM/agent layer proposes** hypotheses, mappings, candidate properties,
  partitions, and configs (here: mock backends).
- **Deterministic layer validates** grounding, clock/reset, syntax, review state,
  transition legality, catalog membership, and result vocabulary.
- The supervisor **may**: dispatch agents, reject candidates, plan from the
  approved catalog, request approval, execute an approved plan, classify and
  report the backend result, recommend a next action.
- The supervisor **may not**: modify RTL, assumptions, proof scope, budgets, or
  abstraction boundaries without a human-approval gate; declare an assertion
  valid; declare a proof complete; declare signoff; or map TIMEOUT/ERROR/UNKNOWN
  to PASS.

## Failure recovery

- Property gate failure -> bounded retry (`max_property_retries`) then `REJECTED`.
- Missing/denied approval on a gated plan -> `REJECTED`, no execution.
- Unexpected exception -> best-effort audited transition to `FAILED`, re-raised.
- Orchestrator refuses unapproved runs (`PermissionError`) as defense in depth.

## Extending to real backends

Implement the `Protocol`s in `backends.py`
(`RtlIngestorBackend`, `SvaAgentBackend`, `PartitionAgentBackend`,
`OrchestratorBackend`) and inject them into `Supervisor(...)`. No supervisor,
state-machine, gate, audit, or evidence code needs to change.
