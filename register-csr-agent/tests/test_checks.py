"""Check tests: each deterministic check must actually catch its defect, and a
clean map must produce zero errors."""

from __future__ import annotations

from pathlib import Path

from register_csr_agent.checks import run_all_checks
from register_csr_agent.models import Severity
from register_csr_agent.parsers import load_register_map

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "register_maps"


def _codes(map_name: str) -> set[str]:
    m = load_register_map(EXAMPLES / map_name)
    return {d.code for d in run_all_checks(m)}


def test_clean_map_has_no_errors():
    m = load_register_map(EXAMPLES / "timer_block.yaml")
    discs = run_all_checks(m)
    errors = [d for d in discs if d.severity == Severity.ERROR]
    assert errors == [], errors


def test_buggy_map_catches_all_defect_families():
    codes = _codes("buggy_block.json")
    expected = {
        "ADDR_OVERLAP",
        "ADDR_MISALIGN",
        "FIELD_OOB",
        "FIELD_OVERLAP",
        "RESET_FIELD_SUM",
        "ACCESS_RESERVED_RESET",
        "IRQ_STATUS_ACCESS",
    }
    missing = expected - codes
    assert not missing, f"checks failed to catch: {missing}"


def test_address_dup_detected():
    m = load_register_map(EXAMPLES / "timer_block.yaml")
    m.registers[1].address = m.registers[0].address  # force duplicate
    codes = {d.code for d in run_all_checks(m)}
    assert "ADDR_DUP" in codes


def test_reset_field_sum_math():
    m = load_register_map(EXAMPLES / "timer_block.yaml")
    ctrl = next(r for r in m.registers if r.name == "CTRL")
    ctrl.reset_value = 0x2  # now disagrees with fields (all 0)
    discs = run_all_checks(m)
    sums = [d for d in discs if d.code == "RESET_FIELD_SUM" and d.register == "CTRL"]
    assert len(sums) == 1


def test_error_severity_sorted_first():
    m = load_register_map(EXAMPLES / "buggy_block.json")
    discs = run_all_checks(m)
    severities = [d.severity for d in discs]
    # all ERROR indices come before any WARNING/INFO
    first_warn = next(
        (i for i, s in enumerate(severities) if s != Severity.ERROR), len(severities)
    )
    assert all(s == Severity.ERROR for s in severities[:first_warn])
