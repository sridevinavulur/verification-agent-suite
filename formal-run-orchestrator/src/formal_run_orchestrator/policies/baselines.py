"""Baseline and heuristic policies.

  * FixedPolicy      - always the same catalog config (deterministic baseline).
  * RandomPolicy     - seeded uniform choice from the catalog (control baseline).
  * RuleBasedPolicy  - transparent hand-written heuristic over item features.

All are deterministic given their seed, so offline comparisons are reproducible.
"""

from __future__ import annotations

import hashlib

from ..catalog import config_ids, is_valid_config
from ..models import BenchmarkItem, PropertyKind
from .base import Policy, PolicyChoice

DEFAULT_FIXED_CONFIG = "bmc_mid"


def _seeded_index(n: int, *parts: str) -> int:
    h = hashlib.sha256("::".join(parts).encode()).hexdigest()
    return int(h[:16], 16) % n


class FixedPolicy(Policy):
    """Always pick one fixed catalog config. The deterministic baseline."""

    name = "fixed"

    def __init__(self, config_id: str = DEFAULT_FIXED_CONFIG) -> None:
        if not is_valid_config(config_id):
            raise ValueError(f"fixed policy config '{config_id}' not in catalog")
        self.config_id = config_id

    def choose(self, item: BenchmarkItem, seed: int) -> PolicyChoice:
        return PolicyChoice(
            config_id=self.config_id,
            rationale=f"fixed-policy baseline: always use '{self.config_id}'",
        )


class RandomPolicy(Policy):
    """Seeded uniform-random choice from the catalog. Control baseline."""

    name = "random"

    def choose(self, item: BenchmarkItem, seed: int) -> PolicyChoice:
        ids = config_ids()
        idx = _seeded_index(len(ids), item.benchmark_id, str(seed))
        cid = ids[idx]
        return PolicyChoice(
            config_id=cid,
            rationale=f"random baseline: seeded uniform pick -> '{cid}'",
        )


class RuleBasedPolicy(Policy):
    """Transparent rule-based heuristic (explicitly labeled heuristic, not sound).

    Rules encode common formal folklore:
      * Properties expected to HOLD favor unbounded/inductive engines (PDR / k-induction).
      * Properties expected to FAIL (or cover objectives) favor BMC to a depth that
        covers the resolving bound, since a shallow counterexample is fast.
      * Larger COI / difficulty escalates the timeout+memory tier.
      * Deep resolving bounds force a deep-BMC or unbounded engine.
    """

    name = "rule_based"

    def choose(self, item: BenchmarkItem, seed: int) -> PolicyChoice:
        reasons: list[str] = []

        big = item.coi_size >= 200 or item.intrinsic_difficulty >= 0.5
        deep = item.max_depth_hint > 60

        if item.property.kind is PropertyKind.COVER or not item.is_holds:
            # Want a (possibly shallow) counterexample: BMC is well suited.
            if deep:
                cid = "bmc_deep"
                reasons.append("expects a counterexample at deep bound -> deep BMC")
            elif big:
                cid = "bmc_mid"
                reasons.append("expects a counterexample, medium size -> mid BMC")
            else:
                cid = "bmc_shallow"
                reasons.append("expects a shallow counterexample -> shallow BMC")
        else:
            # Property expected to hold: prefer inductive/unbounded engines.
            if big and deep:
                cid = "pdr_big"
                reasons.append("holding property, large+deep -> PDR (large budget)")
            elif big:
                cid = "pdr_std"
                reasons.append("holding property, large COI -> PDR")
            elif deep:
                cid = "kind_deep"
                reasons.append("holding property, deep bound -> deep k-induction")
            else:
                cid = "kind_mid"
                reasons.append("holding property, small -> mid k-induction")

        rationale = "rule-based (heuristic): " + "; ".join(reasons)
        return PolicyChoice(config_id=cid, rationale=rationale)
