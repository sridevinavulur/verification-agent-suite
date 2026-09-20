"""Provider-neutral LLM adapter.

The deterministic pipeline does NOT require an LLM. This module exists so an
optional LLM extractor could be plugged in later behind a stable interface. In
tests and CI only the :class:`MockLLMAdapter` is used -- it never touches the
network and returns canned, deterministic output.

Authority boundary: an LLM may *propose* hypotheses (e.g. alternative clause
splits). It may never resolve a symbol, choose a clock, or invent a bound --
that remains the job of the deterministic engines.
"""

from __future__ import annotations

from typing import Protocol


class LLMAdapter(Protocol):
    """Minimal interface an LLM extractor would implement."""

    provider: str
    model_name: str

    def propose(self, prompt: str) -> str:  # pragma: no cover - protocol
        ...


class MockLLMAdapter:
    """Deterministic, offline mock. Echoes a fixed marker.

    This is intentionally inert: it must never be able to smuggle a signal
    name or bound into the deterministic path.
    """

    provider = "mock"
    model_name = "mock-deterministic-0"

    def __init__(self, canned: dict[str, str] | None = None) -> None:
        self._canned = canned or {}

    def propose(self, prompt: str) -> str:
        return self._canned.get(prompt, "[mock-llm] no proposal (deterministic mode)")
