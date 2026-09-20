"""Offline policy evaluation harness.

Runs each policy over a benchmark suite using the MOCK executor and computes metrics
per split. For learning policies (the bandit) it:
  1. trains on the TRAIN split only (fit -> execute -> reward -> update),
  2. evaluates on the held-out TEST split.

Non-learning policies are simply evaluated on both splits. This is the offline,
leakage-free evaluation mode required by the spec. No ledger writes happen here; it
is a pure comparison utility (the CLI can persist results separately).
"""

from __future__ import annotations

import hashlib

from .executor import execute
from .metrics import compute_metrics
from .models import BenchmarkItem, PolicyMetrics, RunRecord
from .policies import Policy, get_policy
from .policies.bandit import LinUCBBanditPolicy
from .reward import reward
from .split import group_holdout_split


def _stable_seed(base_seed: int, benchmark_id: str) -> int:
    """Process-independent seed (avoid Python's salted ``hash`` for reproducibility)."""
    h = int(hashlib.sha256(benchmark_id.encode()).hexdigest()[:8], 16)
    return base_seed + h % 100000


def _run_items(policy: Policy, items: list[BenchmarkItem], base_seed: int) -> list[RunRecord]:
    records: list[RunRecord] = []
    for item in items:
        seed = _stable_seed(base_seed, item.benchmark_id)
        choice = policy.choose(item, seed)
        rec = execute(
            item,
            choice.config_id,
            seed,
            plan_id=f"eval-{policy.name}",
            run_id=f"eval-{policy.name}-{item.benchmark_id}",
            rationale=choice.rationale,
        )
        records.append(rec)
    return records


def evaluate_policy_on_split(
    policy_name: str,
    suite,
    *,
    test_fraction: float = 0.4,
    base_seed: int = 42,
) -> dict[str, PolicyMetrics]:
    """Return {'train': metrics, 'test': metrics} for one policy, leakage-free.

    A fresh policy instance is constructed here so repeated calls are independent.
    """
    split = group_holdout_split(suite, test_fraction=test_fraction)
    policy = get_policy(policy_name)

    # Learning policies train on TRAIN only, then are frozen for TEST.
    if isinstance(policy, LinUCBBanditPolicy):
        # Offline training pass over TRAIN: execute, observe reward, update.
        train_records = _run_items(policy, split.train, base_seed)
        feedback = [
            (item, rec.config_id, reward(rec))
            for item, rec in zip(split.train, train_records, strict=True)
        ]
        policy.train(feedback)
        # Re-evaluate TRAIN with the trained model for a fair train-metric.
        train_records = _run_items(policy, split.train, base_seed)
    else:
        train_records = _run_items(policy, split.train, base_seed)

    test_records = _run_items(policy, split.test, base_seed)

    return {
        "train": compute_metrics(train_records, policy_name, "train"),
        "test": compute_metrics(test_records, policy_name, "test"),
    }


def compare_policies(
    policy_names: list[str],
    suite,
    *,
    test_fraction: float = 0.4,
    base_seed: int = 42,
) -> dict[str, dict[str, PolicyMetrics]]:
    """Evaluate several policies on the same leakage-free split."""
    return {
        name: evaluate_policy_on_split(
            name, suite, test_fraction=test_fraction, base_seed=base_seed
        )
        for name in policy_names
    }


def ablation_feature_groups(
    suite,
    *,
    test_fraction: float = 0.4,
    base_seed: int = 42,
) -> dict[str, PolicyMetrics]:
    """Feature-group ablation for the bandit: TEST-split metrics with each group removed.

    Returns {'full': m, '-size': m, '-depth': m, ...}. Shows which feature groups
    actually move the metric (a defensible way to claim a feature "matters").
    """
    from .policies.bandit import FEATURE_GROUPS

    split = group_holdout_split(suite, test_fraction=test_fraction)
    # Full index set is the union of all feature-group indices.
    all_indices: set[int] = set()
    for idxs in FEATURE_GROUPS.values():
        all_indices.update(idxs)

    results: dict[str, PolicyMetrics] = {}

    def _run_with_mask(mask: set[int], label: str) -> None:
        policy = LinUCBBanditPolicy(feature_mask=mask)
        train_records = _run_items(policy, split.train, base_seed)
        policy.train(
            [
                (it, r.config_id, reward(r))
                for it, r in zip(split.train, train_records, strict=True)
            ]
        )
        test_records = _run_items(policy, split.test, base_seed)
        results[label] = compute_metrics(test_records, f"bandit_linucb[{label}]", "test")

    _run_with_mask(all_indices, "full")
    for group, idxs in FEATURE_GROUPS.items():
        if group == "bias":
            continue  # never ablate the bias term
        mask = all_indices - set(idxs)
        _run_with_mask(mask, f"-{group}")

    return results
