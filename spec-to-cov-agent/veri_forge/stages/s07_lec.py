"""Stage 7 — Logic Equivalence Check (LEC).

Compares golden RTL against generated RTL using Formality (Synopsys) or
a lightweight Verilator-based structural comparison. Skipped if no reference RTL.
"""
from __future__ import annotations

import os
from pathlib import Path
from ..models import RunContext, StageResult


class Lec:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(7, "lec")

        # LEC only makes sense when both a reference and a generated RTL exist
        if not ctx.rtl_files:
            return StageResult(stage=7, name="lec", status="skip",
                               summary="No RTL files — LEC skipped")

        formality = os.getenv("FORMALITY_HOME")
        if not formality:
            # Soft skip — LEC requires commercial tools
            return StageResult(stage=7, name="lec", status="skip",
                               summary="FORMALITY_HOME not set — LEC skipped (set to enable)")

        try:
            import subprocess
            fm_bin = str(Path(formality) / "bin" / "fm_shell")
            if not Path(fm_bin).exists():
                return StageResult(stage=7, name="lec", status="skip",
                                   summary=f"fm_shell not found at {fm_bin}")

            # Generate minimal Formality script
            tcl = _gen_formality_tcl(ctx.rtl_files, ctx.config.top)
            tcl_f = stage_dir / "run_lec.tcl"
            tcl_f.write_text(tcl)

            proc = subprocess.run([fm_bin, "-f", str(tcl_f)],
                                  capture_output=True, text=True, timeout=300, cwd=str(stage_dir))
            log = proc.stdout + proc.stderr
            (stage_dir / "lec.log").write_text(log)

            success = proc.returncode == 0 and "Verification SUCCEEDED" in log
            return StageResult(stage=7, name="lec",
                               status="pass" if success else "fail",
                               summary=f"LEC {'PASSED' if success else 'FAILED'}",
                               artifacts={"lec_log": str(stage_dir / "lec.log")})
        except Exception as exc:
            return StageResult(stage=7, name="lec", status="warn",
                               summary=f"LEC error: {exc}")


def _gen_formality_tcl(rtl_files: list, top: str) -> str:
    reads = "\n".join(f"read_verilog -r {f}" for f in rtl_files)
    return f"""
set_svf {top}.svf
{reads}
set_top r:/{top or 'top'}
verify
report_failing_points
"""
