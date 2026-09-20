"""Markdown report rendering for summarize/compare."""

from __future__ import annotations

from .models import PolicyMetrics


def _fmt_ci(m: PolicyMetrics) -> str:
    if m.reward_ci95 is None:
        return "n/a (n<3)"
    lo, hi = m.reward_ci95
    return f"[{lo:.3f}, {hi:.3f}]"


def render_summary(m: PolicyMetrics) -> str:
    c = m.status_counts
    lines = [
        f"# Summary: policy `{m.policy_name}` (split: {m.split})",
        "",
        f"- Designs: {m.n_designs}",
        f"- Configuration attempts: {m.n_attempts}",
        f"- **Solved within budget:** {m.solved_within_budget_pct:.2f}% "
        f"(PASS+FAIL / attempts)",
        "",
        "## Status counts",
        "",
        "| PASS | FAIL | TIMEOUT | ERROR | INCONCLUSIVE |",
        "| ---: | ---: | ------: | ----: | -----------: |",
        f"| {c.PASS} | {c.FAIL} | {c.TIMEOUT} | {c.ERROR} | {c.INCONCLUSIVE} |",
        "",
        "## Resources",
        "",
        f"- Total CPU time: {m.total_cpu_time_s:.3f} s",
        f"- Total wall time: {m.total_wall_time_s:.3f} s",
        f"- Peak memory: {m.peak_memory_mb:.1f} MB",
        "",
        "## Reward (offline objective)",
        "",
        f"- Mean reward: {m.mean_reward:.4f}",
        f"- Per-design reward variance: {m.per_design_reward_variance:.6f}",
        f"- 95% CI (mean reward): {_fmt_ci(m)}",
        "",
        "> Note: TIMEOUT/ERROR/INCONCLUSIVE are never counted as solved. "
        "Orchestration is heuristic; formal-tool results remain authoritative.",
        "",
    ]
    return "\n".join(lines)


def render_comparison(results: dict[str, dict[str, PolicyMetrics]], split: str = "test") -> str:
    """Render a leaderboard over policies for a given split."""
    lines = [
        f"# Policy comparison (split: {split})",
        "",
        "| Policy | Solved % | PASS | FAIL | TIMEOUT | ERROR | INCONC | "
        "CPU s | Wall s | PeakMem MB | Mean reward | Reward 95% CI | Design var |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",  # noqa: E501
    ]
    # Sort by solved %, then mean reward (deterministic tie-break by name).
    def _key(item: tuple[str, dict[str, PolicyMetrics]]) -> tuple[float, float, str]:
        m = item[1][split]
        return (-m.solved_within_budget_pct, -m.mean_reward, item[0])

    for name, per_split in sorted(results.items(), key=_key):
        m = per_split[split]
        c = m.status_counts
        lines.append(
            f"| {name} | {m.solved_within_budget_pct:.1f} | {c.PASS} | {c.FAIL} | "
            f"{c.TIMEOUT} | {c.ERROR} | {c.INCONCLUSIVE} | {m.total_cpu_time_s:.1f} | "
            f"{m.total_wall_time_s:.1f} | {m.peak_memory_mb:.0f} | {m.mean_reward:.3f} | "
            f"{_fmt_ci(m)} | {m.per_design_reward_variance:.4f} |"
        )
    lines += [
        "",
        "> Metrics computed on the held-out split via the deterministic MOCK executor. "
        "See THREAT_MODEL.md for threats to validity (leakage, correlated designs, "
        "non-determinism, tool-version drift, selective reporting).",
        "",
    ]
    return "\n".join(lines)


def render_ablation(results: dict[str, PolicyMetrics]) -> str:
    lines = [
        "# Bandit feature-group ablation (TEST split)",
        "",
        "Each row removes one feature group from the LinUCB context. A drop vs `full` "
        "indicates the group carries signal.",
        "",
        "| Variant | Solved % | Mean reward | Design var |",
        "| --- | ---: | ---: | ---: |",
    ]
    full = results.get("full")
    for label, m in results.items():
        delta = ""
        if full is not None and label != "full":
            d = m.mean_reward - full.mean_reward
            delta = f" ({d:+.3f})"
        lines.append(
            f"| {label} | {m.solved_within_budget_pct:.1f} | "
            f"{m.mean_reward:.3f}{delta} | {m.per_design_reward_variance:.4f} |"
        )
    lines += [
        "",
        "> On a small toy suite the trained bandit may converge to the same arm "
        "regardless of which feature group is masked, giving near-zero deltas. That is "
        "expected here and is itself a threat-to-validity signal (sample too small to "
        "attribute importance); see THREAT_MODEL.md.",
        "",
    ]
    return "\n".join(lines)
