"""Leakage-free benchmark splitting.

Correlated designs (variants of the same design, e.g. a FIFO at several widths)
share a ``group`` label. Splitting is done at the GROUP level, never the item level,
so no design family straddles train and test. This prevents the most common form of
benchmark leakage in solver-tuning experiments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .models import BenchmarkItem, BenchmarkSuite


@dataclass(frozen=True)
class Split:
    train: list[BenchmarkItem]
    test: list[BenchmarkItem]
    train_groups: list[str]
    test_groups: list[str]


def _group_bucket(group: str, salt: str, buckets: int) -> int:
    h = hashlib.sha256(f"{salt}:{group}".encode()).hexdigest()
    return int(h[:16], 16) % buckets


def group_holdout_split(
    suite: BenchmarkSuite, test_fraction: float = 0.4, salt: str = "frv-holdout-b"
) -> Split:
    """Deterministic group-level holdout split.

    Groups are hashed into 100 buckets; the lowest ``test_fraction`` of buckets go to
    TEST. Because the assignment is by group hash, adding items to an existing group
    never moves that group across the split boundary.
    """
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be in (0, 1)")

    groups = sorted({i.group for i in suite.items})
    threshold = int(round(test_fraction * 100))
    test_groups = {g for g in groups if _group_bucket(g, salt, 100) < threshold}
    # Guard against degenerate all-train/all-test on tiny suites.
    if not test_groups and groups:
        test_groups = {groups[0]}
    if len(test_groups) == len(groups) and len(groups) > 1:
        test_groups.discard(sorted(test_groups)[-1])

    train = [i for i in suite.items if i.group not in test_groups]
    test = [i for i in suite.items if i.group in test_groups]
    return Split(
        train=train,
        test=test,
        train_groups=sorted({i.group for i in train}),
        test_groups=sorted(test_groups),
    )
