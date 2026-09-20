"""Human-readable Markdown rendering of a triage report."""

from __future__ import annotations

from .report_models import Crossing, TriageReport


def _loc(loc: object) -> str:
    if loc is None:
        return "?"
    return f"{loc.file}:{loc.line}:{loc.col}"  # type: ignore[attr-defined]


def _crossing_md(c: Crossing) -> list[str]:
    lines = [
        f"#### [{c.severity.value}] score={c.risk_score} "
        f"{c.kind.value}: `{c.src_signal}` -> `{c.dst_signal}` "
        f"(module `{c.module}`)",
        "",
        f"- source domain: `{c.src_domain.label()}` @ {_loc(c.src_location)}",
        f"- destination domain: `{c.dst_domain.label()}` @ {_loc(c.dst_location)}",
        f"- width: {c.width_bits if c.width_bits is not None else 'unknown'}"
        f"{'  (MULTI-BIT)' if c.multi_bit else ''}",
        f"- synchronizer evidence: {c.sync_evidence.value}"
        f"{f' (depth {c.sync_depth})' if c.sync_depth else ''}",
        "- HEURISTIC finding" if c.heuristic else "- proven finding",
        "- rationale:",
    ]
    lines.extend(f"  - {r}" for r in c.rationale)
    lines.append("")
    return lines


def render_markdown(report: TriageReport) -> str:
    out: list[str] = []
    out.append("# CDC/RDC Structural Triage Report")
    out.append("")
    out.append(f"> **{report.disclaimer}**")
    out.append("")
    out.append(f"- tool: `{report.tool}` v{report.tool_version}")
    out.append(f"- top: `{report.top}`" if report.top else "- top: (none)")
    out.append("")

    out.append("## Non-claims")
    out.extend(f"- {n}" for n in report.non_claims)
    out.append("")

    out.append("## Summary")
    for k in sorted(report.summary):
        out.append(f"- {k}: {report.summary[k]}")
    out.append("")

    out.append("## Findings by module")
    out.append("")
    for mr in report.modules:
        out.append(f"### Module `{mr.module}`")
        out.append("")
        out.append(f"- clock domains: {', '.join(mr.clock_domains) or '(none)'}")
        out.append(f"- reset domains: {', '.join(mr.reset_domains) or '(none)'}")
        out.append("")
        if not mr.crossings:
            out.append("_No candidate CDC/RDC crossings detected in this module._")
            out.append("")
            out.append(
                "> Absence of detected crossings is NOT a clean result -- it may "
                "reflect the limits of structural heuristics."
            )
            out.append("")
            continue
        for c in mr.crossings:
            out.extend(_crossing_md(c))

    out.append("## Reviewer checklist")
    out.extend(f"- [ ] {item}" for item in report.reviewer_checklist)
    out.append("")

    out.append("## Limitations")
    out.extend(f"- {lim}" for lim in report.limitations)
    out.append("")

    return "\n".join(out) + "\n"
