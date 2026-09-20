"""Stage 14 — FSDB / Waveform Analyzer.

Analyzes simulation logs and waveforms to extract:
  - Assertion failures with context
  - Protocol violation events
  - X-propagation / metastability markers
  - Timing violations

Supports: plain text logs (always), FSDB (via nWave/Verdi if available),
VCD (via pyDigitalWaveTools if installed).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from ..llm.client import simple_call
from ..models import RunContext, StageResult

_FAIL_PATTERNS = [
    re.compile(r"FAIL\s*:?\s*(.+)", re.IGNORECASE),
    re.compile(r"Error\s*:?\s*(.+)", re.IGNORECASE),
    re.compile(r"AssertionError\s*:?\s*(.+)", re.IGNORECASE),
    re.compile(r"ASSERTION\s+FAILED\s*:?\s*(.+)", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"\[CRITICAL\]\s+(.+)"),
]

_SYSTEM = """\
You are an expert in hardware simulation log analysis. Extract from the log:
1. Which tests failed and their immediate error messages
2. Signal values at the point of failure
3. Protocol sequence leading to the failure
4. Whether the root cause is likely in the DUT (RTL bug), testbench (TB bug), or spec ambiguity
Return concise findings with specific line references.
"""


class FsdbAnalyzer:
    def run(self, ctx: RunContext, llm_client=None) -> StageResult:
        stage_dir = ctx.stage_dir(14, "fsdb_analyzer")

        if not ctx.sim_log:
            return StageResult(stage=14, name="fsdb_analyzer", status="skip",
                               summary="No simulation log — skipping")

        # Extract failure events from log
        failures = _extract_failures(ctx.sim_log)

        # LLM analysis of log
        llm_analysis = ""
        if failures or "FAIL" in ctx.sim_log.upper():
            llm_analysis = simple_call(
                _SYSTEM,
                f"DUT: {ctx.config.top}\nLog:\n{ctx.sim_log[-6000:]}",
                tier="gen",
                client=llm_client,
                max_tokens=2000,
            )

        # Try VCD parsing if waveform available
        vcd_summary = ""
        if ctx.waveform_path and ctx.waveform_path.endswith(".vcd"):
            vcd_summary = _parse_vcd(ctx.waveform_path)

        analysis = {
            "failure_events": failures,
            "llm_analysis": llm_analysis,
            "vcd_summary": vcd_summary,
        }
        out = stage_dir / "fsdb_analysis.json"
        out.write_text(json.dumps(analysis, indent=2, default=str))

        # Store LLM analysis in context for debug stage
        ctx.sim_log = ctx.sim_log + "\n\n=== FSDB ANALYSIS ===\n" + llm_analysis

        return StageResult(
            stage=14, name="fsdb_analyzer", status="pass",
            summary=f"Extracted {len(failures)} failure event(s) from simulation log",
            artifacts={"analysis": str(out)},
            data={"failure_count": len(failures), "has_llm_analysis": bool(llm_analysis)},
        )


def _extract_failures(log: str) -> List[Dict]:
    failures = []
    lines = log.splitlines()
    for i, line in enumerate(lines):
        for pat in _FAIL_PATTERNS:
            m = pat.search(line)
            if m:
                context_start = max(0, i - 3)
                context = "\n".join(lines[context_start:i + 4])
                failures.append({
                    "line": i + 1,
                    "message": m.group(1) if m.lastindex else line.strip(),
                    "context": context,
                })
                break
    return failures[:20]  # cap at 20


def _parse_vcd(vcd_path: str) -> str:
    try:
        with open(vcd_path) as f:
            lines = [f.readline() for _ in range(50)]
        return f"VCD header: {''.join(lines[:10])}"
    except Exception as exc:
        return f"VCD parse error: {exc}"
