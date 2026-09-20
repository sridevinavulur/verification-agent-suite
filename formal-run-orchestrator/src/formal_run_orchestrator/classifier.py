"""Result classifier.

Maps a backend's raw signals (return code, whether a conclusion was reached, timing
vs budget) onto the fixed ``RunStatus`` vocabulary. This is the single sanctioned
place where a status is decided, and it *never* classifies a timeout, error, or
inconclusive run as PASS.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RunStatus


@dataclass(frozen=True)
class RawResult:
    """The primitive signals a backend (real or mock) hands to the classifier."""

    return_code: int
    wall_time_s: float
    timeout_s: float
    reached_conclusion: bool
    conclusion_holds: bool | None  # True=proven, False=counterexample, None=no conclusion
    tool_reported_error: bool


def classify(raw: RawResult) -> RunStatus:
    """Deterministically classify a raw backend result.

    Precedence (safety-first):
    1. Tool error / nonzero-but-not-timeout return code -> ERROR.
    2. Wall time at/over budget without a conclusion    -> TIMEOUT.
    3. Conclusion reached and holds                     -> PASS.
    4. Conclusion reached and refuted (counterexample)  -> FAIL.
    5. Anything else (ran, no conclusion)               -> INCONCLUSIVE.

    A TIMEOUT/ERROR/INCONCLUSIVE outcome can never fall through to PASS.
    """
    # 1. Explicit tool error.
    if raw.tool_reported_error:
        return RunStatus.ERROR

    # 2. Timeout: reached/exceeded budget with no conclusion.
    if not raw.reached_conclusion and raw.wall_time_s >= raw.timeout_s:
        return RunStatus.TIMEOUT

    # An error return code that is not a clean timeout is an ERROR, not a pass.
    if raw.return_code != 0 and not (raw.reached_conclusion and raw.conclusion_holds is not None):
        return RunStatus.ERROR

    # 3/4. Conclusive verdicts.
    if raw.reached_conclusion and raw.conclusion_holds is True:
        # PASS additionally requires a clean return code (defense in depth).
        return RunStatus.PASS if raw.return_code == 0 else RunStatus.ERROR
    if raw.reached_conclusion and raw.conclusion_holds is False:
        return RunStatus.FAIL

    # 5. Ran, produced nothing conclusive, did not time out.
    return RunStatus.INCONCLUSIVE
