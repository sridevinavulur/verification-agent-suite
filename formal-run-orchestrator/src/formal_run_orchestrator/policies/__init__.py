"""Policy registry."""

from __future__ import annotations

from .bandit import LinUCBBanditPolicy
from .base import Policy, PolicyChoice
from .baselines import FixedPolicy, RandomPolicy, RuleBasedPolicy


def get_policy(name: str) -> Policy:
    """Construct a policy by name with default hyperparameters."""
    registry: dict[str, type[Policy]] = {
        "fixed": FixedPolicy,
        "random": RandomPolicy,
        "rule_based": RuleBasedPolicy,
        "bandit_linucb": LinUCBBanditPolicy,
    }
    if name not in registry:
        raise ValueError(
            f"unknown policy '{name}'. Available: {', '.join(sorted(registry))}"
        )
    return registry[name]()


def available_policies() -> list[str]:
    return ["fixed", "random", "rule_based", "bandit_linucb"]


__all__ = [
    "Policy",
    "PolicyChoice",
    "FixedPolicy",
    "RandomPolicy",
    "RuleBasedPolicy",
    "LinUCBBanditPolicy",
    "get_policy",
    "available_policies",
]
