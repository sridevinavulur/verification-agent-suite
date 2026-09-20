"""Stage 3 — Lint Runner (Verilator --lint-only)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from ..models import RunContext, StageResult


class LintRunner:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(3, "lint")
        if not ctx.rtl_files:
            return StageResult(stage=3, name="lint_runner", status="skip",
                               summary="No RTL files to lint")
        try:
            proc = subprocess.run(
                ["verilator", "--lint-only", "--Wall"] + ctx.rtl_files,
                capture_output=True, text=True, timeout=60, cwd=str(stage_dir),
            )
            ok = proc.returncode == 0
            out_file = stage_dir / "lint.txt"
            out_file.write_text(proc.stdout + proc.stderr)
            status = "pass" if ok else "warn"
            return StageResult(stage=3, name="lint_runner", status=status,
                               summary=f"Lint {'clean' if ok else 'warnings/errors'}: {len(ctx.rtl_files)} file(s)",
                               artifacts={"lint_log": str(out_file)})
        except FileNotFoundError:
            return StageResult(stage=3, name="lint_runner", status="skip",
                               summary="verilator not found — lint skipped")
        except Exception as exc:
            return StageResult(stage=3, name="lint_runner", status="warn",
                               summary=f"Lint error: {exc}")
