"""Advisory ranking composition (CRAVS-style multi-hypothesis pattern).

The deterministic hypothesis ranking produced by :class:`~cx_triage.triage.TriageEngine`
is **authoritative** and is never re-ordered or overwritten by this module. What
this module adds is the reference project's *multi-hypothesis debug* pattern as a
composition step:

    try a structured/advisory analysis; fall back to the deterministic result.

Reference (READ-ONLY, not imported):
``spec-to-cov-agent/veri_forge/cravs/integration.py`` -- CRAVS runs a structured
multi-agent analysis and, when the structured engine is unavailable, falls back
to an LLM-only path. We adopt the *shape* of that pattern (structured-or-fallback)
but invert the authority: here the deterministic layer is the trusted engine and
any structured/LLM/real-repro input is strictly **advisory** -- it may annotate a
hypothesis with an advisory confidence *hint* and a note, but:

* it never changes the ranking order (that stays confidence-sorted, authoritative);
* it never adds or removes a hypothesis;
* it never adds evidence to a ``design_bug`` (or any) hypothesis;
* a non-conclusive reproduction (skip/timeout/error) is ignored for hinting.

This keeps BUILD_STANDARD.md's authority boundary intact: LLM/external paths
propose, deterministic tools decide.
"""

from __future__ import annotations

from dataclasses import dataclass

from .executor import ReproResult, ReproStatus
from .models import HypothesisCategory, ReproAttempt, TriageReport


@dataclass
class AdvisoryHint:
    """A non-authoritative note attached during composition (display-only)."""

    source: str
    text: str
    confidence_hint: float | None = None


def repro_result_to_attempt(result: ReproResult) -> ReproAttempt:
    """Project an executor :class:`ReproResult` onto the report's model field."""
    return ReproAttempt(
        status=result.status.value,
        adapter=result.adapter,
        summary=result.summary,
        exit_code=result.exit_code,
        duration_s=round(result.duration_s, 3),
        notes=list(result.notes),
    )


def compose_report(
    report: TriageReport,
    *,
    repro: ReproResult | None = None,
) -> TriageReport:
    """Attach advisory reproduction context to a *finished* deterministic report.

    Mutates and returns ``report`` in place. The hypothesis ranking is untouched;
    only an advisory ``reproduction_attempt`` record and (optionally) advisory
    unresolved-question notes are added.
    """
    if repro is None:
        return report

    report.reproduction_attempt = repro_result_to_attempt(repro)

    # CRAVS-style: only a *conclusive* structured outcome informs anything, and
    # even then only as an advisory note -- never as evidence or a re-ranking.
    if repro.status == ReproStatus.NOT_REPRODUCED:
        # The DUT re-ran and did NOT exhibit the failure. This does NOT clear a
        # design bug (the captured counterexample still stands) but it is a strong
        # signal that the counterexample may be environment/stimulus specific.
        report.unresolved_questions.append(
            "Real re-run did NOT reproduce the failure "
            f"({repro.adapter}); confirm whether the counterexample depends on "
            "specific stimulus/environment before concluding a design bug. "
            "(Advisory only; does not override the deterministic ranking.)"
        )
    elif repro.status == ReproStatus.REPRODUCED and repro.adapter != "deterministic-v1":
        report.unresolved_questions.append(
            f"Real re-run reproduced the failure ({repro.adapter}). "
            "This corroborates the captured counterexample but is advisory context, "
            "not additional evidence for any single hypothesis."
        )
    elif repro.status in (
        ReproStatus.SKIPPED,
        ReproStatus.TIMEOUT,
        ReproStatus.ERROR,
    ):
        # Never a pass; surface transparently and move on.
        report.unresolved_questions.append(
            f"Real reproduction was inconclusive (status={repro.status.value}, "
            f"{repro.adapter}); triage relies on the deterministic analysis only."
        )
    return report


def advisory_hints_for(
    report: TriageReport,
    repro: ReproResult | None,
) -> list[AdvisoryHint]:
    """Compute display-only hints (used by callers/UI; never mutates ranking).

    Returned hints are informational. They deliberately do not touch
    ``report.hypotheses``; a caller may render them beside the authoritative
    ranking, clearly labeled advisory.
    """
    hints: list[AdvisoryHint] = []
    if repro is not None and repro.status == ReproStatus.NOT_REPRODUCED:
        top = report.top_hypothesis()
        if top is not None and top.category == HypothesisCategory.DESIGN_BUG:
            hints.append(
                AdvisoryHint(
                    source=repro.adapter,
                    text=(
                        "Real re-run did not reproduce the failure; treat the "
                        "top design_bug hypothesis with extra caution."
                    ),
                    confidence_hint=max(0.0, top.confidence - 0.1),
                )
            )
    return hints
