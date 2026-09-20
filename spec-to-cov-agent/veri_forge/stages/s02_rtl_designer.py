"""Stage 2 — RTL Designer.

If rtl_dir is set, discovers existing RTL files and populates ctx.rtl_files.
If no RTL exists, uses the LLM to generate a synthesizable Verilog skeleton
from the parsed spec.
"""
from __future__ import annotations

from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
You are an RTL designer. Generate clean, synthesizable Verilog for the described design.
Include: all I/O ports, register declarations, FSM, and clock/reset logic.
Output ONLY valid Verilog code.
"""


class RtlDesigner:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(2, "rtl_designer")

        # Discover existing RTL
        if ctx.config.rtl_dir and ctx.config.rtl_dir.exists():
            found = []
            for ext in ("*.v", "*.sv"):
                found.extend(str(f) for f in ctx.config.rtl_dir.rglob(ext))
            if found:
                ctx.rtl_files = found
                return StageResult(stage=2, name="rtl_designer", status="pass",
                                   summary=f"Found {len(found)} RTL file(s) in {ctx.config.rtl_dir}",
                                   data={"rtl_files": found})

        # Generate RTL from spec
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "dut"
        import json
        user = f"DUT: {dut}\nSpec: {json.dumps(spec, indent=2)[:6000]}\nGenerate Verilog module."
        code = simple_call(_SYSTEM, user, tier="gen", max_tokens=6000)

        out = stage_dir / f"{dut}.v"
        out.write_text(code)
        ctx.rtl_files = [str(out)]
        if not ctx.config.top:
            ctx.config.top = dut

        return StageResult(stage=2, name="rtl_designer", status="pass",
                           summary=f"Generated RTL skeleton for {dut}",
                           artifacts={"rtl": str(out)},
                           data={"rtl_files": [str(out)]})
