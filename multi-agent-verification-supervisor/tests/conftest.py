from __future__ import annotations

import pytest

from mav_supervisor.models import VerificationTask


@pytest.fixture
def clean_task() -> VerificationTask:
    return VerificationTask(
        task_id="t-clean",
        repo_revision="rev-abc",
        requirement_text=(
            "Whenever req is accepted, grant must arrive within 1 to 3 cycles "
            "unless reset is asserted."
        ),
        rtl_files=["examples/handshake.sv"],
    )


@pytest.fixture
def budget_task() -> VerificationTask:
    return VerificationTask(
        task_id="t-budget",
        repo_revision="rev-abc",
        requirement_text="Same requirement but the run budget changes.",
        rtl_files=["examples/handshake.sv"],
        affects_budget=True,
    )
