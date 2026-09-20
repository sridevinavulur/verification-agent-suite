"""Human-readable Markdown report for a ProtocolContract."""

from __future__ import annotations

from .models import ProtocolContract, Severity


def _sym(s) -> str:
    loc = f"{s.file}:{s.line}" if s.file and s.line else "?"
    return f"`{s.name}` ({s.ownership.value}, id={s.symbol_id}, {loc})"


def render_markdown(c: ProtocolContract) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# Interface Contract: {c.contract_id}")
    a("")
    a(f"- Protocol: **{c.protocol.value}**")
    a(f"- Module: `{c.module}`")
    if c.instance_label:
        a(f"- Instance: `{c.instance_label}`")
    a("")
    a("> All items below are **candidates for human review**. "
      "Nothing here is verified, proven, or signoff-quality.")
    a("")

    a("## Signal-role mapping")
    a("")
    if c.signal_roles:
        a("| Role | Signal | Ownership | Required | Source |")
        a("|------|--------|-----------|----------|--------|")
        for sr in c.signal_roles:
            s = sr.symbol
            loc = f"{s.file}:{s.line}" if s.file and s.line else ""
            a(f"| {sr.role} | `{s.name}` | {s.ownership.value} | "
              f"{'yes' if sr.required else 'no'} | {loc} |")
    else:
        a("_No roles resolved._")
    a("")

    a("## Clock / reset mapping")
    a("")
    cr = c.clock_reset
    a(f"- Clock: {_sym(cr.clock) if cr.clock else '**UNRESOLVED**'}")
    a(f"- Reset: {_sym(cr.reset) if cr.reset else '**none/UNRESOLVED**'}")
    a(f"- Reset polarity: **{cr.reset_polarity.value}**")
    a(f"- Reset sync: **{cr.reset_sync.value}**")
    a(f"- Reset behavior: {cr.reset_behavior}")
    a("")

    a("## Environmental assumptions")
    a("")
    if c.assumptions:
        for asm in c.assumptions:
            flag = "" if asm.ownership_ok else "  ⚠️ REVIEW: constrains non-input"
            a(f"- **{asm.id}**: {asm.description}{flag}")
            if asm.review_reason:
                a(f"  - review: {asm.review_reason}")
    else:
        a("_None._")
    a("")

    a("## Design guarantees")
    a("")
    if c.guarantees:
        for g in c.guarantees:
            a(f"- **{g.id}**: {g.description}")
    else:
        a("_None._")
    a("")

    a("## Candidate SVA + cover properties")
    a("")
    for p in c.properties:
        a(f"### {p.name}  _( {p.property_kind.value} / {p.role} )_")
        a(p.description)
        if p.depends_on:
            a(f"- depends on: {', '.join(p.depends_on)}")
        for n in p.notes:
            a(f"- note: {n}")
        a("```systemverilog")
        a(p.sva_text)
        a("```")
        a("")

    a("## Negative scenarios")
    a("")
    if c.negative_scenarios:
        for n in c.negative_scenarios:
            a(f"- **{n.id}** ({n.property_kind.value}): {n.description}")
    else:
        a("_None._")
    a("")

    a("## Property dependencies")
    a("")
    if c.dependencies:
        for d in c.dependencies:
            a(f"- `{d.property_name}` -> {', '.join(d.depends_on)}"
              + (f"  ({d.rationale})" if d.rationale else ""))
    else:
        a("_None._")
    a("")

    a("## Review checklist")
    a("")
    for item in c.checklist:
        a(f"- [{item.auto_status}] ({item.severity.value}) **{item.id}**: {item.question}"
          + (f"  -- {item.detail}" if item.detail else ""))
    a("")

    if c.warnings:
        a("## Warnings")
        a("")
        errs = [w for w in c.warnings if w.severity == Severity.ERROR]
        warns = [w for w in c.warnings if w.severity != Severity.ERROR]
        for w in errs + warns:
            a(f"- **{w.severity.value.upper()}** [{w.code}] {w.message}")
        a("")

    a("## Limitations")
    a("")
    for lim in c.limitations:
        a(f"- {lim}")
    a("")
    return "\n".join(lines)


def render_sva_file(c: ProtocolContract) -> str:
    """Emit just the candidate SVA blocks (compiled-offline style)."""
    out: list[str] = []
    out.append(f"// Candidate SVA for contract {c.contract_id}")
    out.append("// CANDIDATE properties for human review. Not verified. "
               "Compile offline; syntactic acceptance != correctness.")
    out.append("")
    for p in c.properties:
        out.append(f"// [{p.property_kind.value}/{p.role}] {p.description}")
        out.append(p.sva_text)
        out.append("")
    return "\n".join(out)
