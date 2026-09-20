"""Classifier tests -- the safety-critical mapping to the status vocabulary.

The central invariant: a TIMEOUT, ERROR, or INCONCLUSIVE raw result is NEVER
classified as PASS.
"""

from __future__ import annotations

from formal_run_orchestrator.classifier import RawResult, classify
from formal_run_orchestrator.models import RunStatus


def _raw(**kw):
    base = {
        "return_code": 0,
        "wall_time_s": 1.0,
        "timeout_s": 100.0,
        "reached_conclusion": True,
        "conclusion_holds": True,
        "tool_reported_error": False,
    }
    base.update(kw)
    return RawResult(**base)


def test_pass_requires_clean_conclusion_and_return_code():
    assert classify(_raw()) is RunStatus.PASS
    # nonzero return code with a holding conclusion is downgraded to ERROR, not PASS
    assert classify(_raw(return_code=5)) is RunStatus.ERROR


def test_fail_on_counterexample():
    assert classify(_raw(conclusion_holds=False)) is RunStatus.FAIL


def test_timeout_never_pass():
    r = _raw(reached_conclusion=False, conclusion_holds=None, wall_time_s=100.0, timeout_s=100.0)
    assert classify(r) is RunStatus.TIMEOUT
    assert classify(r) is not RunStatus.PASS


def test_error_never_pass():
    r = _raw(tool_reported_error=True, return_code=1)
    assert classify(r) is RunStatus.ERROR
    assert classify(r) is not RunStatus.PASS


def test_inconclusive_never_pass():
    # ran, under budget, but no conclusion (e.g. BMC exhausted a shallow bound)
    r = _raw(reached_conclusion=False, conclusion_holds=None, wall_time_s=5.0, timeout_s=100.0)
    assert classify(r) is RunStatus.INCONCLUSIVE
    assert classify(r) is not RunStatus.PASS


def test_error_return_code_without_conclusion_is_error():
    r = _raw(return_code=1, reached_conclusion=False, conclusion_holds=None, wall_time_s=5.0)
    assert classify(r) is RunStatus.ERROR
