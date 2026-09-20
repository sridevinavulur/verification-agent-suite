"""Mock executor tests: determinism, provenance completeness, invalid-config handling."""

from __future__ import annotations

from formal_run_orchestrator.catalog import get_config
from formal_run_orchestrator.executor import execute, simulate
from formal_run_orchestrator.models import RunStatus, ValidationStatus
from formal_run_orchestrator.sample_suite import build_sample_suite


def _item(bid: str):
    return next(i for i in build_sample_suite().items if i.benchmark_id == bid)


def test_simulate_is_deterministic():
    it = _item("fifo_no_overflow")
    cfg = get_config("kind_mid")
    a = simulate(it, cfg, 7)
    b = simulate(it, cfg, 7)
    assert a == b


def test_execute_records_full_provenance():
    it = _item("cnt_no_overflow")
    rec = execute(
        it, "kind_mid", 42, plan_id="p", run_id="r1", rationale="test"
    )
    # All required provenance fields present and non-empty.
    assert rec.design_sha and rec.property_sha and rec.input_hash
    assert rec.tool_name and rec.tool_version
    assert rec.command_line and rec.config_id == "kind_mid"
    assert rec.catalog_version
    assert rec.machine.hostname and rec.machine.python_version
    assert rec.cpu_time_s >= 0 and rec.wall_time_s >= 0 and rec.peak_memory_mb >= 0
    assert rec.start_time <= rec.end_time
    assert rec.validation_status is ValidationStatus.VALID


def test_holding_property_can_pass_and_bug_can_fail():
    holds = execute(_item("cnt_no_overflow"), "kind_mid", 1, plan_id="p", run_id="r2",
                    rationale="")
    bug = execute(_item("cnt_wrap_bug"), "bmc_shallow", 1, plan_id="p", run_id="r3",
                  rationale="")
    assert holds.status is RunStatus.PASS
    assert bug.status is RunStatus.FAIL


def test_invalid_config_is_error_not_hidden():
    rec = execute(
        _item("cnt_no_overflow"), "does_not_exist", 1,
        plan_id="p", run_id="r4", rationale="",
    )
    assert rec.status is RunStatus.ERROR
    assert rec.validation_status is ValidationStatus.INVALID_CONFIG
    # never silently a pass
    assert rec.status is not RunStatus.PASS


def test_shallow_bmc_on_deep_property_never_passes():
    # alu_add_comm resolves at depth 150; shallow BMC (depth 20) cannot conclude PASS.
    rec = execute(_item("alu_add_comm"), "bmc_shallow", 3, plan_id="p", run_id="r5",
                  rationale="")
    assert rec.status is not RunStatus.PASS


def test_artifact_written_and_hashed(tmp_path):
    rec = execute(
        _item("cnt_no_overflow"), "kind_mid", 1,
        plan_id="p", run_id="r6", rationale="", artifact_dir=str(tmp_path),
    )
    assert rec.artifact_path is not None
    assert rec.artifact_hash is not None
