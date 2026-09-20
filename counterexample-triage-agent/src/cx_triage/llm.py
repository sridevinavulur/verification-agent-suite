"""LLM narrative adapter.

The deterministic evidence extraction is authoritative. The LLM narrative is an
optional, clearly-labeled prose summary. The default adapter is a *mock* that
does no network I/O -- it deterministically templatizes the already-extracted
evidence. This keeps tests and CI fully offline (per BUILD_STANDARD.md).

A real provider adapter can be added later behind the same ``LLMAdapter``
protocol; it must never be the source of any evidence field.
"""

from __future__ import annotations

from typing import Protocol

from .models import TriageReport


class LLMAdapter(Protocol):
    def narrate(self, report: TriageReport) -> str: ...


class MockLLMAdapter:
    """Deterministic, offline narrative generator.

    It only rephrases evidence already present in the report. It explicitly
    hedges and never upgrades a hypothesis to a conclusion.
    """

    name = "mock-llm-v1"

    def narrate(self, report: TriageReport) -> str:
        top = report.top_hypothesis()
        lines: list[str] = []
        lines.append(
            f"Property '{report.property_name}' produced a counterexample "
            f"(defined at {report.property_location.file}:"
            f"{report.property_location.line})."
        )
        if report.antecedent_cycle is not None:
            lines.append(
                f"The antecedent first activated at cycle "
                f"{report.antecedent_cycle}."
            )
        if report.first_divergence_cycle is not None:
            lines.append(
                f"The first divergence from expected behavior is at cycle "
                f"{report.first_divergence_cycle}."
            )
        if top is not None:
            lines.append(
                f"The highest-ranked hypothesis is '{top.category.value}' "
                f"(confidence {top.confidence:.2f}), but alternatives are retained "
                f"and should be ruled out before concluding a root cause."
            )
        lines.append(
            "This narrative is advisory only and is derived from the deterministic "
            "evidence above; it is not itself evidence and does not establish a "
            "design bug."
        )
        return " ".join(lines)


def get_adapter(name: str = "mock") -> LLMAdapter:
    if name == "mock":
        return MockLLMAdapter()
    raise ValueError(
        f"Unknown LLM adapter '{name}'. Only the offline 'mock' adapter is "
        f"bundled; real providers must be added explicitly and are never enabled "
        f"in CI."
    )
