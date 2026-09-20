"""Top-level review orchestration: parse -> run deterministic checks -> report."""

from __future__ import annotations

import re
from pathlib import Path

from .checks import REGISTRY, CheckContext
from .models import (
    Finding,
    ParsedProperty,
    ReviewReport,
    RtlIntentManifest,
    Severity,
)
from .parser import parse_sva

_REQ_TAG_RE = re.compile(r"//\s*@requirement:\s*([A-Za-z0-9_\-]+)")

# Severity ordering for stable output (errors first).
_SEV_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _extract_traceability(text: str, props: list[ParsedProperty]) -> dict[str, str]:
    """Associate each `// @requirement: X` tag with the property whose source
    line is nearest *after* the tag."""
    lines = text.splitlines()
    tags: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        m = _REQ_TAG_RE.search(line)
        if m:
            tags.append((i, m.group(1)))

    traced: dict[str, str] = {}
    for p in props:
        key = p.name or f"@line{p.location.line}"
        best: str | None = None
        best_line = -1
        for tline, req in tags:
            if tline <= p.location.line and tline > best_line:
                best_line = tline
                best = req
        if best is not None:
            traced[key] = best
    return traced


def build_checklist(report: ReviewReport) -> list[str]:
    """Reviewer checklist. Items are marked done/attention based on findings."""
    seen = {f.check_id for f in report.findings}
    items = [
        ("Every property has an explicit clock", "MISSING_CLOCK"),
        ("Reset handling via 'disable iff' is present and correct polarity",
         "MISSING_DISABLE_IFF"),
        ("Reset polarity matches the RTL Intent Manifest", "RESET_POLARITY_RISK"),
        ("Implication style (|-> vs |=>) matches intended cycle alignment",
         "IMPLICATION_STYLE_RISK"),
        ("Temporal operators are bounded / intentional", "UNBOUNDED_TEMPORAL"),
        ("Consequents are non-trivial and specific", "WEAK_CONSEQUENT"),
        ("No antecedent duplicated in consequent", "ANTECEDENT_IN_CONSEQUENT"),
        ("No trivially-passing / vacuous-by-construction assertions", "TRIVIALLY_PASSING"),
        ("Assumptions constrain inputs only (not outputs/internal state)",
         "ASSUME_CONSTRAINS_OUTPUT"),
        ("All identifiers grounded to manifest, widths match", "UNDECLARED_SIGNAL"),
        ("Property names reflect semantics", "NAME_SEMANTICS"),
        ("Properties traced to requirements", "REQ_TRACEABILITY"),
        ("Antecedent reachability confirmed (cover / formal) -- vacuity is heuristic here",
         "VACUITY_RISK"),
    ]
    out: list[str] = []
    for text, cid in items:
        mark = "[!]" if cid in {s.value for s in seen} else "[x]"
        out.append(f"{mark} {text}")
    return out


def review_text(
    sva_text: str,
    source_file: str = "<memory>",
    manifest: RtlIntentManifest | None = None,
    requirement_ids: set[str] | None = None,
) -> ReviewReport:
    props = parse_sva(sva_text, file=source_file)
    traced = _extract_traceability(sva_text, props)

    all_findings: list[Finding] = []
    for p in props:
        ctx = CheckContext(
            prop=p,
            manifest=manifest,
            requirement_ids=requirement_ids or set(),
            traced=traced,
        )
        for check in REGISTRY:
            all_findings.extend(check(ctx))

    all_findings.sort(
        key=lambda f: (f.location.line, _SEV_ORDER[f.severity], f.check_id.value)
    )

    report = ReviewReport(
        source_file=source_file,
        manifest_top=manifest.top if manifest else None,
        property_count=len(props),
        findings=all_findings,
    )
    report.checklist = build_checklist(report)
    return report


def review_file(
    sva_path: str | Path,
    manifest_path: str | Path | None = None,
    requirement_ids: set[str] | None = None,
    manifest_format: str = "auto",
) -> ReviewReport:
    sva_path = Path(sva_path)
    text = sva_path.read_text()
    manifest = None
    if manifest_path is not None:
        # ``auto`` detects and adapts a canonical rtl-intent-ingestor manifest,
        # while still accepting this reviewer's own fixture format.
        from .rtl_intent_adapter import load_manifest

        manifest = load_manifest(manifest_path, manifest_format=manifest_format)
    return review_text(
        text,
        source_file=str(sva_path),
        manifest=manifest,
        requirement_ids=requirement_ids,
    )
