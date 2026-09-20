"""Dashboard HTML generator for veri-forge runs.

Produces a self-contained HTML report including:
  - Pipeline stage status tiles
  - Coverage metrics with bar charts and unreachability analysis
  - Bug inventory table (grouped by type)
  - Test results table
  - Open items / spec gaps
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import RunContext


def generate_html(ctx: RunContext) -> str:
    """Generate a full HTML dashboard for the completed pipeline run."""
    top = ctx.config.top or "Unknown DUT"
    run_dir = str(ctx.run_dir)
    now = _ts()

    # Gather data
    last_cov = ctx.last_stage("coverage_closure")
    last_sim = ctx.last_stage("simulation")
    last_formal = ctx.last_stage("formal")
    last_debug = ctx.last_stage("debug_analyzer")

    line_pct   = last_cov.data.get("line_pct",   0.0) if last_cov else 0.0
    toggle_pct = last_cov.data.get("toggle_pct", 0.0) if last_cov else 0.0
    branch_pct = last_cov.data.get("branch_pct", 0.0) if last_cov else 0.0
    closure    = last_cov.data.get("closure", "n/a")  if last_cov else "n/a"

    tests_passed = last_sim.data.get("passed", 0) if last_sim else 0
    tests_failed = last_sim.data.get("failed", 0) if last_sim else 0
    tests_total  = tests_passed + tests_failed

    bugs_total   = len(ctx.bugs)
    bugs_open    = sum(1 for b in ctx.bugs if b.get("status") == "open")

    # Unreachability data from coverage closure
    unreachable = []
    if last_cov:
        unreach_json = last_cov.artifacts.get("unreachability_json", "")
        if unreach_json and Path(unreach_json).exists():
            try:
                unreachable = json.loads(Path(unreach_json).read_text())
            except Exception:
                pass

    proven = 0
    if last_formal:
        proven = len(last_formal.data.get("proven", []))

    return _TEMPLATE.format(
        TOP=top,
        NOW=now,
        RUN_DIR=run_dir,
        ITERATIONS=ctx.iteration + 1,
        TESTS_PASSED=tests_passed,
        TESTS_TOTAL=tests_total,
        TESTS_FAILED=tests_failed,
        FORMAL_PROVEN=proven,
        BUGS_TOTAL=bugs_total,
        BUGS_OPEN=bugs_open,
        LINE_PCT=f"{line_pct:.1f}",
        TOGGLE_PCT=f"{toggle_pct:.1f}",
        BRANCH_PCT=f"{branch_pct:.1f}",
        CLOSURE=closure.upper(),
        STAGE_ROWS=_render_stage_rows(ctx.stage_results),
        COV_HISTORY=_render_cov_history(ctx.coverage_history),
        BUG_ROWS=_render_bug_rows(ctx.bugs),
        UNREACH_ROWS=_render_unreach_rows(unreachable),
        SPEC_ISSUES=_render_spec_issues(ctx.bugs),
    )


def _ts() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _bar(pct: float, color: str = "#4CAF50") -> str:
    w = min(100, max(0, pct))
    return (f'<div style="background:#e0e0e0;border-radius:4px;height:14px;width:200px;display:inline-block">'
            f'<div style="background:{color};width:{w}%;height:14px;border-radius:4px"></div></div>'
            f' <b>{pct:.1f}%</b>')


def _badge(status: str) -> str:
    colors = {"pass": "#4CAF50", "fail": "#f44336", "skip": "#9E9E9E",
              "warn": "#FF9800", "open": "#f44336", "fixed": "#4CAF50"}
    c = colors.get(status.lower(), "#9E9E9E")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{status.upper()}</span>'


def _render_stage_rows(stages: list) -> str:
    rows = []
    seen = {}
    for r in stages:
        key = (r.stage, r.name)
        seen[key] = r  # last result per stage wins
    for r in seen.values():
        rows.append(
            f"<tr><td>{r.stage}</td><td>{r.name}</td>"
            f"<td>{_badge(r.status)}</td>"
            f"<td style='font-size:12px;max-width:500px'>{r.summary}</td></tr>"
        )
    return "\n".join(rows)


def _render_cov_history(history: list) -> str:
    if not history:
        return "<tr><td colspan='5'>No coverage history</td></tr>"
    rows = []
    for h in history:
        rows.append(
            f"<tr><td>{h.get('iteration',0)}</td>"
            f"<td>{h.get('line_pct',0):.1f}%</td>"
            f"<td>{h.get('toggle_pct',0):.1f}%</td>"
            f"<td>{h.get('branch_pct',0):.1f}%</td>"
            f"<td>{h.get('tests_passed',0)}/{h.get('tests_passed',0)+h.get('tests_failed',0)}</td></tr>"
        )
    return "\n".join(rows)


def _render_bug_rows(bugs: list) -> str:
    if not bugs:
        return "<tr><td colspan='5'>No bugs recorded</td></tr>"
    rows = []
    for b in bugs:
        rows.append(
            f"<tr><td><code>{b.get('id','?')}</code></td>"
            f"<td>{b.get('failure_type','')}</td>"
            f"<td>{b.get('severity','')}</td>"
            f"<td style='max-width:300px'>{b.get('description','')}</td>"
            f"<td>{_badge(b.get('status','open'))}</td></tr>"
        )
    return "\n".join(rows)


def _render_unreach_rows(unreachable: list) -> str:
    if not unreachable:
        return "<tr><td colspan='4'>No unreachable signals identified</td></tr>"
    rows = []
    cat_labels = {
        "hardwired_constant": "Hardwired",
        "dead_code": "Dead Code",
        "counter_ceiling": "Counter Ceiling",
        "architectural_limit": "Arch Limit",
        "spec_gap": "Spec Gap",
        "unknown": "Unknown",
    }
    for u in unreachable[:50]:
        cat = u.get("category", "unknown")
        rows.append(
            f"<tr><td><code>{u.get('signal','?')}</code></td>"
            f"<td>{u.get('direction','')}</td>"
            f"<td><span style='background:#FF9800;color:#fff;padding:1px 6px;border-radius:8px;"
            f"font-size:11px'>{cat_labels.get(cat, cat)}</span></td>"
            f"<td style='font-size:12px'>{u.get('explanation','')[:120]}</td></tr>"
        )
    return "\n".join(rows)


def _render_spec_issues(bugs: list) -> str:
    issues = [b for b in bugs if b.get("failure_type") == "SPEC_ISSUE"]
    if not issues:
        return "<li>No spec issues identified</li>"
    items = []
    for b in issues:
        items.append(
            f"<li><b>{b.get('id','?')}</b> [{b.get('severity','?')}] "
            f"{b.get('description','')} — <i>{b.get('suggested_fix','')}</i></li>"
        )
    return "\n".join(items)


_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>veri-forge: {TOP}</title>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f5f7fa;margin:0;padding:0;color:#222}}
  .header{{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:28px 40px}}
  .header h1{{margin:0;font-size:28px;letter-spacing:.5px}}
  .header .sub{{font-size:13px;opacity:.8;margin-top:6px}}
  .container{{max-width:1200px;margin:0 auto;padding:24px 40px}}
  .tiles{{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:28px}}
  .tile{{background:#fff;border-radius:10px;padding:20px 24px;min-width:140px;
         box-shadow:0 2px 8px rgba(0,0,0,.09);text-align:center}}
  .tile .val{{font-size:32px;font-weight:700;color:#1a237e;margin:4px 0}}
  .tile .lbl{{font-size:12px;color:#666;text-transform:uppercase;letter-spacing:.5px}}
  .card{{background:#fff;border-radius:10px;padding:20px 24px;margin-bottom:24px;
         box-shadow:0 2px 8px rgba(0,0,0,.09)}}
  .card h2{{margin:0 0 16px;font-size:18px;color:#1a237e;border-bottom:2px solid #e8eaf6;padding-bottom:8px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#e8eaf6;color:#283593;text-align:left;padding:8px 12px}}
  td{{padding:8px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top}}
  tr:hover td{{background:#fafafa}}
  .cov-bar{{margin:8px 0}}
  footer{{text-align:center;font-size:12px;color:#999;padding:20px}}
</style>
</head>
<body>
<div class="header">
  <h1>veri-forge &mdash; {TOP}</h1>
  <div class="sub">Generated: {NOW} &nbsp;|&nbsp; Run dir: {RUN_DIR} &nbsp;|&nbsp; Iterations: {ITERATIONS}</div>
</div>

<div class="container">

<!-- Stat tiles -->
<div class="tiles">
  <div class="tile"><div class="val">{TESTS_PASSED}/{TESTS_TOTAL}</div><div class="lbl">Tests Pass</div></div>
  <div class="tile"><div class="val">{FORMAL_PROVEN}</div><div class="lbl">Formal Proven</div></div>
  <div class="tile"><div class="val">{BUGS_TOTAL}</div><div class="lbl">Total Bugs</div></div>
  <div class="tile"><div class="val">{BUGS_OPEN}</div><div class="lbl">Open Bugs</div></div>
  <div class="tile"><div class="val">{LINE_PCT}%</div><div class="lbl">Line Coverage</div></div>
  <div class="tile"><div class="val">{TOGGLE_PCT}%</div><div class="lbl">Toggle Coverage</div></div>
  <div class="tile"><div class="val">{BRANCH_PCT}%</div><div class="lbl">Branch Coverage</div></div>
  <div class="tile"><div class="val" style="font-size:18px">{CLOSURE}</div><div class="lbl">Closure Status</div></div>
</div>

<!-- Pipeline stages -->
<div class="card">
  <h2>Pipeline Stage Results</h2>
  <table>
    <tr><th>#</th><th>Stage</th><th>Status</th><th>Summary</th></tr>
    {STAGE_ROWS}
  </table>
</div>

<!-- Coverage history -->
<div class="card">
  <h2>Coverage Closure History</h2>
  <table>
    <tr><th>Iter</th><th>Line</th><th>Toggle</th><th>Branch</th><th>Tests</th></tr>
    {COV_HISTORY}
  </table>
</div>

<!-- Unreachability analysis -->
<div class="card">
  <h2>Toggle Unreachability Analysis</h2>
  <p style="font-size:13px;color:#555">
    Signals below are architecturally unreachable and excluded from the effective coverage ceiling.
  </p>
  <table>
    <tr><th>Signal</th><th>Direction</th><th>Category</th><th>Explanation</th></tr>
    {UNREACH_ROWS}
  </table>
</div>

<!-- Bug inventory -->
<div class="card">
  <h2>Bug Inventory</h2>
  <table>
    <tr><th>ID</th><th>Type</th><th>Severity</th><th>Description</th><th>Status</th></tr>
    {BUG_ROWS}
  </table>
</div>

<!-- Spec issues -->
<div class="card">
  <h2>Open Spec / Design Issues</h2>
  <ul style="font-size:13px;line-height:1.8">
    {SPEC_ISSUES}
  </ul>
</div>

</div>
<footer>Generated by veri-forge &mdash; agentic hardware verification pipeline</footer>
</body>
</html>
"""
