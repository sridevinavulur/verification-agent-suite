"""Deterministic, offline mock-LLM adapter.

Per BUILD_STANDARD.md: the LLM layer *proposes narrative/hypotheses*; the
deterministic engine (:mod:`eq_triage.triage`) is the sole authority for
verdicts. This adapter makes NO network calls -- it produces a fixed, templated
advisory narrative from the already-computed :class:`TriageReport` so that
tests and CI are hermetic.
"""

from __future__ import annotations

from .models import TriageReport


class MockLLMAdapter:
    """Templated narrator. Deterministic; never invents evidence."""

    name = "mock"

    def narrate(self, report: TriageReport) -> str:
        lines: list[str] = []
        lines.append(
            f"The equivalence tool reported status "
            f"'{report.reported_status.value}' comparing "
            f"'{report.reference_design}' against '{report.revised_design}'."
        )
        if report.has_config_differences:
            lines.append(
                "NOTE: configuration/constraint differences were detected and "
                "are listed in the report; reconcile these before concluding "
                "anything about the RTL."
            )
        if report.groups:
            top = report.groups[0]
            cause = top.likely_causes[0] if top.likely_causes else None
            if cause:
                lines.append(
                    f"The largest mismatch group ({top.count} compare point(s)) "
                    f"most likely stems from a '{cause.category.value}' issue "
                    f"(heuristic confidence {cause.confidence:.0%}). "
                    "This is a hypothesis, not a proof."
                )
        else:
            lines.append("No mismatches were reported to localize.")
        lines.append(
            "All conclusions above are advisory. Confirm with the ranked "
            "source locations and the reproducible debug packet."
        )
        return " ".join(lines)


def get_adapter(name: str = "mock") -> MockLLMAdapter:
    if name != "mock":
        raise ValueError(
            f"Only the offline 'mock' adapter is available (got {name!r})."
        )
    return MockLLMAdapter()
