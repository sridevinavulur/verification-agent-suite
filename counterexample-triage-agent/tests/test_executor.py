"""Tests for the reproduction executor adapters (task 1).

These stay CI-safe: the deterministic path never runs a subprocess, and the
Verilator path is only exercised for its *graceful skip* behavior (no simulator
is actually required to run these tests).
"""

import cx_triage.executor as executor_mod
from cx_triage.compose import compose_report
from cx_triage.executor import (
    DeterministicExecutor,
    ReproStatus,
    VerilatorReproExecutor,
    get_executor,
)
from cx_triage.models import AssertionFailure, RTLIntentManifest
from cx_triage.parser import parse_vcd_file
from cx_triage.triage import TriageEngine


def _toy_report(examples_dir):
    d = examples_dir / "toy_counter"
    trace = parse_vcd_file(d / "counter_fail.vcd")
    failure = AssertionFailure.model_validate_json((d / "failure.json").read_text())
    manifest = RTLIntentManifest.model_validate_json((d / "manifest.json").read_text())
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    return report, trace


# -- deterministic (default) path -------------------------------------------


def test_deterministic_executor_reproduces_present_artifacts(examples_dir):
    d = examples_dir / "toy_counter"
    ex = get_executor(
        "deterministic",
        trace_path=d / "counter_fail.vcd",
        failure_path=d / "failure.json",
        trace_signal_count=5,
    )
    res = ex.reproduce()
    assert res.status == ReproStatus.REPRODUCED
    assert res.adapter == "deterministic-v1"
    assert not res.is_conclusive_pass  # "reproduced" is not a DUT-pass


def test_deterministic_executor_errors_on_missing_artifacts(tmp_path):
    ex = DeterministicExecutor(
        trace_path=tmp_path / "nope.vcd",
        failure_path=tmp_path / "nope.json",
    )
    res = ex.reproduce()
    assert res.status == ReproStatus.ERROR
    assert res.status != ReproStatus.REPRODUCED


def test_deterministic_executor_errors_on_empty_trace(examples_dir):
    d = examples_dir / "toy_counter"
    ex = DeterministicExecutor(
        trace_path=d / "counter_fail.vcd",
        failure_path=d / "failure.json",
        trace_signal_count=0,
    )
    res = ex.reproduce()
    assert res.status == ReproStatus.ERROR


# -- verilator path (graceful skip; no simulator required) -------------------


def test_verilator_executor_skips_when_absent(monkeypatch, tmp_path):
    # Force "verilator not found" regardless of the host environment.
    monkeypatch.setattr(executor_mod, "_find_verilator", lambda: None)
    ex = VerilatorReproExecutor(
        rtl_files=[tmp_path / "dut.v"],
        top_module="dut",
        work_dir=tmp_path / "work",
    )
    res = ex.reproduce()
    assert res.status == ReproStatus.SKIPPED  # never fails, never a pass
    assert "verilator" in res.summary.lower()


def test_verilator_executor_errors_on_missing_rtl(monkeypatch, tmp_path):
    monkeypatch.setattr(executor_mod, "_find_verilator", lambda: "/fake/verilator")
    ex = VerilatorReproExecutor(
        rtl_files=[tmp_path / "does_not_exist.v"],
        top_module="dut",
        work_dir=tmp_path / "work",
    )
    res = ex.reproduce()
    assert res.status == ReproStatus.ERROR
    assert res.status != ReproStatus.NOT_REPRODUCED


def test_get_executor_rejects_unknown_kind():
    import pytest

    with pytest.raises(ValueError):
        get_executor("magic-sim")


# -- composition: advisory, never re-ranks (task 2) -------------------------


def test_compose_attaches_advisory_without_reranking(examples_dir):
    report, _ = _toy_report(examples_dir)
    ranking_before = [(h.category, h.confidence) for h in report.hypotheses]
    d = examples_dir / "toy_counter"
    result = get_executor(
        "deterministic",
        trace_path=d / "counter_fail.vcd",
        failure_path=d / "failure.json",
        trace_signal_count=5,
    ).reproduce()
    compose_report(report, repro=result)
    ranking_after = [(h.category, h.confidence) for h in report.hypotheses]
    assert ranking_after == ranking_before  # deterministic ranking is authoritative
    assert report.reproduction_attempt is not None
    assert report.reproduction_attempt.status == "reproduced"


def test_compose_skip_is_never_a_pass_and_is_surfaced(examples_dir, monkeypatch, tmp_path):
    report, _ = _toy_report(examples_dir)
    monkeypatch.setattr(executor_mod, "_find_verilator", lambda: None)
    result = VerilatorReproExecutor(
        rtl_files=[tmp_path / "dut.v"], top_module="dut", work_dir=tmp_path
    ).reproduce()
    compose_report(report, repro=result)
    assert report.reproduction_attempt.status == "skipped"
    assert any("inconclusive" in q.lower() for q in report.unresolved_questions)


def test_compose_not_reproduced_adds_caution_note(examples_dir):
    from cx_triage.executor import ReproResult

    report, _ = _toy_report(examples_dir)
    top_before = report.top_hypothesis().category
    result = ReproResult(status=ReproStatus.NOT_REPRODUCED, adapter="verilator-cocotb-v1")
    compose_report(report, repro=result)
    # Ranking unchanged; a caution note is appended.
    assert report.top_hypothesis().category == top_before
    assert any("did NOT reproduce" in q for q in report.unresolved_questions)
