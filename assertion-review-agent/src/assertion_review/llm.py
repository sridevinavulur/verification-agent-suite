"""Optional LLM explanation layer (behind a mock adapter).

AUTHORITY BOUNDARY: the LLM layer may only attach a plain-language
``explanation`` to a finding that a deterministic check already produced. It
must never create, delete, reclassify, or change the severity of a finding.
The default adapter is a deterministic mock so tests and CI never touch a
network or an API key (per BUILD_STANDARD).
"""

from __future__ import annotations

from typing import Protocol

from .models import CheckId, Finding, ReviewReport


class LLMAdapter(Protocol):
    def explain(self, finding: Finding) -> str: ...


_TEMPLATES: dict[CheckId, str] = {
    CheckId.MISSING_DISABLE_IFF: (
        "Without a reset guard the assertion is evaluated during reset, where signals are "
        "often X/undefined, producing spurious failures or masking real ones."
    ),
    CheckId.RESET_POLARITY_RISK: (
        "Reset polarity errors silently disable the check exactly when it should be inactive "
        "(and enable it during reset), which is a classic source of false confidence."
    ),
    CheckId.IMPLICATION_STYLE_RISK: (
        "'|->' checks the consequent in the same cycle as the antecedent; '|=>' checks it the "
        "next cycle. Picking the wrong one is an off-by-one in the temporal contract."
    ),
    CheckId.UNBOUNDED_TEMPORAL: (
        "Unbounded temporal operators make the property expensive or impossible to bound-prove "
        "and frequently express a stronger claim than intended."
    ),
    CheckId.WEAK_CONSEQUENT: (
        "A weak or constant consequent means the implication holds regardless of design "
        "behaviour, so the assertion provides little verification value."
    ),
    CheckId.ANTECEDENT_IN_CONSEQUENT: (
        "Repeating the antecedent inside the consequent is redundant and often signals a "
        "copy/paste error where the real expected behaviour was never written."
    ),
    CheckId.TRIVIALLY_PASSING: (
        "The property cannot fail as written, so a green result is meaningless."
    ),
    CheckId.ASSUME_CONSTRAINS_OUTPUT: (
        "Assuming a design output or internal state constrains the proof unsoundly and can hide "
        "the very bugs verification is meant to find."
    ),
    CheckId.UNDECLARED_SIGNAL: (
        "An identifier not present in the RTL manifest is either a typo or an ungrounded name; "
        "either way the property will not mean what the author expects."
    ),
    CheckId.WIDTH_MISMATCH: (
        "Comparing a signal against a differently-sized literal can truncate or zero-extend "
        "silently, changing the comparison semantics."
    ),
    CheckId.NAME_SEMANTICS: (
        "A name that does not describe intent makes review, triage, and regression debugging "
        "harder."
    ),
    CheckId.MISSING_CLOCK: (
        "A concurrent assertion needs a sampling clock; relying on an implicit default clocking "
        "block is fragile and non-portable."
    ),
    CheckId.REQ_TRACEABILITY: (
        "Untraced properties cannot be tied back to a requirement, weakening the verification "
        "audit trail."
    ),
    CheckId.VACUITY_RISK: (
        "This is a heuristic structural risk, NOT a vacuity proof. Confirm antecedent "
        "reachability with a cover property or formal reachability analysis."
    ),
}


class MockLLMAdapter:
    """Deterministic, offline explanation generator."""

    def explain(self, finding: Finding) -> str:
        base = _TEMPLATES.get(finding.check_id, "See recommendation.")
        return base


def annotate_report(report: ReviewReport, adapter: LLMAdapter | None = None) -> ReviewReport:
    """Return a copy of ``report`` with LLM explanations attached to findings.

    The deterministic findings are otherwise untouched.
    """
    adapter = adapter or MockLLMAdapter()
    new_findings = [
        f.model_copy(update={"explanation": adapter.explain(f)}) for f in report.findings
    ]
    return report.model_copy(update={"findings": new_findings})
