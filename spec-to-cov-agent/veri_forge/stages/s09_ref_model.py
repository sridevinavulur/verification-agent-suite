"""Stage 9 — Reference Model Generator."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm.client import simple_call
from ..models import RunContext, StageResult

_SYSTEM = """\
Generate a Python reference model (golden model) for this hardware design.
The class should implement all transactions, register operations, and protocol checks.
Include a compare_transaction(actual, expected) method for scoreboarding.
Output ONLY valid Python code.
"""


class RefModelGen:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(9, "ref_model")
        spec = ctx.parsed_spec
        dut = spec.get("protocol", {}).get("name") or ctx.config.top or "DUT"
        user = (f"DUT: {dut}\nSpec: {json.dumps(spec, indent=2)[:6000]}\n"
                f"Transactions: {json.dumps(spec.get('transactions', []))[:2000]}")
        code = simple_call(_SYSTEM, user, tier="gen", max_tokens=6000)
        out = stage_dir / f"{dut.lower()}_ref_model.py"
        out.write_text(code)
        ctx.ref_model_file = str(out)
        return StageResult(stage=9, name="ref_model_gen", status="pass",
                           summary=f"Generated Python reference model for {dut}",
                           artifacts={"ref_model": str(out)})
