"""Render a RegressionReport to Markdown.

The Markdown mirrors the JSON contract; it never adds claims that are not in the
underlying findings (every regression line links back to its evidence).
"""

from __future__ import annotations

from .models import RegressionFinding, RegressionReport, Verdict

_VERDICT_BADGE = {
    Verdict.REGRESSION: "🔴 REGRESSION",
    Verdict.IMPROVEMENT: "🟢 IMPROVEMENT",
    Verdict.STABLE: "⚪ STABLE",
    Verdict.INCONCLUSIVE: "🟡 INCONCLUSIVE",
}


def _finding_table_row(f: RegressionFinding) -> str:
    return (
        f"| {_VERDICT_BADGE[f.verdict]} "
        f"| `{f.metric.value}` "
        f"| {f.config} / {f.workload} "
        f"| {f.baseline_stats.mean:.3f} "
        f"| {f.candidate_stats.mean:.3f} "
        f"| {f.delta_pct:+.1f}% "
        f"| {f.robust_z:+.2f} "
        f"| {f.confidence:.2f} |"
    )


def render_markdown(report: RegressionReport) -> str:
    lines: list[str] = []
    lines.append(f"# Performance Regression Report: {report.dataset_name}")
    lines.append("")
    lines.append(f"- Schema version: `{report.schema_version}`")
    lines.append(f"- Runs analyzed: **{report.n_runs}**")
    lines.append(f"- Comparisons: **{report.n_comparisons}**")
    lines.append(f"- Regressions detected: **{report.n_regressions}**")
    lines.append("")

    cfg = report.detection_config
    lines.append("## Detection configuration")
    lines.append("")
    lines.append(f"- min |Δ%| to flag: `{cfg.min_pct_change}%`")
    lines.append(f"- robust z threshold: `{cfg.robust_z_threshold}`")
    lines.append(f"- min samples for confident verdict: `{cfg.min_samples_for_confident}`")
    lines.append(
        f"- outlier rejection: IQR k=`{cfg.outlier_iqr_k}`, "
        f"modified-z=`{cfg.outlier_z_threshold}`"
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Verdict | Metric | Config / Workload | Baseline mean "
        "| Candidate mean | Δ% | robust z | Confidence |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for f in report.findings:
        lines.append(_finding_table_row(f))
    lines.append("")

    regs = report.regressions()
    if regs:
        lines.append("## Regressions (with evidence)")
        lines.append("")
        for f in regs:
            lines.append(
                f"### 🔴 `{f.metric.value}` — {f.config} / {f.workload} "
                f"({f.delta_pct:+.1f}%)"
            )
            lines.append("")
            lines.append(f"- Environment: `{f.env_fingerprint}`")
            lines.append(
                f"- Baseline commit `{f.baseline_commit}` → "
                f"candidate commit `{f.candidate_commit}`"
            )
            lines.append(
                f"- Baseline: mean={f.baseline_stats.mean:.3f} "
                f"(n={f.baseline_stats.n}, stdev={f.baseline_stats.stdev:.3f}, "
                f"CV={f.baseline_stats.cv:.3f}, "
                f"95% CI [{f.baseline_stats.ci95_low:.3f}, "
                f"{f.baseline_stats.ci95_high:.3f}])"
            )
            lines.append(
                f"- Candidate: mean={f.candidate_stats.mean:.3f} "
                f"(n={f.candidate_stats.n}, stdev={f.candidate_stats.stdev:.3f}, "
                f"CV={f.candidate_stats.cv:.3f}, "
                f"95% CI [{f.candidate_stats.ci95_low:.3f}, "
                f"{f.candidate_stats.ci95_high:.3f}])"
            )
            lines.append(f"- Confidence: **{f.confidence:.2f}**")
            lines.append("- Evidence:")
            for e in f.evidence:
                lines.append(f"  - {e}")
            if f.artifact_urls:
                lines.append("- Artifacts:")
                for u in f.artifact_urls:
                    lines.append(f"  - <{u}>")
            lines.append("")
    else:
        lines.append("## Regressions")
        lines.append("")
        lines.append("No regressions detected above the configured thresholds.")
        lines.append("")

    lines.append("---")
    lines.append(
        "_Heuristic report. Findings are deterministic statistical comparisons, "
        "not a root-cause claim. Every REGRESSION/IMPROVEMENT verdict lists its "
        "supporting evidence; INCONCLUSIVE marks changes that lack enough samples "
        "or signal-to-noise to confirm._"
    )
    lines.append("")
    return "\n".join(lines)
