"""Human-readable Markdown renderer for a RecoveryReport."""

from __future__ import annotations

from .models import Provenance, RecoveryReport, TargetPhase


def _cmd_line(c) -> str:
    tag = "EXTRACTED" if c.provenance is Provenance.EXTRACTED else "HYPOTHESIS"
    ev = ""
    if c.evidence:
        e = c.evidence[0]
        ev = f" _(evidence: {e.file}:{e.line})_"
    dest = " **[destructive]**" if c.destructive else ""
    line = f"- `{c.command}` [{tag}] phase={c.phase.value}{dest}{ev}"
    if c.provenance is Provenance.HYPOTHESIS and c.rationale:
        line += f"\n    - rationale: {c.rationale}"
    return line


def render_markdown(report: RecoveryReport) -> str:
    r = report
    out: list[str] = []
    out.append("# Testbench Recovery Report")
    out.append("")
    out.append(f"- tool: {r.repro.tool_name} v{r.repro.tool_version}")
    out.append(f"- repo root: `{r.repro.repo_root}`")
    out.append(f"- git SHA: {r.repro.git_sha or '(not a git checkout)'}")
    out.append(f"- inspected files: {len(r.repro.inspected_files)}")
    out.append("")

    if r.recommended_smoke_test:
        out.append("## Recommended minimal smoke test")
        out.append("")
        out.append(_cmd_line(r.recommended_smoke_test))
        out.append("")

    out.append("## Candidate commands")
    out.append("")
    for phase in TargetPhase:
        group = [c for c in r.candidate_commands if c.phase is phase]
        if not group:
            continue
        out.append(f"### {phase.value}")
        for c in group:
            out.append(_cmd_line(c))
        out.append("")

    if r.tool_requirements:
        out.append("## Tool / simulator requirements")
        out.append("")
        for t in r.tool_requirements:
            tag = ("EXTRACTED" if t.provenance is Provenance.EXTRACTED
                   else "HYPOTHESIS")
            out.append(f"- **{t.name}** ({t.category}) [{tag}]")
        out.append("")

    if r.dependencies:
        out.append("## Dependency inventory")
        out.append("")
        for d in r.dependencies:
            out.append(f"- {d.name} (via {d.manager})")
        out.append("")

    if r.target_source_map:
        out.append("## Target -> source mapping")
        out.append("")
        for m in r.target_source_map:
            srcs = ", ".join(m.sources) or "(none)"
            fls = ", ".join(m.filelists)
            extra = f" | filelists: {fls}" if fls else ""
            out.append(f"- **{m.target_name}**: {srcs}{extra}")
        out.append("")

    if r.setup_issues:
        out.append("## Unresolved setup issues")
        out.append("")
        for i in r.setup_issues:
            loc = ""
            if i.evidence:
                e = i.evidence[0]
                loc = f" _({e.file}:{e.line})_"
            out.append(f"- [{i.severity.value.upper()}] {i.message}{loc}")
        out.append("")

    return "\n".join(out) + "\n"
