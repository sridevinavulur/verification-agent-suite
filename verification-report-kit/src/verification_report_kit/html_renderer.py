"""Self-contained HTML renderer.

Produces a single deterministic HTML string with **inline CSS only** — no
external stylesheets, no CDN scripts, no remote fonts, no images. The output
opens directly in any browser and can be committed / emailed as one file.

The inline-CSS / stat-tile / status-badge / coverage-bar approach is adapted
from the reference dashboard in
``spec-to-cov-agent/veri_forge/dashboard.py`` and
``.../veri_forge/utils/report.py`` (read-only reference), re-implemented here
against the generic :class:`ReportModel` contract so it is decoupled from any
one pipeline. Nothing is copied verbatim; the visual language is the citation.

Determinism: the renderer never calls ``datetime.now()`` or any nondeterministic
source. Any timestamp comes from ``report.provenance.timestamp`` supplied by the
caller, so identical input yields byte-identical output (golden-testable).
"""
from __future__ import annotations

import html

from .models import (
    CoveragePoint,
    Finding,
    ReportModel,
    Section,
    Stat,
    Status,
    Table,
)

# --- color palette -----------------------------------------------------------

_SEVERITY_COLORS = {
    "critical": "#b71c1c",
    "high": "#f44336",
    "medium": "#FF9800",
    "low": "#3b82f6",
    "info": "#9E9E9E",
}

_STATUS_COLORS = {
    "PASS": "#4CAF50",
    "FAIL": "#f44336",
    "TIMEOUT": "#FF9800",
    "ERROR": "#b71c1c",
    "UNKNOWN": "#9E9E9E",
    "INCONCLUSIVE": "#9E9E9E",
    "COMPILED": "#607d8b",
    "WARN": "#FF9800",
    "SKIP": "#9E9E9E",
    "INFO": "#3b82f6",
}


