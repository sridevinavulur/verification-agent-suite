"""CoverageParser — normalize coverage data from any simulator backend.

Accepts a SimRunResult and returns a CoverageResult (legacy name kept for
compatibility with the old models.py RunContext.coverage field).

Internally delegates to veri_forge.sim.coverage helpers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import CoverageSnapshot
from ..sim.coverage import (
    build_coverage_result,
    parse_coverage_dat,
    parse_lcov,
    parse_stdout_coverage,
    extract_toggle_coverage,
)


class CoverageParser:
    """Normalize coverage numbers from simulation output into a CoverageSnapshot."""

    def from_sim_result(self, sim_result, out_dir: Path) -> "LegacyCoverageResult":
        """
        Accept a SimRunResult (from sim/runner.py) and return a coverage
        object compatible with the RunContext.coverage field.
        """
        rich = build_coverage_result(
            iteration=0,
            coverage_dat=sim_result.coverage_dat_path,
            lcov_path=sim_result.lcov_path,
            stdout=(sim_result.stdout or "") + (sim_result.stderr or ""),
            tests_passed=sim_result.tests_passed,
            tests_failed=sim_result.tests_failed,
        )

        return LegacyCoverageResult(
            line_pct   = rich.line.pct   if rich.line   else 0.0,
            toggle_pct = rich.toggle.pct if rich.toggle else 0.0,
            branch_pct = rich.branch.pct if rich.branch else 0.0,
            expr_pct   = 0.0,
            line_hit   = rich.line.covered   if rich.line   else 0,
            line_total = rich.line.total     if rich.line   else 0,
            branch_hit = rich.branch.covered if rich.branch else 0,
            branch_total = rich.branch.total if rich.branch else 0,
            uncovered_toggles=[
                f"{u.signal} ({u.direction})" for u in rich.uncovered_toggles
            ],
            raw_lcov_path=sim_result.lcov_path,
        )


class LegacyCoverageResult:
    """Lightweight coverage bag.

    Unifies the attributes expected by:
      - fork's s16_coverage_closure.py (uses .uncovered_lines, .uncovered_branches)
      - fork's s15_debug_analyzer.py  (uses .uncovered_lines, .uncovered_branches)
      - old RunContext.coverage interface
    """

    def __init__(
        self,
        line_pct: float = 0.0,
        toggle_pct: float = 0.0,
        branch_pct: float = 0.0,
        expr_pct: float = 0.0,
        line_hit: int = 0,
        line_total: int = 0,
        branch_hit: int = 0,
        branch_total: int = 0,
        uncovered_toggles=None,
        uncovered_lines=None,
        uncovered_branches=None,
        raw_lcov_path: Optional[str] = None,
    ):
        self.line_pct     = round(line_pct, 1)
        self.toggle_pct   = round(toggle_pct, 1)
        self.branch_pct   = round(branch_pct, 1)
        self.expr_pct     = round(expr_pct, 1)
        self.line_hit     = line_hit
        self.line_total   = line_total
        self.branch_hit   = branch_hit
        self.branch_total = branch_total
        self.uncovered_toggles:  list = uncovered_toggles or []
        # uncovered_lines / uncovered_branches: derived from uncovered_toggles when not set
        self.uncovered_lines:    list = uncovered_lines or [
            t for t in (uncovered_toggles or []) if "0->1" in str(t)
        ]
        self.uncovered_branches: list = uncovered_branches or [
            t for t in (uncovered_toggles or []) if "1->0" in str(t)
        ]
        self.raw_lcov_path = raw_lcov_path

    def overall_pct(self) -> float:
        vals = [v for v in [self.line_pct, self.toggle_pct, self.branch_pct] if v > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def __repr__(self) -> str:
        return (f"Coverage(line={self.line_pct}%, toggle={self.toggle_pct}%, "
                f"branch={self.branch_pct}%)")
