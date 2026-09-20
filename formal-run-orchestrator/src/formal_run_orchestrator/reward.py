"""Reward design for offline policy evaluation.

The reward is the objective policies are compared against. By construction it:
  * rewards conclusive, within-budget results (PASS/FAIL both count as *solved*),
  * penalizes TIMEOUT,
  * penalizes ERROR and INCONCLUSIVE,
  * penalizes excess memory (relative to the config's cap tier),
  * heavily penalizes invalid/unsound configuration choices.

Note: "solved within budget" means the tool reached a *conclusion* (PASS or FAIL)
within its resource budget. A FAIL is a legitimate, useful outcome (a counterexample);
it is NOT a proof failure of the orchestrator. TIMEOUT/ERROR/INCONCLUSIVE are never
treated as solved.
"""

from __future__ import annotations

from .catalog import get_config, is_valid_config
from .models import RunRecord, RunStatus, ValidationStatus

# Weights (documented, tunable). Kept simple and transparent.
R_SOLVED = 1.0            # base reward for a conclusive within-budget result
W_TIME = 0.30            # penalty weight for wall-time fraction of budget used
W_MEM = 0.50             # penalty weight for memory over/near cap
P_TIMEOUT = 0.80         # penalty for a timeout
P_ERROR = 0.90           # penalty for a tool error
P_INCONCLUSIVE = 0.85    # penalty for an inconclusive run
P_INVALID_CONFIG = 2.0   # large penalty for choosing an out-of-catalog/invalid config


def reward(run: RunRecord) -> float:
    """Scalar reward for a single run record. Higher is better."""
    # Invalid/unsound configuration choices are penalized hardest.
    if run.validation_status is ValidationStatus.INVALID_CONFIG or not is_valid_config(
        run.config_id
    ):
        return -P_INVALID_CONFIG
    if run.validation_status is ValidationStatus.INCOMPLETE_PROVENANCE:
        return -P_INVALID_CONFIG

    cfg = get_config(run.config_id)

    if run.status in (RunStatus.PASS, RunStatus.FAIL):
        # Solved within budget. Subtract normalized time cost + memory pressure.
        time_frac = min(run.wall_time_s / max(cfg.timeout_s, 1), 1.0)
        mem_frac = run.peak_memory_mb / max(cfg.memory_cap_mb, 1)
        mem_penalty = W_MEM * max(0.0, mem_frac - 0.8)  # only penalize near/over cap
        return R_SOLVED - W_TIME * time_frac - mem_penalty

    if run.status is RunStatus.TIMEOUT:
        return -P_TIMEOUT
    if run.status is RunStatus.ERROR:
        return -P_ERROR
    if run.status is RunStatus.INCONCLUSIVE:
        return -P_INCONCLUSIVE

    return -P_ERROR  # pragma: no cover - exhaustive above
