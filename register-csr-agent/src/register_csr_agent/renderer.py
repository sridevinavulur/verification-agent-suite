"""Human-facing text renderers for package artifacts."""

from __future__ import annotations

from .models import Severity, VerificationPackage


def render_sva_file(pkg: VerificationPackage) -> str:
    lines = [
        "// Candidate SystemVerilog Assertions -- register-csr-agent",
        "// STATUS: candidate (NOT proven / NOT verified).",
        "// Bus handles (csr_write/csr_read/csr_addr/csr_wdata/csr_rdata) are abstract;",
        "// bind them to the real CSR interface before use.",
        "",
    ]
    for s in pkg.candidate_sva:
        lines.append(f"// [{s.check}] {s.rationale}")
        lines.append(s.sva)
        lines.append("")
    return "\n".join(lines)


def render_discrepancy_report(pkg: VerificationPackage) -> str:
    lines = ["# Discrepancy Report", ""]
    lines.append(
        f"ERRORS: {pkg.error_count}  WARNINGS: {pkg.warning_count}  "
        f"TOTAL: {len(pkg.discrepancies)}"
    )
    lines.append("")
    if not pkg.discrepancies:
        lines.append("No discrepancies found by the deterministic checks.")
        return "\n".join(lines)
    for sev in (Severity.ERROR, Severity.WARNING, Severity.INFO):
        group = [d for d in pkg.discrepancies if d.severity == sev]
        if not group:
            continue
        lines.append(f"## {sev.value} ({len(group)})")
        for d in group:
            loc = d.register + (f".{d.field}" if d.field else "")
            lines.append(f"- [{d.code}] {loc}: {d.message}")
            if d.explanation:
                lines.append(f"    explanation: {d.explanation}")
        lines.append("")
    return "\n".join(lines)


def render_coverage_matrix(pkg: VerificationPackage) -> str:
    lines = ["# Coverage Matrix", ""]
    lines.append("| register | field | access | checks | #sva | #tests |")
    lines.append("|---|---|---|---|---|---|")
    for row in pkg.coverage:
        lines.append(
            f"| {row.register} | {row.field or '-'} | {row.access} | "
            f"{','.join(row.checks_covered) or '-'} | {row.sva_count} | {row.test_count} |"
        )
    return "\n".join(lines)


def render_grounding_report(pkg: VerificationPackage) -> str:
    g = pkg.grounding
    lines = ["# RTL Grounding Report", ""]
    lines.append(f"matched {g.matched_count}/{g.total_count}")
    lines.append("")
    for r in g.results:
        if r.matched:
            lines.append(f"- {r.manifest_name} -> {r.rtl_symbol} ({r.match_kind})")
        else:
            lines.append(f"- {r.manifest_name} -> UNMAPPED")
    if g.unmatched_rtl:
        lines.append("")
        lines.append("RTL registers with no manifest counterpart:")
        for s in g.unmatched_rtl:
            lines.append(f"- {s}")
    return "\n".join(lines)


def render_checklist(pkg: VerificationPackage) -> str:
    lines = ["# Human Review Checklist", ""]
    for item in pkg.review_checklist:
        box = "[x]" if item.resolved else "[ ]"
        lines.append(f"- {box} {item.id}: {item.prompt}")
        lines.append(f"      why: {item.why}")
    return "\n".join(lines)
