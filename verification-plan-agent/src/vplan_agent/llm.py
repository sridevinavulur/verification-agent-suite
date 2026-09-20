"""Deterministic mock LLM adapter.

The pack and BUILD_STANDARD require a **mock LLM only** - no network calls. In
this agent the LLM has a strictly advisory role: it proposes short natural
-language *rationale phrasing* for assertion candidates. All structural
decisions (categories, techniques, risk, traceability) are made by the
deterministic engine, not the LLM.

The mock is a pure function of its input (a hash-seeded template pick) so runs
are reproducible and golden tests are stable.
"""

from __future__ import annotations

import hashlib
from typing import Protocol


class LLMAdapter(Protocol):
    def rationale_for_assertion(self, feature_name: str, sva_sketch: str) -> str: ...


_TEMPLATES = [
    "Guards the intended behavior of {feature}; derived from the interface handshake.",
    "Encodes the safety invariant implied by {feature}; check under reset de-assertion.",
    "Captures the liveness expectation for {feature}; refine bounds during review.",
    "Sketch for {feature}; a reviewer must confirm the temporal window and signals.",
]


class MockLLM:
    """Deterministic, offline mock. Never contacts a network."""

    name = "mock"

    def rationale_for_assertion(self, feature_name: str, sva_sketch: str) -> str:
        key = f"{feature_name}|{sva_sketch}".encode()
        idx = int.from_bytes(hashlib.sha256(key).digest()[:2], "big") % len(_TEMPLATES)
        return _TEMPLATES[idx].format(feature=feature_name)


def get_adapter(name: str = "mock") -> LLMAdapter:
    if name != "mock":
        raise ValueError(
            f"Unknown LLM adapter {name!r}. Only the offline 'mock' adapter is supported."
        )
    return MockLLM()
