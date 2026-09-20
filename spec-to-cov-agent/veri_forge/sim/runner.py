"""SimRunner — unified simulation backend for veri-forge.

Dispatches to Verilator (default), VCS, or Xcelium based on config.
Wraps the low-level run_verilator_cocotb() function and normalizes the result
into a SimRunResult that CoverageParser can consume.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .verilator import run_verilator_cocotb


@dataclass
class SimRunResult:
    """Normalized result from any simulator backend."""
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    compile_time_s: float = 0.0
    sim_time_s: float = 0.0
    log_path: Optional[str] = None
    vcd_path: Optional[str] = None
    lcov_path: Optional[str] = None
    coverage_dat_path: Optional[str] = None
    results_xml_path: Optional[str] = None
    tests_passed: int = 0
    tests_failed: int = 0
    error_message: Optional[str] = None


class SimRunner:
    """Dispatcher — creates the correct backend based on `simulator` arg."""

    def run_simulation(
        self,
        rtl_files: List[Path],
        test_file: Path,
        top: str,
        out_dir: Path,
        simulator: str = "verilator",
        extra_defines: Optional[List[str]] = None,
        timeout_s: int = 300,
    ) -> SimRunResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        sim = simulator.lower()

        if sim == "verilator":
            return self._verilator(rtl_files, test_file, top, out_dir, extra_defines, timeout_s)
        elif sim in ("vcs", "vcssim"):
            return self._vcs(rtl_files, test_file, top, out_dir, timeout_s)
        elif sim in ("xcelium", "xrun"):
            return self._xcelium(rtl_files, test_file, top, out_dir, timeout_s)
        else:
            return SimRunResult(success=False, exit_code=-1,
                                error_message=f"Unknown simulator: {simulator!r}")

    def _verilator(
        self,
        rtl_files: List[Path],
        test_file: Path,
        top: str,
        out_dir: Path,
        extra_defines: Optional[List[str]],
        timeout_s: int,
    ) -> SimRunResult:
        result = run_verilator_cocotb(
            top_module=top,
            rtl_files=[str(f) for f in rtl_files],
            test_file=str(test_file),
            work_dir=str(out_dir),
            extra_defines=extra_defines,
            timeout_s=timeout_s,
            coverage=True,
        )
        return SimRunResult(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            compile_time_s=result.compile_time_s,
            sim_time_s=result.sim_time_s,
            log_path=result.log_file,
            coverage_dat_path=result.coverage_dat,
            results_xml_path=result.results_xml,
            tests_passed=result.tests_passed,
            tests_failed=result.tests_failed,
            error_message=result.error_message,
        )

    def _vcs(self, rtl_files, test_file, top, out_dir, timeout_s) -> SimRunResult:
        vcs_home = os.getenv("VCS_HOME", "")
        vcs = str(Path(vcs_home) / "bin" / "vcs") if vcs_home else "vcs"
        t0 = time.time()
        try:
            cp = subprocess.run(
                [vcs, "-full64", "-sverilog", f"-top={top}", "-cm", "line+tgl+branch"]
                + [str(f) for f in rtl_files],
                capture_output=True, text=True, timeout=120, cwd=str(out_dir),
            )
            if cp.returncode != 0:
                return SimRunResult(False, cp.returncode, cp.stdout, cp.stderr,
                                    compile_time_s=time.time()-t0, error_message="VCS compile failed")
            env = {**os.environ, "COCOTB_RESULTS_FILE": str(out_dir / "results.xml"),
                   "MODULE": test_file.stem, "PYTHONPATH": str(test_file.parent)}
            sp = subprocess.run([str(out_dir / "simv")], env=env, capture_output=True,
                                text=True, timeout=timeout_s, cwd=str(out_dir))
            from .verilator import _parse_results_xml
            p, f = _parse_results_xml(str(out_dir / "results.xml"))
            return SimRunResult(sp.returncode == 0 and f == 0, sp.returncode,
                                sp.stdout[-6000:], sp.stderr[-2000:],
                                compile_time_s=time.time()-t0, sim_time_s=time.time()-t0,
                                tests_passed=p, tests_failed=f)
        except Exception as e:
            return SimRunResult(False, -1, error_message=str(e))

    def _xcelium(self, rtl_files, test_file, top, out_dir, timeout_s) -> SimRunResult:
        xhome = os.getenv("XCELIUM_HOME", "")
        xrun = str(Path(xhome) / "tools" / "bin" / "xrun") if xhome else "xrun"
        env = {**os.environ, "COCOTB_RESULTS_FILE": str(out_dir / "results.xml"),
               "MODULE": test_file.stem, "PYTHONPATH": str(test_file.parent)}
        t0 = time.time()
        try:
            proc = subprocess.run(
                [xrun, "-sv", "-coverage", "all", f"-top={top}"]
                + [str(f) for f in rtl_files] + [str(test_file)],
                env=env, capture_output=True, text=True, timeout=timeout_s, cwd=str(out_dir),
            )
            from .verilator import _parse_results_xml
            p, f = _parse_results_xml(str(out_dir / "results.xml"))
            return SimRunResult(proc.returncode == 0 and f == 0, proc.returncode,
                                proc.stdout[-6000:], proc.stderr[-2000:],
                                sim_time_s=time.time()-t0, tests_passed=p, tests_failed=f)
        except Exception as e:
            return SimRunResult(False, -1, error_message=str(e))
