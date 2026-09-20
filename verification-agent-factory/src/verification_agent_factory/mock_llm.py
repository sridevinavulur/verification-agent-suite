"""Deterministic mock LLM adapter.

The BUILD_STANDARD mandates a deterministic mock adapter so tests and CI never
make network calls. The factory itself does not call an LLM; this adapter is
what the *generated* agents use by default, and it is exercised by
``run-mock-demo``.

Determinism: the same prompt + seed always yields the same completion.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str
    seed: int
    prompt_sha256: str


class MockLlmAdapter:
    """A deterministic, offline stand-in for a real LLM provider."""

    model_name = "mock-llm-deterministic-v1"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def complete(self, prompt: str) -> LlmResponse:
        """Return a deterministic pseudo-completion for ``prompt``.

        The output is derived from a hash of (seed, prompt) so it is stable and
        reproducible, and it is clearly labelled as a mock so no caller can
        mistake it for a real model response.
        """
        digest = hashlib.sha256(f"{self.seed}:{prompt}".encode()).hexdigest()
        text = (
            "[MOCK-LLM] deterministic proposal "
            f"(seed={self.seed}, token={digest[:12]}). "
            "This is a placeholder hypothesis that MUST be validated by "
            "deterministic tools before use."
        )
        return LlmResponse(
            text=text,
            model=self.model_name,
            seed=self.seed,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        )
