"""Policy interface.

A policy maps a benchmark item (plus its observable features) to a *catalog*
config_id and a human-readable rationale. Policies are heuristic; the formal tool
result remains authoritative. Policies choose ONLY from the approved catalog.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import BenchmarkItem


@dataclass(frozen=True)
class PolicyChoice:
    config_id: str
    rationale: str


class Policy(ABC):
    """Base class for configuration-selection policies."""

    name: str = "base"

    @abstractmethod
    def choose(self, item: BenchmarkItem, seed: int) -> PolicyChoice:
        """Return a catalog config_id and rationale for this item."""

    def train(self, feedback: list[tuple[BenchmarkItem, str, float]]) -> None:  # noqa: B027
        """Optional offline training hook.

        ``feedback`` is a list of (item, chosen_config_id, reward) tuples drawn from
        the TRAIN split only. Non-learning policies ignore it. Default: no-op.
        """
        return None
