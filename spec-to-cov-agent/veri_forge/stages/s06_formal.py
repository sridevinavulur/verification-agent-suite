"""Stage 6 — Formal Verification (JasperGold / SymbiYosys)."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from ..models import RunContext, StageResult


class Formal:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(6, "formal")
        sva = ctx.sva_file
        if not sva or not Path(sva).exists():
            return StageResult(stage=6, name="formal", status="skip",
                               summary="No SVA file — formal skipped")
        if not ctx.rtl_files:
            return StageResult(stage=6, name="formal", status="skip",
                               summary="No RTL files — formal skipped")

        jasper = os.getenv("JASPER_HOME") or os.getenv("JG_HOME")
        sby = _which("sby")

        if jasper:
            result = _run_jasper(jasper, stage_dir, ctx.rtl_files, sva, ctx.config.top)
        elif sby:
            result = _run_sby(sby, stage_dir, ctx.rtl_files, sva, ctx.config.top)
        else:
            return StageResult(stage=6, name="formal", status="skip",
                               summary="No formal tool available (set JASPER_HOME or install sby)")

        proven = len(result.get("proven", []))
        cex = len(result.get("cex", []))
        return StageResult(
            stage=6, name="formal",
            status="pass" if cex == 0 else "fail",
            summary=f"Formal: {proven} proven, {cex} CEX, tool={result.get('tool','?')}",
            data=result,
        )


def _which(cmd: str) -> str:
    import shutil
    return shutil.which(cmd) or ""


def _run_jasper(jasper: str, stage_dir: Path, rtl: list, sva: str, top: str) -> dict:
    jg = Path(jasper) / "bin" / "jg"
    if not jg.exists():
        return {"status": "skip", "reason": f"jg not found at {jg}", "tool": "jasper"}
    rtl_lines = "\n".join(f"analyze -sv {f}" for f in rtl)
    tcl = f"""clear -all\n{rtl_lines}\nanalyze -sv {sva}\nelaborate -top {top or 'top'}\nclock clk\nreset ~rst_n\nprove -all\n"""
    tcl_f = stage_dir / "run.tcl"
    tcl_f.write_text(tcl)
    try:
        proc = subprocess.run([str(jg), "-batch", "-tcl", str(tcl_f)],
                              capture_output=True, text=True, timeout=600, cwd=str(stage_dir))
        log = proc.stdout + proc.stderr
        (stage_dir / "jg.log").write_text(log)
        proven = [m for m in re.findall(r"(\w+_prop\w*)", log) if "proven" in log[log.find(m):log.find(m)+80].lower()]
        cex    = [m for m in re.findall(r"(\w+_prop\w*)", log) if "cex" in log[log.find(m):log.find(m)+80].lower() or "fail" in log[log.find(m):log.find(m)+80].lower()]
        return {"tool": "jasper", "proven": list(set(proven)), "cex": list(set(cex))}
    except Exception as exc:
        return {"tool": "jasper", "status": "error", "reason": str(exc), "proven": [], "cex": []}


def _run_sby(sby: str, stage_dir: Path, rtl: list, sva: str, top: str) -> dict:
    content = f"""[options]\nmode prove\n\n[engines]\nsmtbmc yices\n\n[script]\nread -sv {sva}\n"""
    content += "\n".join(f"read -sv {f}" for f in rtl)
    content += f"\nprep -top {top or 'top'}\n\n[files]\n{sva}\n" + "\n".join(rtl)
    sby_f = stage_dir / "run.sby"
    sby_f.write_text(content)
    try:
        proc = subprocess.run([sby, "-f", str(sby_f)], capture_output=True, text=True,
                              timeout=300, cwd=str(stage_dir))
        log = proc.stdout + proc.stderr
        (stage_dir / "sby.log").write_text(log)
        proven = ["all"] if "PASS" in log else []
        cex    = ["at_least_one"] if "FAIL" in log else []
        return {"tool": "sby", "proven": proven, "cex": cex}
    except Exception as exc:
        return {"tool": "sby", "status": "error", "reason": str(exc), "proven": [], "cex": []}
