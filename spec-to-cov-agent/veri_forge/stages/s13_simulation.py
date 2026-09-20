"""Stage 13 — Simulation.

Actually runs cocotb simulation using sim/runner.py.
Collects results and parses real coverage using coverage/parser.py.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models import RunContext, StageResult
from ..sim.runner import SimRunner
from ..coverage.parser import CoverageParser

logger = logging.getLogger(__name__)


class Simulation:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(13, "simulation")

        if not ctx.rtl_files:
            return StageResult(stage=13, name="simulation", status="fail",
                               summary="No RTL files available for simulation")

        test_file = self._find_test_file(ctx)
        if test_file is None:
            return StageResult(stage=13, name="simulation", status="fail",
                               summary="No cocotb test file found from stage 12")

        runner = SimRunner()
        sim_result = runner.run_simulation(
            rtl_files=[Path(f) for f in ctx.rtl_files],
            test_file=test_file,
            top=ctx.config.top,
            out_dir=stage_dir / "sim_out",
            simulator=ctx.config.simulator,
        )

        ctx.sim_log = (sim_result.stdout or "") + (sim_result.stderr or "")
        if sim_result.vcd_path:
            ctx.waveform_path = sim_result.vcd_path

        parser = CoverageParser()
        cov = parser.from_sim_result(sim_result, stage_dir)
        ctx.coverage = cov

        log_path = sim_result.log_path or str(stage_dir / "sim.log")

        status = "pass" if sim_result.success else "fail"
        summary = (
            f"Simulation {'passed' if sim_result.success else 'FAILED'}: "
            f"exit={sim_result.exit_code}, "
            f"compile={sim_result.compile_time_s:.1f}s, sim={sim_result.sim_time_s:.1f}s | "
            f"Coverage: line={cov.line_pct}%, branch={cov.branch_pct}%"
        )

        return StageResult(
            stage=13, name="simulation", status=status,
            summary=summary,
            artifacts={"sim_log": log_path,
                       "lcov": sim_result.lcov_path or "",
                       "coverage_dat": sim_result.coverage_dat_path or ""},
            data={
                "success": sim_result.success,
                "exit_code": sim_result.exit_code,
                "line_pct": cov.line_pct,
                "toggle_pct": cov.toggle_pct,
                "branch_pct": cov.branch_pct,
            },
        )

    def _find_test_file(self, ctx: RunContext) -> Optional[Path]:
        if ctx.cocotb_tests:
            p = Path(ctx.cocotb_tests[0])
            if p.exists():
                return p
        for r in ctx.stage_results:
            if r.stage == 12 and "test_file" in r.artifacts:
                p = Path(r.artifacts["test_file"])
                if p.exists():
                    return p
        return None
