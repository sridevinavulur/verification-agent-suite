"""Stage 11 — cocotb VIP / BFM Generator."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
You are a cocotb expert. Generate Python BFM (Bus Functional Model) classes.
Each BFM:
  - Accepts a `dut` cocotb handle
  - Implements async read/write/transaction methods with correct timing
  - Includes fault injection (bad_crc, timeout, reserved_values)
  - Includes a Monitor class for scoreboarding
Output ONLY valid Python code using cocotb.
"""


class CocotbVipGen:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(11, "cocotb_vip")
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "DUT"
        ifaces = json.dumps(spec.get("interfaces", []), indent=2)[:3000]
        txns   = json.dumps(spec.get("transactions", []), indent=2)[:2000]
        proto  = json.dumps(spec.get("protocol", {}), indent=2)[:1500]
        user = f"DUT: {dut}\nProtocol: {proto}\nInterfaces: {ifaces}\nTransactions: {txns}"
        code = simple_call(_SYSTEM, user, tier="gen", max_tokens=8000)
        out = stage_dir / f"{dut.lower()}_bfm.py"
        out.write_text(code)
        ctx.bfm_file = str(out)
        return StageResult(stage=11, name="cocotb_vip_gen", status="pass",
                           summary=f"Generated cocotb BFMs for {dut}",
                           artifacts={"bfm": str(out)})
