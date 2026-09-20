"""Review-quality scoring rubric.

The score answers "how clean is this SVA file per the deterministic reviewer?"
It is a *review-quality* signal, not a correctness proof. Weighted penalties:

    ERROR   -> 10 points
    WARNING ->  4 points
    INFO    ->  1 point

score = 100 * (1 - penalty / max_penalty), where max_penalty scales with the
number of properties so a large file is not unfairly capped. See
``docs/SCORING_RUBRIC.md`` for the full rubric and grade bands.
"""

from __future__ import annotations

from .models import ReviewReport, ReviewScore, Severity

WEIGHTS = {Severity.ERROR: 10, Severity.WARNING: 4, Severity.INFO: 1}
# Per-property notional budget of penalty points before the score hits zero.
PER_PROPERTY_BUDGET = 20


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def score_report(report: ReviewReport) -> ReviewScore:
    counts = report.counts()
    err = counts[Severity.ERROR.value]
    warn = counts[Severity.WARNING.value]
    info = counts[Severity.INFO.value]

    penalty = err * WEIGHTS[Severity.ERROR] + warn * WEIGHTS[Severity.WARNING] + info

    props = max(report.property_count, 1)
    max_penalty = props * PER_PROPERTY_BUDGET
    ratio = min(penalty / max_penalty, 1.0)
    score = round(100.0 * (1.0 - ratio), 1)

    return ReviewScore(
        error_count=err,
        warning_count=warn,
        info_count=info,
        penalty=penalty,
        max_penalty=max_penalty,
        score=score,
        grade=_grade(score),
    )
