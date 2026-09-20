"""Deterministic Markdown renderer for a :class:`TriageReport`.

Pure function of the report model: same report in -> byte-identical Markdown
out (used for golden tests).
"""

from __future__ import annotations

from .models import TriageReport


def _fmt_loc(rl) -> str:
    if rl.location is None:
        return "(no source-map entry)"
    loc = rl.location
    mod = f" [{rl.module}]" if rl.module else ""
    return f"{loc.file}:{loc.line}:{loc.col}{mod}"


def render_markdown(report: TriageReport) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Equivalence Mismatch-Localization Report")
    a("")
    a(f"- **Reference design:** `{report.reference_design}`")
    a(f"- **Revised design:** `{report.revised_design}`")
    a(f"- **Reported status (from tool, echoed):** `{report.reported_status.value}`")
    a(
        f"- **Compare points:** {report.compare_points_matched} matched / "
        f"{report.compare_points_total} total"
    )
    a(f"- **Distinct mismatch points:** {report.mismatch_count}")
    a(f"- **Mismatch groups (deduplicated):** {len(report.groups)}")
    a("")

    a("> This report echoes the equivalence tool's own status; it does **not** "
      "independently prove equivalence or non-equivalence. All likely-cause "
      "entries are **heuristic**.")
    a("")

    a("## Status evidence")
    a("")
    for ev in report.status_evidence:
        a(f"- `{ev}`")
    a("")

    if report.warnings:
        a("## Warnings")
        a("")
        for w in report.warnings:
            a(f"- {w}")
        a("")

    a("## Configuration / constraint deltas")
    a("")
    if not report.config_deltas:
        a("_No configuration deltas reported._")
    else:
        a("| Key | Reference | Revised | Differs |")
        a("| --- | --- | --- | --- |")
        for d in report.config_deltas:
            a(
                f"| `{d.key}` | {d.reference_value or '-'} | "
                f"{d.revised_value or '-'} | {'YES' if d.differs else 'no'} |"
            )
    a("")

    a("## Reset / initialization comparison")
    a("")
    rc = report.reset_comparison
    a(
        f"- Reference reset: signal=`{rc.reference.signal}`, "
        f"polarity={rc.reference.polarity.value}, sync={rc.reference.sync.value}"
    )
    a(
        f"- Revised reset:   signal=`{rc.revised.signal}`, "
        f"polarity={rc.revised.polarity.value}, sync={rc.revised.sync.value}"
    )
    a(f"- Polarity differs: {'YES' if rc.polarity_differs else 'no'}")
    a(f"- Sync differs: {'YES' if rc.sync_differs else 'no'}")
    if rc.init_value_diffs:
        a("- Init-value differences:")
        for sig, diff in rc.init_value_diffs.items():
            a(f"  - `{sig}`: {diff}")
    for note in rc.notes:
        a(f"- {note}")
    a("")

    a("## Mismatch groups")
    a("")
    if not report.groups:
        a("_No mismatches to localize._")
    for i, g in enumerate(report.groups, 1):
        a(f"### Group {i} (x{g.count}) -- kind: {g.kind.value}")
        a("")
        a(f"- **Signature:** `{g.signature}`")
        a(f"- **Members:** {', '.join(f'`{m}`' for m in g.members)}")
        if g.width_ref is not None or g.width_rev is not None:
            a(f"- **Widths:** ref={g.width_ref}, rev={g.width_rev}")
        a(
            "- **Mismatch cone:** "
            + (", ".join(f"`{s}`" for s in g.cone_signals) or "_(none reported)_")
        )
        a("")
        a("**Likely causes (heuristic):**")
        a("")
        for c in g.likely_causes:
            a(
                f"- `{c.category.value}` (confidence {c.confidence:.2f}, heuristic): "
                + " ".join(c.rationale)
            )
        a("")
        a("**Ranked source locations for review:**")
        a("")
        if not g.ranked_locations:
            a("_No locations resolved._")
        else:
            a("| Rank | Signal | Design | Location | Score | Reasons |")
            a("| --- | --- | --- | --- | --- | --- |")
            for rank, rl in enumerate(g.ranked_locations, 1):
                a(
                    f"| {rank} | `{rl.signal}` | {rl.design} | {_fmt_loc(rl)} | "
                    f"{rl.score:.1f} | {'; '.join(rl.reasons)} |"
                )
        a("")

    if report.debug_packet:
        dp = report.debug_packet
        a("## Reproducible debug packet")
        a("")
        a(f"- **Repro command:** `{dp.repro_command}`")
        a("- **Input files:**")
        for f in dp.input_files:
            a(f"  - `{f}`")
        a("- **Focus compare points:** "
          + (", ".join(f"`{c}`" for c in dp.focus_compare_points) or "_(none)_"))
        a("- **Focus signals:** "
          + (", ".join(f"`{s}`" for s in dp.focus_signals) or "_(none)_"))
        a("- **Suggested next steps:**")
        for step in dp.suggested_next_steps:
            a(f"  1. {step}")
        a("")

    a("## Provenance")
    a("")
    p = report.provenance
    a(f"- tool: `{p.tool}` v`{p.tool_version}` (schema `{p.schema_version}`)")
    a(f"- command: `{p.command}`")
    a(f"- git_sha: `{p.git_sha}`")
    if p.input_sha256:
        a("- input hashes:")
        for f, h in sorted(p.input_sha256.items()):
            a(f"  - `{f}`: `{h[:16]}...`")
    a("")

    return "\n".join(lines) + "\n"
