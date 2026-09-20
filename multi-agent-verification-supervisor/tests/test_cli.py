from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mav_supervisor.cli import app

runner = CliRunner()


def test_cli_run_demo_task(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", "--artifact-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Final state       : DONE" in result.output
    assert (tmp_path / "demo-req-grant" / "evidence_packet.json").exists()


def test_cli_run_ungrounded_defect_is_rejected(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["run", "--artifact-root", str(tmp_path), "--sva-defect", "ungrounded"]
    )
    assert result.exit_code == 0, result.output
    assert "Final state       : REJECTED" in result.output


def test_cli_run_budget_task_from_file_blocked_without_approve(tmp_path: Path) -> None:
    task_file = Path("examples/task_budget_change.json").resolve()
    result = runner.invoke(
        app, ["run", "--task-file", str(task_file), "--artifact-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "Final state       : REJECTED" in result.output


def test_cli_run_budget_task_with_approve_proceeds(tmp_path: Path) -> None:
    task_file = Path("examples/task_budget_change.json").resolve()
    result = runner.invoke(
        app,
        ["run", "--task-file", str(task_file), "--artifact-root", str(tmp_path), "--approve"],
    )
    assert result.exit_code == 0, result.output
    assert "Final state       : DONE" in result.output


def test_cli_show_catalog() -> None:
    result = runner.invoke(app, ["show-catalog"])
    assert result.exit_code == 0
    assert "CFG-BMC-SHALLOW" in result.output


def test_cli_show_states() -> None:
    result = runner.invoke(app, ["show-states"])
    assert result.exit_code == 0
    assert "EXECUTION" in result.output
