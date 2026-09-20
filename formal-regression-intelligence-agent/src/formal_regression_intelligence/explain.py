"""LLM explanation layer (deterministic mock adapter).

Authority boundary: the LLM may ONLY narrate findings the deterministic engine
has already produced and substantiated. It must not invent findings, statuses,
root causes, or run IDs. To enforce that in a testable way, the default adapter
is a deterministic template-based ``MockLLM`` -- no network, no API key -- that
turns a :class:`Finding`'s own evidence into prose. Every explanation is tagged
as HEURISTIC and cites the exact member run IDs it was given.

A real provider adapter would implement the same ``explain(finding)`` contract
behind an environment-gated flag; it is intentionally NOT wired up here (spec:
"LLM only explains evidence-backed clusters (mock adapter)").
"""

from __future__ import annotations

from typing import Protocol

from .models import Finding, FindingKind


class LLMAdapter(Protocol):
    def explain(self, finding: Finding) -> str: ...


class MockLLM:
    """Deterministic, offline explanation generator.

    Same finding in -> same text out. It only consumes fields already present on
    the finding, so it cannot fabricate evidence. This is the CI/default adapter.
    """

    name = "mock-llm-0.1.0"

    _CAUSE_HINTS = {
        FindingKind.FAILURE_CLUSTER: (
            "candidates include a genuine design bug, an over-strong property, or a shared "
            "environment assumption -- all require human triage of a counterexample"
        ),
        FindingKind.TIMEOUT_CLUSTER: (
            "candidates include an under-provisioned timeout tier, a poor engine fit, or "
            "genuinely hard proof obligations -- none is confirmed here"
        ),
        FindingKind.DUPLICATE_JOBS: (
            "this is likely wasted compute, but repeated seeds may be intentional flakiness probes"
        ),
        FindingKind.RUNTIME_REGRESSION: (
            "candidates include a tool-version change, altered inputs, or host contention -- "
            "a bisect is needed to attribute it"
        ),
        FindingKind.MEMORY_REGRESSION: (
            "candidates include a larger cone-of-influence, deeper unrolling, or a leak "
            "-- unconfirmed"
        ),
        FindingKind.CONFIG_SENSITIVITY: (
            "the design is near a config's capability boundary; which config to trust is a "
            "human decision"
        ),
        FindingKind.REPRODUCIBILITY_WARNING: (
            "candidates include nondeterministic solver behavior, uninitialized state, or a "
            "race in the environment -- must be resolved before trusting any single run"
        ),
    }

    def explain(self, finding: Finding) -> str:
        cause = self._CAUSE_HINTS[finding.kind]
        n_runs = len(finding.member_run_ids)
        cites = ", ".join(finding.member_run_ids[:5])
        if n_runs > 5:
            cites += f", +{n_runs - 5} more"
        return (
            f"[{self.name}] HEURISTIC explanation of {finding.kind.value} "
            f"({finding.severity.value}). {finding.summary} "
            f"Possible (unconfirmed) explanations: {cause}. "
            f"Evidence: {n_runs} run(s) [{cites}]. "
            "This is a statistical/structural observation, not a proven root cause; "
            "correlation is not causation."
        )


def explain_findings(findings: list[Finding], adapter: LLMAdapter | None = None) -> dict[str, str]:
    """Return {finding_id: explanation} using the given adapter (mock by default)."""
    llm = adapter or MockLLM()
    return {f.finding_id: llm.explain(f) for f in findings}
