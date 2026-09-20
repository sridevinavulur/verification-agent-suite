"""Typer CLI for the Multi-Agent Verification Supervisor."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .backends import MockOrchestrator, MockPartitionAgent, MockSvaAgent
from .catalog import APPROVED_CONFIGS, CATALOG_VERSION
from .models import ApprovalDecision, VerificationTask
from .state_machine import ALLOWED_TRANSITIONS
from .supervisor import Supervisor

app = typer.Typer(
    add_completion=False,
    help="State-machine workflow coordinator for verification agents (mock backends).",
)


@app.command()
def run(
    task_file: Path | None = typer.Option(
        None, "--task-file", help="JSON file with a VerificationTask. Omit to use the demo task."
    ),
    artifact_root: Path = typer.Option(
        Path("artifacts"), "--artifact-root", help="Artifact-store root directory."
    ),
    approve: bool = typer.Option(
        False, "--approve", help="Provide human approval for gated plans."
    ),
    approver: str = typer.Option("cli-user", "--approver", help="Approver identity."),
    sva_defect: str | None = typer.Option(
        None, "--sva-defect",
        help="Inject a defective candidate: ungrounded|no_clock|syntax|ambiguous_reset.",
    ),
    cut_assumptions: bool = typer.Option(
        False, "--cut-assumptions",
        help="Make the partition agent emit unproven cut obligations (forces human gate).",
    ),
) -> None:
    """Run a full mocked workflow and print the evidence packet path + result."""
    if task_file is not None:
        task = VerificationTask.model_validate_json(task_file.read_text(encoding="utf-8"))
    else:
        task = _demo_task()

    supervisor = Supervisor(
        task,
        artifact_root=artifact_root,
        sva_backend=MockSvaAgent(defect=sva_defect),
        partition_backend=MockPartitionAgent(needs_cut_assumptions=cut_assumptions),
        orchestrator_backend=MockOrchestrator(),
    )

    approval = None
    if approve or task.requires_human_approval() or cut_assumptions:
        approval = ApprovalDecision(
            task_id=task.task_id, approver=approver,
            approved=approve, reason="CLI approval" if approve else "CLI: not approved",
        )

    packet = supervisor.run(approval=approval)

    typer.echo(f"Final state       : {packet.final_state.value}")
    typer.echo(f"Result            : {packet.result_classification}")
    typer.echo(f"Validation findings: {packet.validation_findings or 'none'}")
    typer.echo(f"Next action       : {packet.next_recommended_action}")
    typer.echo(f"Evidence packet   : {artifact_root / task.task_id / 'evidence_packet.json'}")
    typer.echo(f"Audit log         : {packet.audit_log_path}")


@app.command("show-catalog")
def show_catalog() -> None:
    """Print the approved experiment-configuration catalog."""
    typer.echo(f"Catalog version: {CATALOG_VERSION}")
    for cid, cfg in APPROVED_CONFIGS.items():
        typer.echo(f"  {cid}: engine={cfg.engine} bmc_depth={cfg.bmc_depth} "
                   f"timeout={cfg.timeout_s}s prep={cfg.preprocessing}")


@app.command("show-states")
def show_states() -> None:
    """Print the state machine's allowed transitions."""
    for src, dsts in ALLOWED_TRANSITIONS.items():
        targets = ", ".join(sorted(d.value for d in dsts)) or "(terminal)"
        typer.echo(f"  {src.value:24s} -> {targets}")


@app.command()
def demo(
    artifact_root: Path = typer.Option(Path("artifacts"), "--artifact-root"),
) -> None:
    """End-to-end demo: nominal happy path with a clean candidate property."""
    task = _demo_task()
    supervisor = Supervisor(task, artifact_root=artifact_root)
    packet = supervisor.run()
    typer.echo(json.dumps(json.loads(packet.model_dump_json()), indent=2))


def _demo_task() -> VerificationTask:
    return VerificationTask(
        task_id="demo-req-grant",
        repo_revision="deadbeef",
        requirement_text=(
            "Whenever req is accepted, grant must arrive within 1 to 3 cycles "
            "unless reset is asserted."
        ),
        rtl_files=["examples/handshake.sv"],
    )


if __name__ == "__main__":  # pragma: no cover
    app()
