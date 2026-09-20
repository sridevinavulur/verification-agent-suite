"""16-stage veri-forge pipeline orchestrator.

Runs stages in order, passing RunContext between them. Catches stage
failures and continues (unless the stage is critical: 1=spec_parser, 13=simulation).
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .models import RunConfig, RunContext, StageResult
from .stages import STAGE_MAP

logger = logging.getLogger(__name__)
console = Console()

CRITICAL_STAGES = {1, 13}
STAGE_NAMES = {
    1: "Spec Parser",
    2: "RTL Designer",
    3: "Lint Runner",
    4: "RTL Reviewer",
    5: "Property Gen",
    6: "Formal Verification",
    7: "LEC",
    8: "Testplan Gen",
    9: "Ref Model Gen",
    10: "UVM VIP Gen",
    11: "cocotb VIP Gen",
    12: "Test Gen",
    13: "Simulation",
    14: "Waveform Analyzer",
    15: "Debug Analyzer",
    16: "Coverage Closure",
}


class Pipeline:
    def __init__(self, config: RunConfig):
        self.config = config
        self.run_dir = config.out_dir / f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> RunContext:
        ctx = RunContext(config=self.config, run_dir=self.run_dir)

        console.rule("[bold blue]veri-forge 16-stage DV pipeline[/bold blue]")
        console.print(f"Spec:      {self.config.spec_path}")
        console.print(f"RTL dir:   {self.config.rtl_dir or '(generate from spec)'}")
        console.print(f"Top:       {self.config.top}")
        console.print(f"Simulator: {self.config.simulator}")
        console.print(f"Target:    {self.config.target_coverage}% coverage")
        console.print(f"Output:    {self.run_dir}")
        console.print()

        for stage_n in range(1, 17):
            name = STAGE_NAMES.get(stage_n, f"stage_{stage_n}")

            if stage_n in self.config.skip_stages:
                result = StageResult(stage=stage_n, name=name.lower().replace(" ", "_"),
                                     status="skip", summary="Skipped by --skip-stages flag")
                ctx.stage_results.append(result)
                self._print_result(stage_n, name, result)
                continue

            stage_cls = STAGE_MAP.get(stage_n)
            if stage_cls is None:
                continue

            console.print(f"[cyan]Stage {stage_n:02d}[/cyan] [white]{name}[/white]...", end=" ")
            try:
                result = stage_cls().run(ctx)
            except Exception as exc:
                logger.exception("Stage %d crashed", stage_n)
                result = StageResult(
                    stage=stage_n, name=name.lower().replace(" ", "_"),
                    status="fail", summary=f"Stage crashed: {exc}",
                )

            ctx.stage_results.append(result)
            self._print_result(stage_n, name, result)

            if result.status == "fail" and stage_n in CRITICAL_STAGES:
                console.print(f"\n[bold red]Critical stage {stage_n} failed — aborting pipeline.[/bold red]")
                break

        self._write_results(ctx)
        self._print_summary(ctx)
        return ctx

    def _print_result(self, stage_n: int, name: str, result: StageResult) -> None:
        icon = {"pass": "[green]✓[/green]", "fail": "[red]✗[/red]", "skip": "[yellow]−[/yellow]"}.get(
            result.status, "?"
        )
        console.print(f"{icon} {result.summary}")

    def _write_results(self, ctx: RunContext) -> None:
        from .utils.report import write_report
        write_report(ctx, self.run_dir)

    def _print_summary(self, ctx: RunContext) -> None:
        console.rule("[bold blue]Summary[/bold blue]")
        passed = sum(1 for r in ctx.stage_results if r.status == "pass")
        failed = sum(1 for r in ctx.stage_results if r.status == "fail")
        skipped = sum(1 for r in ctx.stage_results if r.status == "skip")
        console.print(f"Stages: {passed} passed, {failed} failed, {skipped} skipped")

        if ctx.coverage:
            cov = ctx.coverage
            console.print(f"Coverage: line={cov.line_pct}%, toggle={cov.toggle_pct}%, "
                          f"branch={cov.branch_pct}%")

        if ctx.bugs:
            console.print(f"Bugs found: {len(ctx.bugs)}")

        console.print(f"\nResults in: {self.run_dir}")
