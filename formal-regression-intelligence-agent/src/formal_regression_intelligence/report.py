"""Human-readable Markdown rendering of a RegressionReport."""

from __future__ import annotations

from .explain import LLMAdapter, explain_findings
from .models import FindingKind, RegressionReport

_KIND_TITLES = {
    FindingKind.FAILURE_CLUSTER: "Failure clusters",
    FindingKind.TIMEOUT_CLUSTER: "Timeout clusters",
    FindingKind.DUPLICATE_JOBS: "Duplicate / near-duplicate jobs",
    FindingKind.RUNTIME_REGRESSION: "Runtime-regression alerts",
    FindingKind.MEMORY_REGRESSION: "Memory-regression alerts",
    FindingKind.CONFIG_SENSITIVITY: "Configuration-sensitivity summaries",
    FindingKind.REPRODUCIBILITY_WARNING: "Reproducibility warnings",
}


def render_markdown(report: RegressionReport, *, explain: bool = False,
                    adapter: LLMAdapter | None = None) -> str:
    lines: list[str] = []
    lines.append("# Formal Regression Intelligence Report")
    lines.append("")
    lines.append(
        f"Ingested **{report.n_records}** run records across **{report.n_benchmarks}** "
        f"benchmark(s) / **{report.n_jobs}** logical job(s)."
    )
    lines.append("")
    lines.append("Status totals: " + ", ".join(
        f"`{k}`={v}" for k, v in sorted(report.status_totals.items())
    ))
    lines.append("")
    lines.append(
        "> All findings below are **HEURISTIC** statistical/structural observations. "
        "They do not assert a root cause; correlation is not causation. A TIMEOUT/ERROR/"
        "INCONCLUSIVE result is never a PASS."
    )
    lines.append("")

    explanations = (
        explain_findings(report.findings, adapter) if explain else {}
    )

    lines.append("## Prioritized investigation queue")
    lines.append("")
    if not report.investigation_queue:
        lines.append("_No findings._")
    else:
        lines.append("| # | Severity | Kind | Score | Finding |")
        lines.append("|---|----------|------|-------|---------|")
        for item in report.investigation_queue:
            lines.append(
                f"| {item.rank} | {item.severity.value} | {item.kind.value} | "
                f"{item.priority_score:.1f} | {item.title} |"
            )
    lines.append("")

    for kind in FindingKind:
        group = report.findings_by_kind(kind)
        if not group:
            continue
        lines.append(f"## {_KIND_TITLES[kind]} ({len(group)})")
        lines.append("")
        for f in group:
            lines.append(f"### {f.title}")
            lines.append(f"- id: `{f.finding_id}`  severity: **{f.severity.value}**  "
                         f"score: {f.priority_score:.1f}")
            lines.append(f"- {f.summary}")
            if f.member_run_ids:
                shown = ", ".join(f"`{r}`" for r in f.member_run_ids[:8])
                more = f" (+{len(f.member_run_ids) - 8} more)" if len(f.member_run_ids) > 8 else ""
                lines.append(f"- evidence runs: {shown}{more}")
            if explain and f.finding_id in explanations:
                lines.append(f"- explanation: {explanations[f.finding_id]}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
