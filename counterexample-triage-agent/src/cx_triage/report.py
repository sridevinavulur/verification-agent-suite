"""Deterministic Markdown rendering of a :class:`TriageReport`.

Rendering is a pure function of the report so it is trivially golden-testable.
"""

from __future__ import annotations

from .models import TriageReport


def render_markdown(report: TriageReport) -> str:
    r = report
    out: list[str] = []
    out.append(f"# Counterexample Triage Report: `{r.property_name}`")
    out.append("")
    out.append("> Heuristic triage. Hypotheses are ranked evidence-based guesses,")
    out.append("> not conclusions. No RTL or assertions were modified.")
    out.append("")

    out.append("## Property context")
    out.append("")
    out.append(f"- **Property:** `{r.property_name}`")
    out.append(f"- **Location:** `{r.property_location.file}:{r.property_location.line}`")
    if r.property_text:
        out.append(f"- **Text:** `{r.property_text}`")
    out.append(f"- **Clock:** `{r.clock}`")
    out.append(f"- **Reset:** `{r.reset}`" if r.reset else "- **Reset:** (none declared)")
    out.append("")

    out.append("## Key cycles")
    out.append("")
    out.append(
        "- **Antecedent activation:** "
        + (
            f"cycle {r.antecedent_cycle} (time {r.antecedent_time})"
            if r.antecedent_cycle is not None
            else "not located"
        )
    )
    out.append(
        "- **First divergence:** "
        + (
            f"cycle {r.first_divergence_cycle} (time {r.first_divergence_time})"
            if r.first_divergence_cycle is not None
            else "not located"
        )
    )
    out.append("")

    out.append("## Event timeline")
    out.append("")
    if r.timeline:
        out.append("| Cycle | Time | Kind | Description | Signals |")
        out.append("| --- | --- | --- | --- | --- |")
        for e in r.timeline:
            sigs = ", ".join(f"{k}={v}" for k, v in sorted(e.signals.items()))
            out.append(
                f"| {e.cycle} | {e.time} | {e.kind} | {e.description} | {sigs} |"
            )
    else:
        out.append("_No clock edges available to build a timeline._")
    out.append("")

    out.append("## Relevant RTL cone")
    out.append("")
    if r.rtl_cone:
        out.append("_Heuristic structural cone (backward dependency reachability):_")
        out.append("")
        for s in r.rtl_cone:
            out.append(f"- `{s}`")
    else:
        out.append("_No RTL manifest supplied; cone not computed._")
    out.append("")

    out.append("## Source citations")
    out.append("")
    for c in r.citations:
        sym = f" (`{c.symbol}`)" if c.symbol else ""
        out.append(f"- `{c.file}:{c.line}`{sym} — {c.reason}")
    out.append("")

    out.append("## Ranked root-cause hypotheses")
    out.append("")
    for i, h in enumerate(r.hypotheses, 1):
        out.append(
            f"### {i}. {h.category.value} — confidence {h.confidence:.2f}"
        )
        out.append("")
        out.append(h.statement)
        out.append("")
        out.append("Evidence:")
        for ev in h.evidence:
            out.append(f"- {ev}")
        out.append("")

    out.append("## Unresolved questions")
    out.append("")
    if r.unresolved_questions:
        for q in r.unresolved_questions:
            out.append(f"- {q}")
    else:
        out.append("- (none)")
    out.append("")

    out.append("## Reproduction")
    out.append("")
    out.append("```")
    out.append(r.reproduction.command)
    out.append("```")
    out.append("")
    out.append("Artifacts:")
    for a in r.reproduction.artifacts:
        out.append(f"- `{a}`")
    out.append("")

    if r.reproduction_attempt is not None:
        ra = r.reproduction_attempt
        out.append("## Real reproduction (advisory, not evidence)")
        out.append("")
        out.append(f"- **Status:** `{ra.status}`")
        out.append(f"- **Adapter:** `{ra.adapter}`")
        if ra.summary:
            out.append(f"- **Summary:** {ra.summary}")
        if ra.exit_code is not None:
            out.append(f"- **Exit code:** {ra.exit_code}")
        for note in ra.notes:
            out.append(f"- {note}")
        out.append("")

    if r.llm_narrative:
        out.append("## LLM narrative (advisory, not evidence)")
        out.append("")
        out.append(r.llm_narrative)
        out.append("")

    return "\n".join(out)
