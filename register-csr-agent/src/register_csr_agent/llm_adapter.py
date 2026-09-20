"""Deterministic mock LLM adapter.

The LLM's ONLY authority is to attach human-readable *explanations* to
discrepancies that the deterministic layer already produced. It cannot:
* change a discrepancy's ``code`` or ``severity``,
* create a discrepancy,
* invent an access type or a signal mapping.

This mock produces stable, offline text so tests and CI never touch the network.
A real adapter would swap ``explain`` for a constrained API call but keep the
same contract (input = existing Discrepancy, output = prose only).
"""

from __future__ import annotations

from .models import Discrepancy

_TEMPLATES: dict[str, str] = {
    "ADDR_OVERLAP": "Two registers claim overlapping byte ranges; decoding is ambiguous.",
    "ADDR_DUP": "Two registers share one address; a read/write cannot target both.",
    "ADDR_MISALIGN": "The base address is not a multiple of the register size.",
    "FIELD_OOB": "A field's MSB exceeds the register width, so bits fall off the register.",
    "FIELD_OVERLAP": "Two fields claim the same bit(s); the stored value is ill-defined.",
    "FIELD_GAP": "Some bits are undeclared and should be treated as reserved (read 0).",
    "RESET_OOB": "The reset value has more bits than the register can hold.",
    "RESET_FIELD_SUM": "Per-field reset values do not compose to the register reset value.",
    "ACCESS_RESERVED_RESET": "A reserved field must power up as 0 but declares a nonzero reset.",
    "ACCESS_CONFLICT": "Register-level access disagrees with its fields' access types.",
    "IRQ_STATUS_ACCESS": "A status/interrupt bit uses plain RW; software could spuriously set it.",
    "SIDE_EFFECT_UNREVIEWED": "This field triggers a side effect that needs a directed test.",
    "PRIV_ACCESS_DECLARED": "A privilege restriction is declared; denial paths need checking.",
    "RTL_WIDTH_MISMATCH": "Manifest and RTL disagree on the register width.",
    "RTL_RESET_MISMATCH": "Manifest and RTL disagree on the reset value.",
    "RTL_ACCESS_MISMATCH": "Manifest and RTL disagree on the access type.",
    "RTL_UNMAPPED": "No RTL symbol matched this name; grounding is incomplete.",
}


class MockLLM:
    name = "mock-explainer-0.1"

    def explain(self, disc: Discrepancy) -> str:
        return _TEMPLATES.get(disc.code, "Review this finding; no canned explanation available.")


def annotate_discrepancies(
    discrepancies: list[Discrepancy], llm: MockLLM | None = None
) -> list[Discrepancy]:
    """Attach explanations WITHOUT altering codes/severities/messages."""
    llm = llm or MockLLM()
    for d in discrepancies:
        d.explanation = llm.explain(d)
    return discrepancies
