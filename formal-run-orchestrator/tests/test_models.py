"""Schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from formal_run_orchestrator.catalog import CATALOG_VERSION, all_configs
from formal_run_orchestrator.models import (
    EngineFamily,
    RunStatus,
    SolverConfig,
)
from formal_run_orchestrator.sample_suite import build_sample_suite


def test_run_status_success_and_conclusive():
    assert RunStatus.PASS.is_success
    assert not RunStatus.FAIL.is_success
    assert not RunStatus.TIMEOUT.is_success
    assert not RunStatus.ERROR.is_success
    assert not RunStatus.INCONCLUSIVE.is_success
    assert RunStatus.PASS.is_conclusive
    assert RunStatus.FAIL.is_conclusive
    assert not RunStatus.TIMEOUT.is_conclusive
    assert not RunStatus.INCONCLUSIVE.is_conclusive


def test_solver_config_is_frozen_and_validates_bounds():
    c = all_configs()[0]
    with pytest.raises(ValidationError):
        SolverConfig(
            config_id="bad",
            catalog_version=CATALOG_VERSION,
            engine=EngineFamily.BMC,
            bmc_depth=0,  # < 1 -> invalid
            timeout_s=30,
            memory_cap_mb=2048,
            preprocessing=c.preprocessing,
            partition_strategy=c.partition_strategy,
        )
    with pytest.raises(ValidationError):
        # frozen model: assignment must fail
        c.bmc_depth = 999  # type: ignore[misc]


def test_command_line_is_deterministic_and_names_config():
    c = all_configs()[0]
    cl1 = c.command_line("design.sv", "p1")
    cl2 = c.command_line("design.sv", "p1")
    assert cl1 == cl2
    assert c.engine.value in cl1
    assert "--bmc-depth" in cl1


def test_sample_suite_valid_and_unique_ids():
    suite = build_sample_suite()
    ids = [i.benchmark_id for i in suite.items]
    assert len(ids) == len(set(ids))
    assert len(suite.items) >= 12
    # every item has a difficulty in range and a group
    for it in suite.items:
        assert 0.0 <= it.intrinsic_difficulty <= 1.0
        assert it.group
