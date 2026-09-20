"""Stage 8 — Test Plan Generator."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm.client import structured_call
from ..models import RunContext, StageResult

_SYSTEM = """\
You are a hardware verification expert creating a DV test plan.
Generate comprehensive test cases with: name, priority (P0-P3), description,
stimulus, expected outcome, and coverage targets.
Cover: reset, basic transactions, protocol errors, boundary values, FIFO, FSMs.
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "goal_line_pct":   {"type": "number"},
        "goal_toggle_pct": {"type": "number"},
        "goal_branch_pct": {"type": "number"},
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":             {"type": "string"},
                    "priority":         {"type": "string", "enum": ["P0","P1","P2","P3"]},
                    "description":      {"type": "string"},
                    "stimulus":         {"type": "string"},
                    "expected":         {"type": "string"},
                    "coverage_targets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "priority", "description", "stimulus", "expected"],
            },
        },
    },
    "required": ["test_cases"],
}


class TestplanGen:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(8, "testplan")
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "DUT"
        user = f"DUT: {dut}\nSpec: {json.dumps(spec, indent=2)[:8000]}\nGenerate ≥20 test cases."
        data = structured_call(_SYSTEM, user, _SCHEMA, tier="gen")

        out = stage_dir / "testplan.json"
        out.write_text(json.dumps(data, indent=2))
        ctx.testplan = data

        n = len(data.get("test_cases", []))
        return StageResult(stage=8, name="testplan_gen", status="pass",
                           summary=f"Generated {n} test cases",
                           artifacts={"testplan": str(out)},
                           data={"count": n})
