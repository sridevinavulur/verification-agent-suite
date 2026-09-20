"""Stage 10 — UVM VIP Generator.

Generates SystemVerilog UVM VIP components (agent, driver, monitor, sequencer,
sequence, coverage collector) for each interface in the parsed spec.
Requires VCS or Xcelium for compilation; skipped otherwise.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
You are a UVM expert. Generate a complete UVM VIP package for the described interface.
Include: uvm_sequence_item, uvm_driver, uvm_monitor, uvm_sequencer, uvm_agent,
uvm_scoreboard, and a base uvm_sequence. Use proper UVM macros and phasing.
Output ONLY valid SystemVerilog code.
"""


class UvmVipGen:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(10, "uvm_vip")

        # UVM is only useful with VCS/Xcelium
        has_uvm_sim = os.getenv("VCS_HOME") or os.getenv("XCELIUM_HOME")
        if not has_uvm_sim:
            return StageResult(stage=10, name="uvm_vip_gen", status="skip",
                               summary="VCS/Xcelium not detected — UVM VIP generation skipped")

        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "DUT"
        ifaces = json.dumps(spec.get("interfaces", []), indent=2)[:3000]
        user = f"DUT: {dut}\nInterfaces: {ifaces}\nGenerate complete UVM VIP package."
        code = simple_call(_SYSTEM, user, tier="gen", max_tokens=8000)
        out = stage_dir / f"{dut.lower()}_uvm_vip.sv"
        out.write_text(code)

        return StageResult(stage=10, name="uvm_vip_gen", status="pass",
                           summary=f"Generated UVM VIP for {dut}",
                           artifacts={"uvm_vip": str(out)})
