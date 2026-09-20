# Evidence

Each claim is tied to source, a test, and a reproduce command. Run everything from
the repo root inside the venv (`pip install -e ".[dev]"`).

| ID | Claim | Source | Test(s) | Reproduce |
| --- | --- | --- | --- | --- |
| E1 | The workflow is an explicit state machine with an allow-list of transitions. | `state_machine.py` (`ALLOWED_TRANSITIONS`, `assert_transition`) | `tests/test_state_machine.py` | `pytest tests/test_state_machine.py` |
| E2 | A candidate with unresolved grounding is rejected and never executed. | `validators.check_grounding`, `supervisor._propose_and_review` | `test_ungrounded_property_is_rejected_not_executed` | `pytest -k ungrounded` |
| E3 | Missing clock / ambiguous reset are rejected. | `validators.check_clock_reset` | `test_missing_clock_is_rejected`, `test_ambiguous_reset_property_is_rejected` | `pytest -k "clock or reset"` |
| E4 | Syntax failures are rejected. | `validators.check_syntax` | `test_syntax_failure_is_detected`, `test_syntax_failure_property_is_rejected` | `pytest -k syntax` |
| E5 | Insufficient review state is rejected. | `validators.check_review` | `test_unreviewed_property_is_flagged` | `pytest -k reviewed` |
| E6 | Human approval is required before execution for assumption/abstraction/budget/proof-scope changes, and blocked without it. | `supervisor._needs_human_approval`, `_approval_gate` | `test_gated_task_without_approval_is_blocked`, `test_gated_task_with_denied_approval_is_blocked` | `pytest -k gated` |
| E7 | Partition cut obligations force the human gate even for otherwise-clean tasks. | `MockPartitionAgent(needs_cut_assumptions=True)`, `_needs_human_approval` | `test_partition_cut_assumptions_force_the_human_gate` | `pytest -k cut_assumptions` |
| E8 | The orchestrator refuses unapproved execution (defense in depth). | `backends.MockOrchestrator.execute` | `test_orchestrator_refuses_unapproved_execution` | `pytest -k refuses_unapproved` |
| E9 | Only approved catalog configs are usable. | `catalog.get_config` | `test_config_outside_catalog_is_rejected` | `pytest -k catalog` |
| E10 | TIMEOUT/ERROR are never reported as PASS; COMPILED is not a run outcome. | `models.RunRecord` validator, `supervisor._recommend_next` | `test_timeout_is_not_reported_as_pass`, `test_error_result_is_surfaced_not_passed`, `test_run_record_rejects_non_execution_result` | `pytest -k "timeout or error or non_execution"` |
| E11 | A full mocked workflow produces a complete evidence packet + append-only JSONL audit log. | `supervisor.run`, `audit.AuditLog`, `models.EvidencePacket` | `test_full_happy_path_produces_evidence_packet`, `test_audit_log_is_jsonl_and_ordered` | `pytest tests/test_workflow.py` |
| E12 | The packet carries explicit non-claims (no validity/proof/signoff). | `models.EvidencePacket.non_claims` | `test_non_claims_present_in_packet` | `pytest -k non_claims` |
| E13 | The CLI runs an end-to-end mocked workflow and enforces the gates. | `cli.py` | `tests/test_cli.py` | `pytest tests/test_cli.py` |

## Full run

```bash
ruff check .
pytest                # 37 tests
mav-supervisor run --task-file examples/task_req_grant.json --artifact-root artifacts
```

## Distinction: implementation vs experimental-performance evidence

All evidence here is **implementation evidence** (the coordinator behaves as
specified against deterministic mocks). There is **no** experimental-performance
claim: no real formal tool is run, so no solved-rate, runtime, or proof result is
asserted.
