"""veri-forge Pipeline Orchestrator.

Runs the 16-stage DV pipeline from spec to coverage closure and generates
a final HTML dashboard report.

Stage map (driven by stages/__init__.py STAGE_MAP):
  1  SpecParser        — parse design spec
  2  RtlDesigner       — generate or locate RTL
  3  LintRunner        — verilator lint check
  4  RtlReviewer       — LLM code review
  5  PropertyGen       — SVA property generation
  6  Formal            — JasperGold / sby formal verification
  7  Lec               — Logic Equivalence Check
  8  TestplanGen       — test plan from spec
  9  RefModelGen       — Python golden model
  10 UvmVipGen         — UVM VIP stubs (optional)
  11 CocotbVipGen      — cocotb BFMs
  12 TestGen           — cocotb test file
  13 Simulation        — run Verilator / VCS / Xcelium
  14 FsdbAnalyzer      — log + waveform analysis
  15 DebugAnalyzer     — CRAVS root-cause analysis
  16 CoverageClosureStage — parse coverage, decide iterate/done

Coverage closure loop:   12 → 13 → 14 → 15 → 16 → [done|12→…]
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .models import RunConfig, RunContext, StageResult
from .stages import STAGE_MAP

logger = logging.getLogger(__name__)

# Stages that participate in the coverage closure loop
_CLOSURE_STAGES = [12, 13, 14, 15, 16]


class VeriForgeOrchestrator:
    """Main pipeline runner."""

    def __init__(self, config: RunConfig):
        self.config = config

    def run(self, llm_client=None) -> RunContext:
        run_dir = Path(self.config.out_dir) / f"run_{int(time.time())}"
        run_dir.mkdir(parents=True, exist_ok=True)

        ctx = RunContext(config=self.config, run_dir=run_dir)
        logger.info("veri-forge run started: %s", run_dir)

        # ── Phase 1: Stages 1–11 (run once) ────────────────────────────────
        for stage_num in range(1, 12):
            if stage_num in self.config.skip_stages:
                ctx.stage_results.append(StageResult(
                    stage=stage_num, name=f"stage_{stage_num}", status="skip",
                    summary="Skipped per config.skip_stages",
                ))
                continue

            stage_cls = STAGE_MAP.get(stage_num)
            if stage_cls is None:
                continue

            logger.info("Stage %d: %s", stage_num, stage_cls.__name__)
            try:
                instance = stage_cls()
                result = self._call_stage(instance, ctx, llm_client)
                ctx.stage_results.append(result)
                self._log_stage(result)
                if result.status == "fail":
                    logger.warning("Stage %d failed — continuing anyway", stage_num)
            except Exception as exc:
                logger.exception("Stage %d raised exception", stage_num)
                ctx.stage_results.append(StageResult(
                    stage=stage_num,
                    name=stage_cls.__name__,
                    status="fail",
                    summary=f"Exception: {exc}",
                ))

        # ── Phase 2: Coverage closure loop (stages 12–16) ──────────────────
        for iteration in range(self.config.max_iter):
            ctx.iteration = iteration
            logger.info("=== Coverage closure iteration %d ===", iteration)

            for stage_num in _CLOSURE_STAGES:
                if stage_num in self.config.skip_stages:
                    continue
                stage_cls = STAGE_MAP.get(stage_num)
                if stage_cls is None:
                    continue

                logger.info("Stage %d (iter %d): %s", stage_num, iteration, stage_cls.__name__)
                try:
                    instance = stage_cls()
                    result = self._call_stage(instance, ctx, llm_client)
                    ctx.stage_results.append(result)
                    self._log_stage(result)
                except Exception as exc:
                    logger.exception("Stage %d iter %d raised exception", stage_num, iteration)
                    ctx.stage_results.append(StageResult(
                        stage=stage_num,
                        name=stage_cls.__name__ if stage_cls else f"stage_{stage_num}",
                        status="fail",
                        summary=f"Exception: {exc}",
                    ))

            # Check coverage closure decision from stage 16
            last_16 = ctx.last_stage("coverage_closure")
            if last_16:
                closure = last_16.data.get("closure", "iterate")
                if closure in ("closed", "max_iter"):
                    logger.info("Coverage closure: %s after %d iteration(s)", closure, iteration + 1)
                    break
                if iteration < self.config.max_iter - 1:
                    logger.info("Iterating: %d reachable signals still uncovered",
                                last_16.data.get("reachable_uncovered", 0))
            else:
                logger.info("No coverage closure result — stopping loop")
                break

        # ── Phase 3: Dashboard ──────────────────────────────────────────────
        self._generate_dashboard(ctx)

        # ── Save run summary ────────────────────────────────────────────────
        summary = self._build_summary(ctx)
        (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str))
        logger.info("veri-forge run complete: %s", run_dir)
        return ctx

    def _call_stage(self, instance: Any, ctx: RunContext, llm_client) -> StageResult:
        """Call stage.run() with the right args (handle both signatures)."""
        import inspect
        sig = inspect.signature(instance.run)
        params = list(sig.parameters.keys())
        if "llm_client" in params:
            return instance.run(ctx, llm_client=llm_client)
        else:
            return instance.run(ctx)

    def _log_stage(self, result: StageResult) -> None:
        icon = {"pass": "✓", "fail": "✗", "skip": "–", "warn": "⚠"}.get(result.status, "?")
        logger.info("  [%s] Stage %d (%s): %s", icon, result.stage, result.name, result.summary)

    def _generate_dashboard(self, ctx: RunContext) -> None:
        try:
            from .dashboard import generate_html
            html = generate_html(ctx)
            dash = ctx.run_dir / "dashboard.html"
            dash.write_text(html)
            logger.info("Dashboard: %s", dash)
        except Exception as exc:
            logger.warning("Dashboard generation failed: %s", exc)

    def _build_summary(self, ctx: RunContext) -> Dict[str, Any]:
        last_cov = ctx.last_stage("coverage_closure")
        last_sim = ctx.last_stage("simulation")
        return {
            "run_dir": str(ctx.run_dir),
            "spec": str(ctx.config.spec_path),
            "top": ctx.config.top,
            "stages_run": len(ctx.stage_results),
            "stages_passed": sum(1 for r in ctx.stage_results if r.status == "pass"),
            "stages_failed": sum(1 for r in ctx.stage_results if r.status == "fail"),
            "iterations": ctx.iteration + 1,
            "coverage": {
                "line_pct":   last_cov.data.get("line_pct", 0)   if last_cov else 0,
                "toggle_pct": last_cov.data.get("toggle_pct", 0) if last_cov else 0,
                "branch_pct": last_cov.data.get("branch_pct", 0) if last_cov else 0,
                "closure":    last_cov.data.get("closure", "n/a")  if last_cov else "n/a",
            },
            "tests": {
                "passed": last_sim.data.get("passed", 0) if last_sim else 0,
                "failed": last_sim.data.get("failed", 0) if last_sim else 0,
            },
            "bugs_total": len(ctx.bugs),
        }
