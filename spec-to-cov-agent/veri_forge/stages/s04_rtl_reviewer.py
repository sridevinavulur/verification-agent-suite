"""Stage 4 — RTL Reviewer (LLM structural code review)."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
You are an expert RTL verification engineer. Review the provided SystemVerilog/Verilog code.
Flag: dead code, missing resets, FSM escape states, undriven outputs, CDC issues, FIFO pointer bugs.
Format each finding: [SEVERITY] module.signal — description — fix.
"""


class RtlReviewer:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(4, "rtl_review")
        if not ctx.rtl_files:
            return StageResult(stage=4, name="rtl_reviewer", status="skip",
                               summary="No RTL to review")

        snippets = []
        for f in ctx.rtl_files[:3]:
            try:
                snippets.append(f"// {Path(f).name}\n{Path(f).read_text()[:4000]}")
            except Exception:
                pass

        review = simple_call(_SYSTEM, "\n\n".join(snippets), tier="review", max_tokens=4000)
        out = stage_dir / "review.txt"
        out.write_text(review)

        # Count findings
        lines = [l for l in review.splitlines() if l.startswith("[")]
        crits = sum(1 for l in lines if "CRITICAL" in l or "HIGH" in l)

        return StageResult(stage=4, name="rtl_reviewer",
                           status="warn" if crits > 0 else "pass",
                           summary=f"Code review: {len(lines)} finding(s), {crits} high/critical",
                           artifacts={"review": str(out)},
                           data={"findings": len(lines), "critical": crits})
