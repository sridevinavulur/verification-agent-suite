"""Report writer — generates results.json, bug_list.json, dashboard.html."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict

from ..models import RunContext


def write_report(ctx: RunContext, run_dir: Path) -> None:
    _write_results_json(ctx, run_dir)
    _write_bug_list(ctx, run_dir)
    _write_dashboard(ctx, run_dir)


def _write_results_json(ctx: RunContext, run_dir: Path) -> None:
    data = {
        "run_dir": str(run_dir),
        "timestamp": datetime.datetime.now().isoformat(),
        "config": ctx.config.model_dump(mode="json", exclude_none=True),
        "stages": [r.model_dump() for r in ctx.stage_results],
        "coverage": ctx.coverage.model_dump() if ctx.coverage else None,
        "bugs": ctx.bugs,
    }
    (run_dir / "results.json").write_text(json.dumps(data, indent=2, default=str))


def _write_bug_list(ctx: RunContext, run_dir: Path) -> None:
    open_bugs = [b for b in ctx.bugs if b.get("status") in ("open", None, "")]
    fixed_bugs = [b for b in ctx.bugs if b.get("status") == "fixed"]
    data = {
        "bugs": ctx.bugs,
        "summary": (
            f"{len(ctx.bugs)} bug(s): "
            f"{len(fixed_bugs)} fixed, {len(open_bugs)} open. "
            + (f"Coverage: line {ctx.coverage.line_pct}%, "
               f"toggle {ctx.coverage.toggle_pct}%, "
               f"branch {ctx.coverage.branch_pct}%"
               if ctx.coverage else "No coverage data.")
        ),
    }
    (run_dir / "bug_list.json").write_text(json.dumps(data, indent=2, default=str))


def _write_dashboard(ctx: RunContext, run_dir: Path) -> None:
    cov = ctx.coverage
    stages = ctx.stage_results

    stage_rows = ""
    for r in stages:
        color = {"pass": "#22c55e", "fail": "#ef4444", "skip": "#a3a3a3"}.get(r.status, "#666")
        badge = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(r.status, r.status.upper())
        stage_rows += (
            f'<tr><td>S{r.stage:02d}</td><td>{r.name}</td>'
            f'<td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px">'
            f'{badge}</span></td><td>{r.summary}</td></tr>\n'
        )

    bug_rows = ""
    for b in ctx.bugs:
        sev_color = {"P1": "#ef4444", "P2": "#f97316", "P3": "#3b82f6"}.get(b.get("severity", ""), "#666")
        status_color = "#22c55e" if b.get("status") == "fixed" else "#ef4444"
        bug_rows += (
            f'<tr><td>{b.get("id","")}</td>'
            f'<td><span style="color:{sev_color};font-weight:bold">{b.get("severity","")}</span></td>'
            f'<td>{b.get("failure_type","")}</td>'
            f'<td>{b.get("description","")}</td>'
            f'<td><span style="color:{status_color}">{b.get("status","open")}</span></td></tr>\n'
        )

    def cov_bar(pct: float) -> str:
        color = "#22c55e" if pct >= 90 else "#f97316" if pct >= 75 else "#ef4444"
        return (
            f'<div style="background:#e5e7eb;border-radius:4px;height:18px;width:200px;display:inline-block">'
            f'<div style="background:{color};width:{min(pct,100):.0f}%;height:100%;border-radius:4px"></div>'
            f'</div> <span>{pct:.1f}%</span>'
        )

    cov_section = ""
    if cov:
        cov_section = f"""
<h2>Coverage</h2>
<table>
<tr><td><b>Line</b></td><td>{cov_bar(cov.line_pct)}</td></tr>
<tr><td><b>Toggle</b></td><td>{cov_bar(cov.toggle_pct)}</td></tr>
<tr><td><b>Branch</b></td><td>{cov_bar(cov.branch_pct)}</td></tr>
<tr><td><b>Expression</b></td><td>{cov_bar(cov.expr_pct)}</td></tr>
</table>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>veri-forge DV Dashboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; margin-bottom: 4px; }}
  h2 {{ color: #7dd3fc; border-bottom: 1px solid #334155; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
  th {{ background: #1e293b; color: #94a3b8; text-align: left; padding: 8px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b; }}
  .stat {{ display: inline-block; background: #1e293b; border-radius: 8px; padding: 16px 24px;
            margin: 0 8px 16px 0; text-align: center; }}
  .stat-val {{ font-size: 2em; font-weight: bold; color: #38bdf8; }}
  .stat-lbl {{ color: #64748b; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>veri-forge DV Dashboard</h1>
<p style="color:#64748b">Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} &bull;
   Top: {ctx.config.top} &bull; Simulator: {ctx.config.simulator}</p>

<div>
  <div class="stat"><div class="stat-val">{sum(1 for r in stages if r.status=='pass')}/{len(stages)}</div><div class="stat-lbl">Stages Passed</div></div>
  <div class="stat"><div class="stat-val">{len(ctx.bugs)}</div><div class="stat-lbl">Bugs Found</div></div>
  {f'<div class="stat"><div class="stat-val">{cov.line_pct:.1f}%</div><div class="stat-lbl">Line Coverage</div></div>' if cov else ''}
  {f'<div class="stat"><div class="stat-val">{cov.branch_pct:.1f}%</div><div class="stat-lbl">Branch Coverage</div></div>' if cov else ''}
</div>

{cov_section}

<h2>Pipeline Stages</h2>
<table>
<tr><th>Stage</th><th>Name</th><th>Status</th><th>Summary</th></tr>
{stage_rows}
</table>

<h2>Bugs ({len(ctx.bugs)})</h2>
<table>
<tr><th>ID</th><th>Sev</th><th>Type</th><th>Description</th><th>Status</th></tr>
{bug_rows if bug_rows else '<tr><td colspan="5" style="color:#64748b">No bugs found</td></tr>'}
</table>

</body>
</html>"""

    (run_dir / "dashboard.html").write_text(html)
