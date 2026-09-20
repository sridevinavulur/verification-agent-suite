"""Executor adapters that classify mutants.

The adapter interface separates the deterministic *mutation* layer from the
*execution/classification* layer, matching the BUILD_STANDARD requirement that
tool results (not the mutator) decide detected/survived. A real adapter would
compile the mutated RTL + SVA and run a formal/simulation tool; here we ship a
deterministic MOCK adapter with no external simulator.

MOCK detection model (documented, heuristic):
  A mutant is DETECTED iff at least one property in the suite references a signal
  that the mutation touches (``mutant.mutated_signals``). The intuition: a
  property that never observes the mutated logic cannot possibly catch its
  defect, so such mutants SURVIVE. This is deliberately conservative and is
  *good enough to demonstrate real mutation scoring* on the toy benchmark, not a
  substitute for formal/simulation evidence.

Never classifies TIMEOUT / ERROR / INCONCLUSIVE as detected. A mutant whose
source is unchanged is INVALID and excluded from scoring.
"""

from __future__ import annotations

from typing import Protocol

from .models import Mutant, MutantResult, MutantStatus, PropertyRef


class ExecutorAdapter(Protocol):
    """Contract every executor adapter must satisfy."""

    name: str

    def classify(
        self, mutant: Mutant, original_source: str, properties: list[PropertyRef]
    ) -> MutantResult:  # pragma: no cover - Protocol signature
        ...


class MockExecutor:
    """Deterministic mock executor. No real simulator involved."""

    name = "mock"

    def classify(
        self, mutant: Mutant, original_source: str, properties: list[PropertyRef]
    ) -> MutantResult:
        # Invalid: mutation produced no source change.
        if mutant.mutated_source == original_source:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INVALID,
                detail="Mutant did not change the source (no-op mutation).",
                executor=self.name,
            )

        touched = set(mutant.mutated_signals)
        if not touched:
            # We cannot determine observability -> inconclusive (excluded from
            # score). Never a PASS/DETECTED without evidence.
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INCONCLUSIVE,
                detail="No mutated signals resolved; observability unknown.",
                executor=self.name,
            )

        detected_by = [
            p.name
            for p in properties
            if touched.intersection(p.referenced_signals)
        ]
        if detected_by:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.DETECTED,
                detected_by=sorted(detected_by),
                detail=(
                    "Property(ies) reference a mutated signal "
                    f"({', '.join(sorted(touched))})."
                ),
                executor=self.name,
            )

        return MutantResult(
            mutant_id=mutant.mutant_id,
            operator=mutant.operator,
            status=MutantStatus.SURVIVED,
            detail=(
                "No property references any mutated signal "
                f"({', '.join(sorted(touched))}); undetected mutation "
                "requiring investigation."
            ),
            executor=self.name,
        )


def get_executor(name: str) -> ExecutorAdapter:
    """Factory for configured executor adapters.

    ``mock`` (default) is the deterministic, simulator-free adapter. ``verilator``
    is the OPTIONAL real-simulator adapter that compiles and runs each mutant
    under Verilator; it degrades gracefully (reports ERROR, never a fake PASS)
    when the ``verilator`` binary is not installed.
    """
    if name == "mock":
        return MockExecutor()
    if name == "verilator":
        # Imported lazily so the default mock path never depends on the
        # (optional) real-simulator adapter or its module-load cost.
        from .verilator_executor import VerilatorExecutor

        return VerilatorExecutor()
    raise ValueError(
        f"Unknown executor '{name}'. Available: mock, verilator. "
        "Other simulator/formal adapters are a documented future phase."
    )
