from __future__ import annotations

from pathlib import Path

from mav_supervisor.audit import AuditLog
from mav_supervisor.backends import MockOrchestrator
from mav_supervisor.models import (
    ApprovalDecision,
    FormalResult,
    WorkflowState,
)
from mav_supervisor.supervisor import Supervisor

S = WorkflowState


def test_full_happy_path_produces_evidence_packet(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(clean_task, artifact_root=tmp_path)
    packet = sup.run()

    assert packet.final_state == S.DONE
    assert packet.rtl_manifest is not None
    assert packet.candidate_property is not None
    assert packet.partition_report is not None
    assert packet.experiment_plan is not None
    assert packet.run_record is not None
    assert packet.result_classification in {
        FormalResult.PASS, FormalResult.FAIL, FormalResult.TIMEOUT,
    }
    # Evidence packet + run record persisted to the artifact store.
    assert (tmp_path / clean_task.task_id / "evidence_packet.json").exists()
    assert (tmp_path / clean_task.task_id / "run_record.json").exists()


def test_non_claims_present_in_packet(clean_task, tmp_path: Path) -> None:
    packet = Supervisor(clean_task, artifact_root=tmp_path).run()
    joined = " ".join(packet.non_claims).lower()
    assert "did not declare the assertion valid" in joined
    assert "signoff" in joined


def test_audit_log_is_jsonl_and_ordered(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(clean_task, artifact_root=tmp_path)
    sup.run()
    log = AuditLog(sup.store.audit_path(clean_task.task_id))
    events = log.read_all()
    assert len(events) > 5
    # seq is strictly increasing from 0.
    assert [e.seq for e in events] == list(range(len(events)))
    # First transition is CREATED -> RTL_INGESTION.
    assert events[0].from_state == S.CREATED
    assert events[0].to_state == S.RTL_INGESTION
    # Terminal event reaches DONE.
    assert events[-1].to_state == S.DONE


def test_budget_change_requires_approval_and_proceeds_when_approved(
    budget_task, tmp_path: Path
) -> None:
    sup = Supervisor(
        budget_task, artifact_root=tmp_path,
        orchestrator_backend=MockOrchestrator(forced_result=FormalResult.PASS),
    )
    approval = ApprovalDecision(
        task_id=budget_task.task_id, approver="alice", approved=True, reason="ok",
    )
    packet = sup.run(approval=approval)
    assert packet.final_state == S.DONE
    assert packet.experiment_plan is not None
    assert packet.experiment_plan.needs_human_approval is True
    assert packet.approval is not None and packet.approval.approved is True
    assert packet.result_classification == FormalResult.PASS


def test_timeout_is_not_reported_as_pass(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        orchestrator_backend=MockOrchestrator(forced_result=FormalResult.TIMEOUT),
    )
    packet = sup.run()
    assert packet.result_classification == FormalResult.TIMEOUT
    assert packet.result_classification != FormalResult.PASS
    assert "inconclusive" in packet.next_recommended_action.lower()
