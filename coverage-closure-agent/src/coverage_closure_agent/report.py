"""Markdown rendering of a :class:`TriageReport` for human reviewers."""

from __future__ import annotations

from .models import TriageReport


def render_markdown(report: TriageReport) -> str:
    p = report.scope_provenance
    m = report.metrics
    lines: list[str] = []
    lines.append("# Coverage Closure Triage Report")
    lines.append("")
    lines.append(f"- Tool version: `{p.tool_version}`")
    lines.append(
        f"- Coverage format: `{p.coverage_format}` (heuristic triage; tool is authoritative)"
    )
    lines.append(f"- Seed: `{p.seed}`")
    lines.append(f"- Coverage items: {p.total_items}  |  Holes: {p.total_holes}")
    lines.append("")
    lines.append("## Metrics")
    lines.append(f"- Valid proposal rate: {m.valid_proposal_rate:.2f}")
    lines.append(f"- Provenance completeness: {m.provenance_completeness:.2f}")
    lines.append(f"- Total recommendations: {m.total_recommendations}")
    if m.sample_size:
        lines.append(f"- Sample size: {m.sample_size}")
        if m.category_precision is not None:
            lines.append(f"- Category precision (vs labels): {m.category_precision:.2f}")
        if m.accepted_proposal_rate is not None:
            lines.append(f"- Accepted proposal rate: {m.accepted_proposal_rate:.2f}")
        if m.false_positive_proposal_rate is not None:
            lines.append(f"- False-positive proposal rate: {m.false_positive_proposal_rate:.2f}")
    lines.append("")
    lines.append("## Coverage-Hole Classifications (ranked actions)")
    for c in report.classifications:
        lines.append("")
        lines.append(f"### `{c.coverage_id}` -- {c.category.value} ({c.kind.value}, {c.module})")
        lines.append(
            f"- Heuristic: {c.is_heuristic}  |  Provenance complete: {c.provenance_complete}"
        )
        if c.root_cause_hypotheses:
            lines.append("- Root-cause hypotheses:")
            for hyp in c.root_cause_hypotheses:
                lines.append(f"  - {hyp}")
        lines.append("- Evidence:")
        for e in c.evidence:
            ref = f" [{e.ref}]" if e.ref else ""
            lines.append(f"  - ({e.source}) {e.detail}{ref}")
        lines.append("- Ranked next actions (all require human approval):")
        for i, r in enumerate(c.recommendations, 1):
            lines.append(
                f"  {i}. **{r.action.value}** (priority {r.priority_score:.2f}, "
                f"expected impact ~{r.expected_impact_items} item(s)) -- {r.rationale}"
            )
            if r.detail:
                lines.append(f"     - Next step: {r.detail}")
    lines.append("")
    lines.append("## Independent-Measurement Manifest")
    lines.append("The agent cannot claim closure. Re-measure coverage independently:")
    for step in report.independent_measurement:
        lines.append(f"- `{step.coverage_id}`: {step.instruction}")
        lines.append(f"  - Verify covered when: {step.verify_covered_when}")
    lines.append("")
    lines.append("## Human-Review Queue")
    for item in report.human_review_queue:
        actions = ", ".join(a.value for a in item.recommendations)
        lines.append(f"- `{item.coverage_id}`: {item.reason} Actions: [{actions}]")
    lines.append("")
    lines.append("## Enforced Prohibited Actions")
    for pa in report.prohibited_actions_enforced:
        lines.append(f"- NEVER: {pa.value}")
    lines.append("")
    lines.append(f"> {p.scope_note}")
    lines.append("")
    return "\n".join(lines)
