"""The Multi-Agent Verification Supervisor state machine.

The supervisor is a policy/workflow coordinator. It:

* drives an explicit state machine (never free-form handoffs),
* rejects candidate properties that fail deterministic gates,
* requires human approval before EXECUTION when the task affects assumptions,
  abstraction, budgets, or proof scope (or when partition cuts add obligations),
* refuses to execute an unapproved plan,
* returns a complete evidence packet.

It NEVER independently declares an assertion valid, a proof complete, or signoff
achieved. It only reports the backend's classified result.
"""

from __future__ import annotations

from pathlib import Path

from .audit import ArtifactStore, AuditLog
from .backends import (
    MockOrchestrator,
    MockPartitionAgent,
    MockRtlIngestor,
    MockSvaAgent,
    OrchestratorBackend,
    PartitionAgentBackend,
    RtlIngestorBackend,
    SvaAgentBackend,
)
from .catalog import default_config, get_config
from .models import (
    ApprovalDecision,
    CandidateProperty,
    EvidencePacket,
    ExecutionRequest,
    ExperimentPlan,
    FormalResult,
    PartitionReport,
    PartitionRequest,
    RtlIngestRequest,
    RtlManifest,
    RunRecord,
    SvaProposalRequest,
    VerificationTask,
    WorkflowState,
)
from .state_machine import assert_transition
from .validators import validate_property

S = WorkflowState


class SupervisorError(RuntimeError):
    """Non-transition supervisor error (e.g. unapproved execution attempt)."""


