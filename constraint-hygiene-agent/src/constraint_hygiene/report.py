"""Render a HygieneReport to human-readable Markdown."""

from __future__ import annotations

from .models import Finding, HygieneReport


def _findings_table(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["_None flagged._", ""]
    lines = ["| Code | Severity | Confidence | Message |", "|---|---|---|---|"]
    for f in findings:
        msg = f.message.replace("|", "\\|")
        lines.append(
            f"| {f.code.value} | {f.severity.value} | {f.confidence.value} | {msg} |"
        )
    lines.append("")
    return lines


def render_markdown(report: HygieneReport) -> str:
    r = report
    out: list[str] = []
    out.append("# Constraint Hygiene Report")
    out.append("")
    out.append(f"> **{r.disclaimer}**")
    out.append("")
    out.append(f"- Tool: `{r.provenance.tool}` v{r.provenance.tool_version}")
    out.append(f"- Top module: `{r.top_module or 'unknown'}`")
    out.append(f"- Inputs: {', '.join(r.provenance.input_files) or 'n/a'}")
    out.append("")

    out.append("## Assumption inventory")
    out.append("")
    if r.assumption_inventory:
        out.append("| Name | Line | Signals | Expr |")
        out.append("|---|---|---|---|")
        for p in r.assumption_inventory:
            expr = p.expr.replace("|", "\\|")
            out.append(f"| {p.name} | {p.line} | {', '.join(p.signals)} | `{expr}` |")
    else:
        out.append("_No assumptions found._")
    out.append("")

    out.append(
        f"## Signal ownership classification ({len(r.signal_ownership)} signals)"
    )
    out.append("")
    out.append("| Signal | Ownership | Rationale |")
    out.append("|---|---|---|")
    for c in r.signal_ownership:
        out.append(f"| {c.signal} | {c.ownership.value} | {c.rationale} |")
    out.append("")

    out.append("## Contradiction candidates")
    out.append("")
    out.extend(_findings_table(r.contradiction_candidates))

    out.append("## Unused assumption candidates")
    out.append("")
    out.extend(_findings_table(r.unused_assumption_candidates))

    out.append("## Output / internal-state constraint warnings")
    out.append("")
    out.extend(_findings_table(r.output_constraint_warnings))

    out.append("## Property dependency map")
    out.append("")
    if r.dependency_map:
        out.append("| Property | Signal | Constrained by assumptions |")
        out.append("|---|---|---|")
        for e in r.dependency_map:
            out.append(
                f"| {e.property} | {e.signal} | "
                f"{', '.join(e.constrained_by_assumptions) or '-'} |"
            )
    else:
        out.append("_No assert/cover properties to map._")
    out.append("")

    out.append("## Vacuity / reachability recommendations")
    out.append("")
    out.extend(_findings_table(r.vacuity_recommendations))

    out.append("## Human-review queue")
    out.append("")
    if r.human_review_queue:
        out.append("| Priority | Subject | Reason | Findings |")
        out.append("|---|---|---|---|")
        for item in r.human_review_queue:
            reason = item.reason.replace("|", "\\|")
            codes = ", ".join(c.value for c in item.related_findings)
            out.append(f"| P{item.priority} | {item.subject} | {reason} | {codes} |")
    else:
        out.append("_Queue empty. NOTE: an empty queue is not a soundness result._")
    out.append("")
    return "\n".join(out)
