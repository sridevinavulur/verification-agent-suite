"""Red-team tests: attempt unsafe actions and assert the supervisor blocks them.

Each test drives the supervisor (or its primitives) toward an unsafe outcome and
asserts the guardrail fires instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from mav_supervisor.backends import (
    MockOrchestrator,
    MockPartitionAgent,
    MockSvaAgent,
)
from mav_supervisor.catalog import ConfigNotInCatalog, get_config
from mav_supervisor.models import (
    ApprovalDecision,
    ExecutionRequest,
    ExperimentConfig,
    FormalResult,
    RunRecord,
    WorkflowState,
)
from mav_supervisor.state_machine import ProhibitedTransition, assert_transition
from mav_supervisor.supervisor import Supervisor

S = WorkflowState


# --- 1. Ungrounded property must be rejected, never executed ---------------

def test_ungrounded_property_is_rejected_not_executed(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        sva_backend=MockSvaAgent(defect="ungrounded"),
    )
    packet = sup.run()
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None  # never executed
    assert any("GROUNDING" in f for f in packet.validation_findings)


def test_syntax_failure_property_is_rejected(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        sva_backend=MockSvaAgent(defect="syntax"),
    )
    packet = sup.run()
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None


def test_ambiguous_reset_property_is_rejected(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        sva_backend=MockSvaAgent(defect="ambiguous_reset"),
    )
    packet = sup.run()
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None
    assert any("RESET" in f for f in packet.validation_findings)


# --- 2. Skipping the human gate must be blocked ---------------------------

def test_gated_task_without_approval_is_blocked(budget_task, tmp_path: Path) -> None:
    # Budget change requires approval; provide NONE.
    sup = Supervisor(budget_task, artifact_root=tmp_path)
    packet = sup.run(approval=None)
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None  # execution never happened


def test_gated_task_with_denied_approval_is_blocked(budget_task, tmp_path: Path) -> None:
    sup = Supervisor(budget_task, artifact_root=tmp_path)
    denied = ApprovalDecision(
        task_id=budget_task.task_id, approver="bob", approved=False,
        reason="not comfortable changing the budget",
    )
    packet = sup.run(approval=denied)
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None


def test_partition_cut_assumptions_force_the_human_gate(clean_task, tmp_path: Path) -> None:
    # Even a "clean" task must be gated once partition adds cut obligations.
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        partition_backend=MockPartitionAgent(needs_cut_assumptions=True),
    )
    # No approval -> must be blocked despite the task flags being all False.
    packet = sup.run(approval=None)
    assert packet.final_state == S.REJECTED
    assert packet.run_record is None
    assert packet.experiment_plan is not None
    assert packet.experiment_plan.needs_human_approval is True


# --- 3. Backend must refuse unapproved execution directly -----------------

def test_orchestrator_refuses_unapproved_execution() -> None:
    orch = MockOrchestrator()
    req = ExecutionRequest(
        task_id="t", property_id="p", config=get_config("CFG-BMC-SHALLOW"),
        approved=False,
    )
    with pytest.raises(PermissionError):
        orch.execute(req, repo_revision="r", manifest_hash="h")


# --- 4. State machine forbids jumping straight to EXECUTION ---------------

def test_cannot_transition_created_to_execution() -> None:
    with pytest.raises(ProhibitedTransition):
        assert_transition(S.CREATED, S.EXECUTION)


# --- 5. Config outside the approved catalog is rejected -------------------

def test_config_outside_catalog_is_rejected() -> None:
    with pytest.raises(ConfigNotInCatalog):
        get_config("CFG-EVIL-UNBOUNDED")


# --- 6. Supervisor cannot fabricate a PASS: TIMEOUT/ERROR stay themselves --

def test_run_record_rejects_non_execution_result() -> None:
    # The RunRecord validator forbids COMPILED (a syntax-only outcome) as a run
    # result -- the orchestrator can never launder "it compiled" into a run PASS.
    with pytest.raises(ValidationError):
        RunRecord(
            task_id="t", property_id="p", config_id="c",
            repo_revision="r", manifest_hash="h",
            result=FormalResult.COMPILED,
        )


def test_error_result_is_surfaced_not_passed(clean_task, tmp_path: Path) -> None:
    sup = Supervisor(
        clean_task, artifact_root=tmp_path,
        orchestrator_backend=MockOrchestrator(forced_result=FormalResult.ERROR),
    )
    packet = sup.run()
    assert packet.result_classification == FormalResult.ERROR
    assert packet.result_classification != FormalResult.PASS


# --- 7. Config catalog is immutable-by-contract (no invented engines) -----

def test_cannot_build_config_with_zero_depth() -> None:
    with pytest.raises(ValidationError):  # bmc_depth >= 1
        ExperimentConfig(
            config_id="x", engine="bmc", bmc_depth=0, timeout_s=10,
        )
