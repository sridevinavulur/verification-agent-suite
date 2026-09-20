"""Stage 12 — Test Generator (full 16-stage pipeline numbering).

Generates cocotb test file from the test plan.
On subsequent iterations, generates targeted tests for uncovered signals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM_INITIAL = """\
You are an expert cocotb verification engineer. Generate a complete cocotb test file
implementing all test cases from the provided test plan.
Requirements:
  - Use @cocotb.test() decorator with timeout_time parameter
  - Apply proper reset sequence before each test
  - Assert on expected outputs with descriptive messages
  - Use the provided BFM classes for protocol-correct stimulus
  - Import the BFM from the bfm module
Output ONLY valid Python code.
"""

_SYSTEM_TARGETED = """\
You are a cocotb verification engineer improving coverage.
Generate ADDITIONAL @cocotb.test() functions to cover specific uncovered signals.
Do NOT rewrite existing tests. Only add new ones.
Output ONLY valid Python code.
"""


class TestGen:
    def run(
        self,
        ctx: RunContext,
        uncovered_signals: Optional[List[str]] = None,
    ) -> StageResult:
        stage_dir = ctx.stage_dir(12, "test_gen")
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "DUT"

        if ctx.iteration == 0 or ctx.test_file is None:
            code = self._initial(ctx, dut)
            out = stage_dir / f"test_{dut.lower()}.py"
            out.write_text(code)
            ctx.test_file = str(out)
            n = len(ctx.testplan.get("test_cases", []))
            summary = f"Generated test file with {n} test cases"
        else:
            code = self._targeted(ctx, dut, uncovered_signals or [])
            iter_out = stage_dir / f"test_{dut.lower()}_iter{ctx.iteration}.py"
            iter_out.write_text(code)
            if ctx.test_file and Path(ctx.test_file).exists():
                existing = Path(ctx.test_file).read_text()
                header = f"\n\n# === Coverage Closure Iteration {ctx.iteration} ===\n"
                Path(ctx.test_file).write_text(existing + header + code)
            summary = f"Appended targeted tests (iter {ctx.iteration}, {len(uncovered_signals or [])} target signals)"

        return StageResult(
            stage=12, name="test_gen", status="pass",
            summary=summary,
            artifacts={"test_file": ctx.test_file or ""},
            data={"iteration": ctx.iteration},
        )

    def _initial(self, ctx: RunContext, dut: str) -> str:
        bfm = ctx.bfm_file or "(no BFM)"
        user = (
            f"DUT: {dut}\nBFM: {bfm}\n"
            f"Spec: {json.dumps(ctx.parsed_spec, indent=2)[:3000]}\n"
            f"Test plan: {json.dumps(ctx.testplan, indent=2)[:3000]}\n"
            f"Ref model: {ctx.ref_model_file or '(none)'}\n"
        )
        return simple_call(_SYSTEM_INITIAL, user, tier="gen", max_tokens=8000)

    def _targeted(self, ctx: RunContext, dut: str, uncovered: List[str]) -> str:
        sigs = "\n".join(f"  - {s}" for s in uncovered[:30])
        prev = json.dumps(ctx.coverage_history[-1] if ctx.coverage_history else {}, indent=2)
        user = f"DUT: {dut}\nIteration: {ctx.iteration}\nUncovered:\n{sigs}\nPrev coverage:\n{prev}"
        return simple_call(_SYSTEM_TARGETED, user, tier="gen", max_tokens=4000)
