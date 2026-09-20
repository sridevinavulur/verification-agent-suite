"""Stage 15 — Debug Analyzer.

Uses LLM to analyze:
- Failing test logs from stage 13
- Low-coverage areas from ctx.coverage
- RTL reviewer bugs from ctx.bugs
Generates debug hypotheses and suggests targeted tests for coverage closure.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from ..models import RunContext, StageResult

logger = logging.getLogger(__name__)

_SYSTEM = """You are a hardware DV debug expert. Analyze the simulation log, coverage gaps,
and known bugs to produce debugging insights and test suggestions.

For each coverage gap or failing test:
1. Hypothesize the root cause
2. Suggest a targeted cocotb test that would expose or cover it
3. Estimate the coverage improvement if the gap is closed

Return JSON:
{
  "hypotheses": [
    {"gap": "description", "root_cause": "hypothesis", "test_suggestion": "cocotb test description"}
  ],
  "priority_targets": ["signal or branch name that is most impactful to cover next"]
}"""


class DebugAnalyzer:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(15, "debug_analyzer")

        cov = ctx.coverage
        if cov is None and not ctx.sim_log:
            return StageResult(stage=15, name="debug_analyzer", status="skip",
                               summary="No coverage data or simulation log available")

        uncovered_sample: List[str] = []
        if cov:
            uncovered_sample = (
                (cov.uncovered_lines[:20] if cov.uncovered_lines else []) +
                (cov.uncovered_branches[:10] if cov.uncovered_branches else [])
            )
        sim_log_excerpt = ctx.sim_log[-4000:] if ctx.sim_log else ""

        analysis = self._analyze(uncovered_sample, sim_log_excerpt, ctx.bugs[:5])

        out_file = stage_dir / "debug_analysis.json"
        out_file.write_text(json.dumps(analysis, indent=2, default=str))

        n_hyp = len(analysis.get("hypotheses", []))
        targets = analysis.get("priority_targets", [])

        return StageResult(
            stage=15, name="debug_analyzer", status="pass",
            summary=f"Debug analysis: {n_hyp} hypothesis(es), {len(targets)} priority target(s)",
            artifacts={"analysis": str(out_file)},
            data={"hypotheses": analysis.get("hypotheses", []),
                  "priority_targets": targets},
        )

    def _analyze(
        self,
        uncovered: List[str],
        sim_log: str,
        bugs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        from ..llm.client import simple_call
        user = (
            f"Uncovered items:\n{json.dumps(uncovered, indent=2)}\n\n"
            f"Known bugs:\n{json.dumps(bugs, indent=2, default=str)}\n\n"
            f"Simulation log (last 4k):\n{sim_log}"
        )
        try:
            raw = simple_call(system=_SYSTEM, user=user, tier="gen", max_tokens=4096)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            logger.warning("Debug analysis failed: %s", e)
        return {"hypotheses": [], "priority_targets": uncovered[:5]}