class Supervisor:
    def __init__(
        self,
        task: VerificationTask,
        artifact_root: Path,
        *,
        rtl_backend: RtlIngestorBackend | None = None,
        sva_backend: SvaAgentBackend | None = None,
        partition_backend: PartitionAgentBackend | None = None,
        orchestrator_backend: OrchestratorBackend | None = None,
        max_property_retries: int = 1,
    ) -> None:
        self.task = task
        self.state: WorkflowState = S.CREATED
        self.store = ArtifactStore(artifact_root)
        self.audit = AuditLog(self.store.audit_path(task.task_id))
        self.rtl_backend = rtl_backend or MockRtlIngestor()
        self.sva_backend = sva_backend or MockSvaAgent()
        self.partition_backend = partition_backend or MockPartitionAgent()
        self.orchestrator_backend = orchestrator_backend or MockOrchestrator()
        self.max_property_retries = max_property_retries

        # Workflow artifacts collected as we go.
        self.manifest: RtlManifest | None = None
        self.candidate: CandidateProperty | None = None
        self.validation_findings: list[str] = []
        self.partition: PartitionReport | None = None
        self.plan: ExperimentPlan | None = None
        self.approval: ApprovalDecision | None = None
        self.run_record: RunRecord | None = None

    # -- transition helper -------------------------------------------------

    def _go(
        self, dst: WorkflowState, event: str, detail: str = "", actor: str = "supervisor"
    ) -> None:
        assert_transition(self.state, dst)
        self.audit.append(self.task.task_id, self.state, dst, event, detail, actor)
        self.state = dst

    # -- gate: does this task need human approval before execution? --------

    def _needs_human_approval(self) -> bool:
        if self.task.requires_human_approval():
            return True
        # Partition cuts that add unproven obligations affect assumptions.
        return bool(self.partition is not None and self.partition.cut_assumptions)

    # -- stages ------------------------------------------------------------

    def _ingest(self) -> None:
        self._go(S.RTL_INGESTION, "dispatch_rtl_ingestion", actor="supervisor")
        req = RtlIngestRequest(
            task_id=self.task.task_id,
            repo_revision=self.task.repo_revision,
            rtl_files=self.task.rtl_files,
        )
        self.manifest = self.rtl_backend.ingest(req)
        self.audit.append(
            self.task.task_id, self.state, self.state,
            "rtl_manifest_received",
            f"design_top={self.manifest.design_top} hash={self.manifest.manifest_hash}",
            actor="rtl_ingestor",
        )

    def _propose_and_review(self) -> bool:
        """Propose a candidate property, run gates, and (mock) review.

        Returns True if the property passes all gates and review; False if the
        supervisor REJECTS it. Retries up to ``max_property_retries``.
        """
        assert self.manifest is not None
        self._go(S.SVA_PROPOSAL, "request_sva_candidate", actor="supervisor")

        for attempt in range(self.max_property_retries + 1):
            req = SvaProposalRequest(
                task_id=self.task.task_id,
                requirement_text=self.task.requirement_text,
                manifest_hash=self.manifest.manifest_hash,
            )
            candidate = self.sva_backend.propose(req)
            self.candidate = candidate
            self.audit.append(
                self.task.task_id, self.state, self.state,
                "sva_candidate_received",
                f"property_id={candidate.property_id} attempt={attempt}",
                actor="sva_agent",
            )

            self._go(S.PROPERTY_REVIEW, "enter_property_review", actor="supervisor")

            # Deterministic gates first (grounding, clock/reset, syntax).
            findings = validate_property(candidate, self.manifest)
            # The mock "human/LLM review" only sets REVIEWED_OK if deterministic
            # gates (other than the review gate itself) are clean.
            non_review = [f for f in findings if not f.startswith("REVIEW:")]
            if not non_review:
                candidate.review_state = candidate.review_state.REVIEWED_OK
                findings = validate_property(candidate, self.manifest)
            self.validation_findings = findings

            if not findings:
                self.audit.append(
                    self.task.task_id, self.state, self.state,
                    "property_accepted", f"property_id={candidate.property_id}",
                    actor="supervisor",
                )
                return True

            self.audit.append(
                self.task.task_id, self.state, self.state,
                "property_gate_failed",
                f"findings={findings}",
                actor="supervisor",
            )
            if attempt < self.max_property_retries:
                # Retry: go back to SVA proposal.
                self._go(S.SVA_PROPOSAL, "retry_sva_candidate",
                         f"prior_findings={len(findings)}", actor="supervisor")

        # Exhausted retries -> reject.
        self._go(S.REJECTED, "reject_property",
                 f"findings={self.validation_findings}", actor="supervisor")
        return False

    def _partition(self) -> None:
        assert self.candidate is not None and self.manifest is not None
        self._go(S.PARTITION_ANALYSIS, "request_partition_analysis", actor="supervisor")
        req = PartitionRequest(
            task_id=self.task.task_id,
            property_id=self.candidate.property_id,
            manifest_hash=self.manifest.manifest_hash,
        )
        self.partition = self.partition_backend.analyze(req, self.manifest)
        self.audit.append(
            self.task.task_id, self.state, self.state,
            "partition_report_received",
            f"coi={len(self.partition.coi_signals)} "
            f"cut_assumptions={len(self.partition.cut_assumptions)}",
            actor="partition_agent",
        )

    def _plan(self) -> None:
        assert self.candidate is not None
        self._go(S.PLAN_EXPERIMENT, "create_experiment_plan", actor="supervisor")
        config = default_config()
        # Validate the choice is in the approved catalog (raises if not).
        get_config(config.config_id)
        needs_approval = self._needs_human_approval()
        self.plan = ExperimentPlan(
            task_id=self.task.task_id,
            property_id=self.candidate.property_id,
            config=config,
            needs_human_approval=needs_approval,
        )
        self.audit.append(
            self.task.task_id, self.state, self.state,
            "experiment_plan_created",
            f"config={config.config_id} needs_approval={needs_approval}",
            actor="supervisor",
        )

    def _approval_gate(self, approval: ApprovalDecision | None) -> bool:
        """Handle the human-approval checkpoint. Returns True to proceed."""
        assert self.plan is not None
        if not self.plan.needs_human_approval:
            return True

        self._go(S.AWAITING_HUMAN_APPROVAL, "await_human_approval", actor="supervisor")
        if approval is None:
            # No approval provided for a plan that requires it -> block (reject).
            self._go(S.REJECTED, "blocked_missing_approval",
                     "plan requires human approval but none was provided.",
                     actor="supervisor")
            return False
        self.approval = approval
        self.audit.append(
            self.task.task_id, self.state, self.state,
            "human_decision", f"approved={approval.approved} by={approval.approver}",
            actor="human",
        )
        if not approval.approved:
            self._go(S.REJECTED, "approval_denied", approval.reason, actor="human")
            return False
        return True

    def _execute(self) -> None:
        assert self.plan is not None and self.manifest is not None
        self._go(S.EXECUTION, "dispatch_execution", actor="supervisor")
        approved = (not self.plan.needs_human_approval) or (
            self.approval is not None and self.approval.approved
        )
        req = ExecutionRequest(
            task_id=self.task.task_id,
            property_id=self.plan.property_id,
            config=self.plan.config,
            approved=approved,
        )
        # The backend also refuses unapproved runs; this is defense in depth.
        self.run_record = self.orchestrator_backend.execute(
            req, self.task.repo_revision, self.manifest.manifest_hash
        )
        self.store.write_json(self.task.task_id, "run_record.json", self.run_record)
        self.audit.append(
            self.task.task_id, self.state, self.state,
            "run_completed", f"result={self.run_record.result.value}",
            actor="orchestrator",
        )

    def _assemble_evidence(self) -> EvidencePacket:
        self._go(S.EVIDENCE_ASSEMBLY, "assemble_evidence", actor="supervisor")
        packet = self._build_packet(final_state=S.DONE)
        self.store.write_json(self.task.task_id, "evidence_packet.json", packet)
        self._go(S.DONE, "workflow_done", f"result={packet.result_classification}",
                 actor="supervisor")
        # Re-stamp final_state to DONE in the persisted packet.
        packet.final_state = S.DONE
        self.store.write_json(self.task.task_id, "evidence_packet.json", packet)
        return packet

    def _build_packet(self, final_state: WorkflowState) -> EvidencePacket:
        result = self.run_record.result if self.run_record else None
        limitations = [
            "Backend is a deterministic MOCK; results are illustrative, not real "
            "formal outcomes.",
            "Partition proposals are heuristic and not a proven formal reduction.",
        ]
        if self.partition and self.partition.cut_assumptions:
            limitations.append(
                "Partition introduces unproven cut obligations: "
                f"{self.partition.cut_assumptions}."
            )
        next_action = self._recommend_next(result)
        return EvidencePacket(
            task_id=self.task.task_id,
            final_state=final_state,
            requirement_text=self.task.requirement_text,
            repo_revision=self.task.repo_revision,
            rtl_manifest=self.manifest,
            candidate_property=self.candidate,
            validation_findings=self.validation_findings,
            partition_report=self.partition,
            experiment_plan=self.plan,
            approval=self.approval,
            run_record=self.run_record,
            result_classification=result,
            limitations=limitations,
            next_recommended_action=next_action,
            audit_log_path=str(self.store.audit_path(self.task.task_id)),
        )

    def _recommend_next(self, result: FormalResult | None) -> str:
        if self.state == S.REJECTED:
            return ("Address the gate findings and resubmit a corrected candidate "
                    "property; or obtain human approval where required.")
        if result is None:
            return "No execution occurred; review workflow state."
        if result == FormalResult.PASS:
            return ("Backend PASS recorded for this exact config. Human review "
                    "required before any signoff claim; consider deeper config.")
        if result == FormalResult.FAIL:
            return "Triage the counterexample before calling it a design bug."
        if result in (FormalResult.TIMEOUT, FormalResult.UNKNOWN):
            return ("Inconclusive: escalate to a deeper config (human approval "
                    "required as it changes the budget/proof scope).")
        return "Investigate the tool ERROR; the run is invalid."

    # -- public entrypoint -------------------------------------------------

    def run(self, approval: ApprovalDecision | None = None) -> EvidencePacket:
        """Drive the full workflow. Returns an evidence packet in all outcomes."""
        try:
            self._ingest()
            if not self._propose_and_review():
                return self._finish_rejected()
            self._partition()
            self._plan()
            if not self._approval_gate(approval):
                return self._finish_rejected()
            self._execute()
            return self._assemble_evidence()
        except Exception as exc:  # noqa: BLE001 - convert to FAILED terminal state
            if self.state not in (S.FAILED, S.REJECTED, S.DONE):
                # Best-effort transition to FAILED for auditability.
                try:
                    self.audit.append(
                        self.task.task_id, self.state, S.FAILED,
                        "workflow_exception", str(exc), actor="supervisor",
                    )
                    self.state = S.FAILED
                except Exception:  # noqa: BLE001
                    pass
            raise

    def _finish_rejected(self) -> EvidencePacket:
        packet = self._build_packet(final_state=S.REJECTED)
        self.store.write_json(self.task.task_id, "evidence_packet.json", packet)
        return packet
