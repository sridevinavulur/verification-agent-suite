"""Markdown report generator for a ResetIntentManifest.

The report foregrounds the safety posture: STRUCTURAL vs verified, HEURISTIC
labels, and explicit ambiguities. It is meant to be read by a verification
engineer before any candidate SVA is used.
"""

from __future__ import annotations

from .models import ResetIntentManifest, ResetPolarity


def _loc(loc) -> str:
    if loc is None:
        return ""
    s = f"{loc.file}:{loc.line}"
    if loc.col:
        s += f":{loc.col}"
    return f" ({s})"


def render_markdown(m: ResetIntentManifest) -> str:
    out: list[str] = []
    top = m.design_top or "(unknown)"
    out.append(f"# Reset Intent Report — `{top}`")
    out.append("")
    out.append(
        "> **Structural detection, not verified intent.** All reset-domain "
        "relationships are **HEURISTIC** until reviewed. Reset polarity is never "
        "inferred silently. Candidate SVA is **candidate** only — not verified."
    )
    out.append("")
    out.append(f"- Tool: `{m.provenance.tool}` v{m.provenance.tool_version}")
    out.append(f"- Schema: {m.schema_version}")
    out.append("")

    # Reset candidates
    out.append("## Reset candidates (STRUCTURAL)")
    out.append("")
    if not m.reset_candidates:
        out.append("_No reset candidates detected._")
    else:
        out.append("| Signal | Polarity | Sync | Confidence | Port | Fanout |")
        out.append("|---|---|---|---|---|---|")
        for c in m.reset_candidates:
            flag = " ⚠️" if c.polarity == ResetPolarity.UNKNOWN else ""
            out.append(
                f"| `{c.signal}`{_loc(c.location)} | {c.polarity.value}{flag} | "
                f"{c.sync.value} | {c.confidence:.2f} | {c.is_port} | "
                f"{len(c.fanout_registers)} reg |"
            )
        out.append("")
        out.append("### Polarity evidence")
        for c in m.reset_candidates:
            out.append(f"- **`{c.signal}`** → `{c.polarity.value}`")
            for e in c.polarity_evidence:
                out.append(f"  - [{e.kind}] {e.detail} → votes `{e.votes_polarity.value}`")
    out.append("")

    # Domains
    out.append("## Reset domains (HEURISTIC)")
    out.append("")
    if not m.reset_domains:
        out.append("_No reset domains grouped._")
    else:
        for d in m.reset_domains:
            out.append(
                f"- **{d.domain_id}** — reset `{d.reset_signal}` "
                f"({d.polarity.value}, {d.sync.value}) — members: "
                + ", ".join(f"`{r}`" for r in d.members)
            )
    out.append("")

    # Crossings
    out.append("## Possible reset-domain crossings (HEURISTIC)")
    out.append("")
    if not m.domain_crossings:
        out.append("_None detected._")
    else:
        for cr in m.domain_crossings:
            out.append(
                f"- `{cr.from_register}` ({cr.from_domain}) → "
                f"`{cr.to_register}` ({cr.to_domain}) — {cr.severity.value}"
                f"{_loc(cr.location)}"
            )
            for r in cr.rationale:
                out.append(f"  - {r}")
    out.append("")

    # Candidate SVA
    out.append("## Candidate reset-behavior SVA (CANDIDATE — not verified)")
    out.append("")
    if not m.candidate_sva:
        out.append("_No candidate properties generated._")
    for p in m.candidate_sva:
        out.append(f"### {p.property_id} `{p.name}` — status: {p.status.value}")
        out.append("")
        out.append("```systemverilog")
        out.append(p.sva_text)
        out.append("```")
        out.append(f"- Rationale: {p.rationale}")
        for note in p.review_notes:
            out.append(f"- Review: {note}")
        out.append("")

    # Risks
    out.append("## Risks & ambiguities")
    out.append("")
    if m.risks:
        out.append("### Risks")
        for r in m.risks:
            h = " [HEURISTIC]" if r.heuristic else ""
            out.append(
                f"- **{r.severity.value.upper()}** ({r.category}){h}: {r.detail}{_loc(r.location)}"
            )
        out.append("")
    if m.ambiguities:
        out.append("### Ambiguities (not inferred silently)")
        for a in m.ambiguities:
            out.append(
                f"- **{a.severity.value.upper()}** {a.ambiguity_id}: {a.detail}{_loc(a.location)}"
            )
        out.append("")

    # Recommendations
    out.append("## Test / cover recommendations")
    out.append("")
    for rec in m.recommendations:
        tgt = f" (`{rec.target_signal}`)" if rec.target_signal else ""
        out.append(f"- [{rec.kind}] {rec.rec_id}{tgt}: {rec.detail}")
    out.append("")

    return "\n".join(out)
