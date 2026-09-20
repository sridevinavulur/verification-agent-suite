"""Optional contextual-bandit policy (LinUCB, pure Python, no numpy).

This is an OPTIONAL, clearly-labeled heuristic learner. It is trained OFFLINE on the
TRAIN split only (see split.py) and evaluated on the held-out TEST split, so there is
no train/test leakage. The bandit chooses only from the approved catalog.

Implementation: disjoint LinUCB. Each arm (catalog config) keeps a ridge-regression
model A (d x d) and b (d) over a small feature vector. Score = mean + alpha * ucb.
Everything is deterministic given the training order and the ties-broken-by-index rule.

We keep the linear algebra in plain lists so the repo needs no numpy and tests run
without a compiler (per BUILD_STANDARD).
"""

from __future__ import annotations

from ..catalog import config_ids
from ..models import BenchmarkItem, PropertyKind
from .base import Policy, PolicyChoice


def _features(item: BenchmarkItem) -> list[float]:
    """Small, normalized, public feature vector. Order is stable."""
    return [
        1.0,  # bias
        min(item.rtl_lines / 1000.0, 5.0),
        min(item.register_count / 500.0, 5.0),
        min(item.coi_size / 500.0, 5.0),
        min(item.max_depth_hint / 200.0, 5.0),
        item.intrinsic_difficulty,
        1.0 if item.is_holds else 0.0,
        1.0 if item.property.kind is PropertyKind.COVER else 0.0,
    ]


FEATURE_GROUPS: dict[str, list[int]] = {
    "bias": [0],
    "size": [1, 2, 3],
    "depth": [4],
    "difficulty": [5],
    "property_type": [6, 7],
}


# --- tiny linear-algebra helpers (dense, small d) --- #
def _identity(d: int, scale: float) -> list[list[float]]:
    return [[scale if i == j else 0.0 for j in range(d)] for i in range(d)]


def _matvec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(m[i][j] * v[j] for j in range(len(v))) for i in range(len(m))]


def _outer_add(m: list[list[float]], v: list[float]) -> None:
    for i in range(len(v)):
        row = m[i]
        vi = v[i]
        for j in range(len(v)):
            row[j] += vi * v[j]


def _invert(m: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse of a small SPD matrix (ridge-regularized => invertible)."""
    n = len(m)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        # Pivot (deterministic: partial pivot by magnitude, first-index tie-break).
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            a[pivot][col] += 1e-9  # nudge; ridge should prevent this
        a[col], a[pivot] = a[pivot], a[col]
        piv = a[col][col]
        a[col] = [x / piv for x in a[col]]
        for r in range(n):
            if r != col:
                factor = a[r][col]
                if factor != 0.0:
                    a[r] = [a[r][k] - factor * a[col][k] for k in range(2 * n)]
    return [row[n:] for row in a]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class LinUCBBanditPolicy(Policy):
    """Disjoint LinUCB contextual bandit over catalog configs."""

    name = "bandit_linucb"

    def __init__(
        self,
        alpha: float = 0.5,
        ridge: float = 1.0,
        feature_mask: set[int] | None = None,
    ) -> None:
        self.alpha = alpha
        self.ridge = ridge
        self.arms = config_ids()
        self._d = len(_features(_DUMMY_ITEM))
        # mask lets ablations disable feature groups (indices kept, values zeroed).
        self.feature_mask = feature_mask
        self.A = {a: _identity(self._d, ridge) for a in self.arms}
        self.b = {a: [0.0] * self._d for a in self.arms}
        self._trained = False

    def _x(self, item: BenchmarkItem) -> list[float]:
        x = _features(item)
        if self.feature_mask is not None:
            x = [v if i in self.feature_mask else 0.0 for i, v in enumerate(x)]
        return x

    def train(self, feedback: list[tuple[BenchmarkItem, str, float]]) -> None:
        """Offline update from (item, chosen_config, reward) drawn from TRAIN only."""
        for item, config_id, r in feedback:
            if config_id not in self.A:
                continue  # ignore feedback for out-of-catalog configs
            x = self._x(item)
            _outer_add(self.A[config_id], x)
            self.b[config_id] = [
                bi + r * xi for bi, xi in zip(self.b[config_id], x, strict=True)
            ]
        self._trained = True

    def choose(self, item: BenchmarkItem, seed: int) -> PolicyChoice:
        x = self._x(item)
        best_arm = self.arms[0]
        best_score = float("-inf")
        for arm in self.arms:
            a_inv = _invert(self.A[arm])
            theta = _matvec(a_inv, self.b[arm])
            mean = _dot(theta, x)
            ucb = self.alpha * (_dot(x, _matvec(a_inv, x)) ** 0.5)
            score = mean + ucb
            if score > best_score:
                best_score = score
                best_arm = arm
        trained = "trained" if self._trained else "untrained (prior)"
        return PolicyChoice(
            config_id=best_arm,
            rationale=(
                f"contextual-bandit LinUCB ({trained}, heuristic): "
                f"selected '{best_arm}' with score {best_score:.3f}"
            ),
        )


# A minimal item used only to size the feature vector at construction time.
from ..models import PropertySpec  # noqa: E402

_DUMMY_ITEM = BenchmarkItem(
    benchmark_id="_dummy",
    design_name="_dummy",
    design_sha="0" * 8,
    property=PropertySpec(property_id="p", kind=PropertyKind.ASSERT),
    property_sha="0" * 8,
    group="_dummy",
    rtl_lines=0,
    register_count=0,
    coi_size=0,
    max_depth_hint=1,
    intrinsic_difficulty=0.0,
    is_holds=True,
)
