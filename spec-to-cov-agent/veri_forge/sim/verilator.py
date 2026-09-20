"""Verilator + cocotb simulation executor.

Runs a cocotb test suite under Verilator and returns a SimResult.
The caller supplies:
  - top_module: Verilog top-level module name
  - rtl_files: list of .v/.sv source files
  - test_file: path to the cocotb test Python file (MODULE= value)
  - work_dir: directory where build artefacts are written

Coverage is collected via Verilator's --coverage flag + lcov export.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from ..models import SimResult


def _run(cmd: List[str], cwd: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _find_verilator() -> str:
    path = shutil.which("verilator")
    if path:
        return path
    for candidate in ["/usr/local/bin/verilator", "/usr/bin/verilator"]:
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "verilator not found. Install with: apt install verilator  or  brew install verilator"
    )


def _find_python() -> str:
    for name in ["python3", "python"]:
        p = shutil.which(name)
        if p:
            return p
    return "python3"


def run_verilator_cocotb(
    top_module: str,
    rtl_files: List[str],
    test_file: str,
    work_dir: str,
    *,
    extra_defines: Optional[List[str]] = None,
    extra_include_dirs: Optional[List[str]] = None,
    timeout_s: int = 300,
    coverage: bool = True,
) -> SimResult:
    """Compile RTL with Verilator and run cocotb tests. Returns SimResult."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    verilator = _find_verilator()
    python_bin = _find_python()
    test_path = Path(test_file).resolve()
    test_module = test_path.stem   # filename without .py

    sim_dir = work / "sim_build"
    sim_dir.mkdir(exist_ok=True)

    defines = extra_defines or []
    includes = extra_include_dirs or []

    # ── Step 1: verilator --lint-only (fast pre-check) ──────────────────────
    t0 = time.time()
    lint_cmd = [verilator, "--lint-only", "--Wall"] + [f"-I{i}" for i in includes]
    for d in defines:
        lint_cmd += ["-D", d]
    lint_cmd += rtl_files
    lint_proc = _run(lint_cmd, cwd=str(work), timeout=60)
    # lint warnings are non-fatal

    # ── Step 2: verilator compilation ──────────────────────────────────────
    cov_flags = ["--coverage"] if coverage else []
    compile_cmd = (
        [verilator, "-Mdir", str(sim_dir), "--cc", "--exe", "--build"]
        + cov_flags
        + ["--top-module", top_module]
        + [f"-I{i}" for i in includes]
        + [f"+define+{d}" for d in defines]
        + rtl_files
        + ["-CFLAGS", "-DVL_USER_FINISH", "--Wall", "-Wno-DECLFILENAME"]
    )
    compile_proc = _run(compile_cmd, cwd=str(work), timeout=120)
    compile_time = time.time() - t0

    if compile_proc.returncode != 0:
        return SimResult(
            success=False,
            exit_code=compile_proc.returncode,
            stdout=compile_proc.stdout,
            stderr=compile_proc.stderr,
            compile_time_s=compile_time,
            error_message="Verilator compilation failed",
        )

    # ── Step 3: run via cocotb Makefile ─────────────────────────────────────
    cocotb_make_dir = work / "cocotb_run"
    cocotb_make_dir.mkdir(exist_ok=True)

    # Generate a minimal cocotb Makefile
    cocotb_share = _find_cocotb_share()
    makefile_content = f"""\
SIM          = verilator
TOPLEVEL     = {top_module}
MODULE       = {test_module}
VERILOG_SOURCES = {" ".join(str(Path(f).resolve()) for f in rtl_files)}
PYTHONPATH   := {test_path.parent}:$(PYTHONPATH)
SIM_BUILD    = {sim_dir}
"""
    if coverage:
        makefile_content += "VERILATOR_ARGS += --coverage\n"
    if cocotb_share:
        makefile_content += f"\ninclude {cocotb_share}/makefiles/Makefile.sim\n"

    (cocotb_make_dir / "Makefile").write_text(makefile_content)

    t1 = time.time()
    results_xml = str(cocotb_make_dir / "results.xml")
    env = {**os.environ, "COCOTB_RESULTS_FILE": results_xml}

    make_proc = _run(
        ["make", "-f", str(cocotb_make_dir / "Makefile"), "-C", str(cocotb_make_dir)],
        cwd=str(cocotb_make_dir),
        timeout=timeout_s,
    )
    sim_time = time.time() - t1

    log_file = str(cocotb_make_dir / "sim.log")
    (cocotb_make_dir / "sim.log").write_text(
        make_proc.stdout + "\n--- STDERR ---\n" + make_proc.stderr
    )

    # ── Step 4: parse results.xml ────────────────────────────────────────────
    passed, failed = _parse_results_xml(results_xml)
    success = make_proc.returncode == 0 and failed == 0

    # ── Step 5: collect coverage.dat location ───────────────────────────────
    cov_dat = _find_coverage_dat(sim_dir, cocotb_make_dir)

    return SimResult(
        success=success,
        exit_code=make_proc.returncode,
        tests_passed=passed,
        tests_failed=failed,
        stdout=make_proc.stdout[-8000:],
        stderr=make_proc.stderr[-4000:],
        results_xml=results_xml if Path(results_xml).exists() else None,
        coverage_dat=str(cov_dat) if cov_dat else None,
        log_file=log_file,
        compile_time_s=compile_time,
        sim_time_s=sim_time,
        error_message=None if success else "Tests failed",
    )


def _find_cocotb_share() -> Optional[str]:
    """Find cocotb share directory via pip or importlib."""
    try:
        import importlib.resources
        import cocotb
        share = Path(cocotb.__file__).parent / "share"
        if share.exists():
            return str(share)
    except ImportError:
        pass
    # Try pip show
    try:
        r = subprocess.run(["pip", "show", "cocotb"], capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            if line.startswith("Location:"):
                loc = Path(line.split(":", 1)[1].strip()) / "cocotb" / "share"
                if loc.exists():
                    return str(loc)
    except Exception:
        pass
    return None


def _parse_results_xml(results_xml: str) -> tuple[int, int]:
    """Parse cocotb JUnit XML; returns (passed, failed)."""
    p = Path(results_xml)
    if not p.exists():
        return 0, 0
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(p)
        root = tree.getroot()
        suites = root.findall(".//testsuite") or [root]
        passed = failed = 0
        for suite in suites:
            for tc in suite.findall("testcase"):
                if tc.findall("failure") or tc.findall("error"):
                    failed += 1
                else:
                    passed += 1
        return passed, failed
    except Exception:
        return 0, 0


def _find_coverage_dat(sim_dir: Path, run_dir: Path) -> Optional[Path]:
    """Find coverage.dat produced by Verilator."""
    for d in [sim_dir, run_dir]:
        for f in d.rglob("coverage.dat"):
            return f
    return None