def _esc(value: object) -> str:
    """HTML-escape any value (None -> empty string)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _status_str(status: Status | None) -> str:
    if status is None:
        return ""
    return status.value if isinstance(status, Status) else str(status)


def _badge(status: Status | None) -> str:
    s = _status_str(status)
    if not s:
        return ""
    color = _STATUS_COLORS.get(s.upper(), "#9E9E9E")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:11px;white-space:nowrap">{_esc(s)}</span>'
    )


def _severity_pill(severity: str) -> str:
    sev = (severity or "info").lower()
    color = _SEVERITY_COLORS.get(sev, "#9E9E9E")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 8px;'
        f'border-radius:8px;font-size:11px;text-transform:uppercase">'
        f"{_esc(sev)}</span>"
    )


def _cov_bar(pct: float) -> str:
    w = min(100.0, max(0.0, float(pct)))
    color = "#4CAF50" if w >= 90 else "#FF9800" if w >= 75 else "#f44336"
    return (
        '<div style="background:#e0e0e0;border-radius:4px;height:14px;'
        'width:180px;display:inline-block;vertical-align:middle">'
        f'<div style="background:{color};width:{w:.1f}%;height:14px;'
        'border-radius:4px"></div></div>'
        f' <b>{w:.1f}%</b>'
    )


# --- fragment renderers ------------------------------------------------------


def _render_stat_tiles(stats: list[Stat]) -> str:
    if not stats:
        return ""
    tiles = []
    for s in stats:
        unit = _esc(s.unit) if s.unit else ""
        badge = _badge(s.status)
        badge_html = f'<div style="margin-top:6px">{badge}</div>' if badge else ""
        tiles.append(
            '<div class="tile">'
            f'<div class="val">{_esc(s.value)}{unit}</div>'
            f'<div class="lbl">{_esc(s.label)}</div>'
            f"{badge_html}</div>"
        )
    return '<div class="tiles">\n' + "\n".join(tiles) + "\n</div>"


def _render_table(table: Table) -> str:
    head = "".join(f"<th>{_esc(c)}</th>" for c in table.columns)
    ncols = max(1, len(table.columns))
    if table.rows:
        body_rows = []
        for row in table.rows:
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            body_rows.append(f"<tr>{cells}</tr>")
        body = "\n".join(body_rows)
    else:
        body = f'<tr><td colspan="{ncols}">No data</td></tr>'
    title = f"<h2>{_esc(table.title)}</h2>" if table.title else ""
    note = (
        f'<p style="font-size:12px;color:#666;margin-top:8px">{_esc(table.note)}</p>'
        if table.note
        else ""
    )
    return (
        '<div class="card">'
        f"{title}"
        f"<table><tr>{head}</tr>\n{body}\n</table>"
        f"{note}</div>"
    )


def _render_coverage_history(history: list[CoveragePoint]) -> str:
    if not history:
        return ""
    # Union of metric names, in first-seen order, for stable columns.
    metric_names: list[str] = []
    for point in history:
        for name in point.metrics:
            if name not in metric_names:
                metric_names.append(name)
    head = "<th>Point</th>" + "".join(f"<th>{_esc(m)}</th>" for m in metric_names)
    rows = []
    for point in history:
        cells = f"<td>{_esc(point.label)}</td>"
        for m in metric_names:
            if m in point.metrics:
                cells += f"<td>{_cov_bar(point.metrics[m])}</td>"
            else:
                cells += "<td>&mdash;</td>"
        rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="card"><h2>Coverage History</h2>'
        f"<table><tr>{head}</tr>\n" + "\n".join(rows) + "\n</table></div>"
    )


def _render_findings(findings: list[Finding]) -> str:
    if not findings:
        return (
            '<div class="card"><h2>Findings</h2>'
            '<p style="font-size:13px;color:#555">No findings recorded.</p></div>'
        )
    rows = []
    for f in findings:
        heur = (
            ' <span style="background:#607d8b;color:#fff;padding:0 6px;'
            'border-radius:6px;font-size:10px">HEURISTIC</span>'
            if f.heuristic
            else ""
        )
        desc = _esc(f.description) if f.description else ""
        fix = (
            f'<br><i style="color:#555">Fix: {_esc(f.suggested_fix)}</i>'
            if f.suggested_fix
            else ""
        )
        loc = (
            f'<br><code style="font-size:11px">{_esc(f.location)}</code>'
            if f.location
            else ""
        )
        rows.append(
            "<tr>"
            f"<td><code>{_esc(f.id)}</code></td>"
            f"<td>{_severity_pill(f.severity)}</td>"
            f"<td>{_esc(f.category)}</td>"
            f'<td style="max-width:520px"><b>{_esc(f.title)}</b>{heur}'
            f'<br>{desc}{fix}{loc}</td>'
            f"<td>{_badge(f.status)}</td>"
            "</tr>"
        )
    head = "<th>ID</th><th>Severity</th><th>Category</th><th>Detail</th><th>Status</th>"
    return (
        '<div class="card"><h2>Findings</h2>'
        f"<table><tr>{head}</tr>\n" + "\n".join(rows) + "\n</table></div>"
    )


def _render_section(section: Section) -> str:
    parts = [f'<div class="card"><h2>{_esc(section.heading)} {_badge(section.status)}</h2>']
    if section.body:
        for para in section.body.split("\n\n"):
            para = para.strip()
            if para:
                parts.append(f'<p style="font-size:13px;line-height:1.6">{_esc(para)}</p>')
    if section.bullets:
        items = "".join(f"<li>{_esc(b)}</li>" for b in section.bullets)
        parts.append(f'<ul style="font-size:13px;line-height:1.7">{items}</ul>')
    if section.stats:
        parts.append(_render_stat_tiles(section.stats))
    for table in section.tables:
        # inline (no extra card wrapper) — reuse table markup without the card
        head = "".join(f"<th>{_esc(c)}</th>" for c in table.columns)
        ncols = max(1, len(table.columns))
        if table.rows:
            body = "\n".join(
                "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in r) + "</tr>"
                for r in table.rows
            )
        else:
            body = f'<tr><td colspan="{ncols}">No data</td></tr>'
        tt = f"<h3>{_esc(table.title)}</h3>" if table.title else ""
        parts.append(f"{tt}<table><tr>{head}</tr>\n{body}\n</table>")
    parts.append("</div>")
    return "\n".join(parts)


# --- top-level template ------------------------------------------------------

_STYLE = """
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f7fa;margin:0;padding:0;color:#222}
  .header{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:28px 40px}
  .header h1{margin:0;font-size:26px;letter-spacing:.4px}
  .header .sub{font-size:13px;opacity:.85;margin-top:6px}
  .container{max-width:1200px;margin:0 auto;padding:24px 40px}
  .tiles{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:24px}
  .tile{background:#fff;border-radius:10px;padding:18px 22px;min-width:130px;
        box-shadow:0 2px 8px rgba(0,0,0,.09);text-align:center}
  .tile .val{font-size:30px;font-weight:700;color:#1a237e;margin:2px 0}
  .tile .lbl{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.4px}
  .card{background:#fff;border-radius:10px;padding:20px 24px;margin-bottom:22px;
        box-shadow:0 2px 8px rgba(0,0,0,.09)}
  .card h2{margin:0 0 14px;font-size:18px;color:#1a237e;
           border-bottom:2px solid #e8eaf6;padding-bottom:8px}
  .card h3{font-size:14px;color:#283593;margin:14px 0 6px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{background:#e8eaf6;color:#283593;text-align:left;padding:8px 12px}
  td{padding:8px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top}
  tr:hover td{background:#fafafa}
  code{background:#f0f0f5;padding:1px 4px;border-radius:3px}
  footer{text-align:center;font-size:12px;color:#999;padding:20px}
"""


def _render_provenance(report: ReportModel) -> str:
    p = report.provenance
    fields = [
        ("Tool", p.tool),
        ("Version", p.tool_version),
        ("Git SHA", p.git_sha),
        ("Command", p.command),
        ("Seed", p.seed),
        ("Status", _status_str(p.status)),
        ("Runtime (s)", p.runtime_seconds),
        ("Peak mem (MB)", p.peak_memory_mb),
        ("Timestamp", p.timestamp),
    ]
    rows = [
        f"<tr><td><b>{_esc(k)}</b></td><td>{_esc(v)}</td></tr>"
        for k, v in fields
        if v is not None and v != ""
    ]
    for k, v in p.input_hashes.items():
        rows.append(f"<tr><td><b>hash:{_esc(k)}</b></td><td><code>{_esc(v)}</code></td></tr>")
    for k, v in p.extra.items():
        rows.append(f"<tr><td><b>{_esc(k)}</b></td><td>{_esc(v)}</td></tr>")
    if not rows:
        return ""
    return (
        '<div class="card"><h2>Run Provenance</h2>'
        "<table>" + "\n".join(rows) + "</table></div>"
    )


def render_html(report: ReportModel) -> str:
    """Render a :class:`ReportModel` to a self-contained HTML document string."""
    subline_bits = []
    if report.provenance.tool:
        subline_bits.append(f"Tool: {_esc(report.provenance.tool)}")
    if report.provenance.timestamp:
        subline_bits.append(f"Generated: {_esc(report.provenance.timestamp)}")
    if report.provenance.git_sha:
        subline_bits.append(f"SHA: {_esc(report.provenance.git_sha)}")
    if report.subtitle:
        subline_bits.insert(0, _esc(report.subtitle))
    subline = " &nbsp;|&nbsp; ".join(subline_bits)

    body_parts: list[str] = []
    body_parts.append(_render_stat_tiles(report.stats))
    for section in report.sections:
        body_parts.append(_render_section(section))
    for table in report.tables:
        body_parts.append(_render_table(table))
    body_parts.append(_render_coverage_history(report.coverage_history))
    if report.findings:
        body_parts.append(_render_findings(report.sorted_findings()))
    body_parts.append(_render_provenance(report))

    body = "\n".join(p for p in body_parts if p)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(report.title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="header">
  <h1>{_esc(report.title)}</h1>
  <div class="sub">{subline}</div>
</div>
<div class="container">
{body}
</div>
<footer>Generated by verification-report-kit &mdash; schema v{_esc(report.schema_version)}</footer>
</body>
</html>
"""
