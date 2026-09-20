"""Stage 5 — Property Generator (SVA)."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
Generate SystemVerilog Assertions (SVA) for the described design.
Include: reset, protocol handshake, register access, FSM coverage, liveness.
Output ONLY valid SystemVerilog.
"""


class PropertyGen:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(5, "property_gen")
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "dut"
        user = f"DUT: {dut}\nSpec: {json.dumps(spec, indent=2)[:6000]}"
        sva = simple_call(_SYSTEM, user, tier="gen", max_tokens=5000)
        out = stage_dir / f"{dut}_props.sv"
        out.write_text(sva)
        ctx.sva_file = str(out)
        return StageResult(stage=5, name="property_gen", status="pass",
                           summary=f"Generated SVA properties for {dut}",
                           artifacts={"sva": str(out)})
