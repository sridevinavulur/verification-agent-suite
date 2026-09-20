"""Stage 16 — Coverage Closure.

REAL coverage closure loop:
1. Check current coverage vs target
2. Identify uncovered items
3. Ask LLM to generate targeted cocotb tests
4. ACTUALLY run simulation with new tests (SimRunner)
5. Parse REAL coverage from simulation output
6. Iterate until target met or max_iter exhausted
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import CoverageResult, RunContext, StageResult
from ..sim.runner import SimRunner
from ..coverage.parser import CoverageParser

logger = logging.getLogger(__name__)

_SYSTEM = """You are a cocotb test engineer specializing in coverage closure.
Given a list of uncovered RTL lines and branches, generate targeted cocotb tests
that specifically exercise those code paths.

Requirements:
- Use @cocotb.test() decorator
- Each test targets a specific uncovered item
- Include proper reset sequence (rst_n low 5 cycles, then high)
- Drive corner-case stimulus that would toggle the uncovered signal
- Output ONLY Python code, starting with import statements."""


class CoverageClosureStage:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(16, "coverage_closure")
        iterations_run = 0
        iteration_log: List[Dict[str, Any]] = []

        cov = ctx.coverage
        if cov is None:
            return StageResult(stage=16, name="coverage_closure", status="skip",
                               summary="No coverage data from stage 13 — cannot close coverage")

        runner = SimRunner()
        parser = CoverageParser()

        for iteration in range(ctx.config.max_iter):
            current_overall = self._overall(cov)
            logger.info("Iter %d: overall=%.1f%% target=%.1f%%",
                        iteration, current_overall, ctx.config.target_coverage)

            iter_entry: Dict[str, Any] = {
                "iteration": iteration,
                "before": {"line_pct": cov.line_pct, "branch_pct": cov.branch_pct,
                           "toggle_pct": cov.toggle_pct, "overall": current_overall},
            }

            if current_overall >= ctx.config.target_coverage:
                iter_entry["action"] = "target_met"
                iteration_log.append(iter_entry)
                break

            gaps = self._find_gaps(cov)
            if not gaps:
                iter_entry["action"] = "no_gaps_found"
                iteration_log.append(iter_entry)
                break

            new_test_code = self._generate_targeted_tests(gaps, ctx, iteration)
            if not new_test_code:
                iter_entry["action"] = "test_gen_failed"
                iteration_log.append(iter_entry)
                break

            iter_dir = stage_dir / f"iter_{iteration:02d}"
            iter_dir.mkdir(exist_ok=True)
            test_file = iter_dir / f"test_coverage_iter{iteration}.py"
            test_file.write_text(new_test_code)

            sim_result = runner.run_simulation(
                rtl_files=[Path(f) for f in ctx.rtl_files],
                test_file=test_file,
                top=ctx.config.top,
                out_dir=iter_dir / "sim",
                simulator=ctx.config.simulator,
            )

            if not sim_result.success:
                logger.warning("Iter %d simulation failed (exit=%d)", iteration, sim_result.exit_code)
                iter_entry["action"] = "sim_failed"
                iter_entry["exit_code"] = sim_result.exit_code
                iteration_log.append(iter_entry)
                iterations_run += 1
                continue

            new_cov = parser.from_sim_result(sim_result, iter_dir)
            new_overall = self._overall(new_cov)

            iter_entry["after"] = {"line_pct": new_cov.line_pct, "branch_pct": new_cov.branch_pct,
                                   "toggle_pct": new_cov.toggle_pct, "overall": new_overall}
            iter_entry["delta"] = round(new_overall - current_overall, 2)
            iter_entry["action"] = "sim_ok"
            iteration_log.append(iter_entry)

            if new_overall > current_overall:
                cov = new_cov
                ctx.coverage = new_cov

            iterations_run += 1

        final_cov = ctx.coverage or cov
        final_overall = self._overall(final_cov)
        met = final_overall >= ctx.config.target_coverage

        log_file = stage_dir / "closure_log.json"
        log_file.write_text(json.dumps(iteration_log, indent=2, default=str))

        return StageResult(
            stage=16, name="coverage_closure",
            status="pass" if met else "fail",
            summary=(
                f"Coverage closure: {iterations_run} iteration(s), "
                f"final overall={final_overall:.1f}% "
                f"({'MET' if met else 'NOT MET'} target={ctx.config.target_coverage}%), "
                f"line={final_cov.line_pct}%, branch={final_cov.branch_pct}%"
            ),
            artifacts={"closure_log": str(log_file)},
            data={
                "iterations": iterations_run,
                "target_met": met,
                "final_line_pct": final_cov.line_pct,
                "final_branch_pct": final_cov.branch_pct,
                "final_toggle_pct": final_cov.toggle_pct,
                "final_overall_pct": final_overall,
            },
        )

    def _overall(self, cov: Optional[CoverageResult]) -> float:
        if cov is None:
            return 0.0
        vals = [v for v in [cov.line_pct, cov.branch_pct, cov.toggle_pct] if v > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def _find_gaps(self, cov: CoverageResult) -> List[str]:
        return list(cov.uncovered_lines[:30]) + list(cov.uncovered_branches[:15])

    def _generate_targeted_tests(
        self, gaps: List[str], ctx: RunContext, iteration: int
    ) -> str:
        from ..llm.client import simple_call
        spec_summary = json.dumps(ctx.parsed_spec.get("protocol", {}), default=str)[:2000]
        user = (
            f"Module: {ctx.config.top}\n"
            f"Protocol: {spec_summary}\n\n"
            f"Uncovered items to target (iteration {iteration}):\n"
            + "\n".join(f"  - {g}" for g in gaps[:25])
        )
        try:
            return simple_call(system=_SYSTEM, user=user, tier="gen", max_tokens=6144)
        except Exception as e:
            logger.warning("Targeted test generation failed: %s", e)
            return ""
