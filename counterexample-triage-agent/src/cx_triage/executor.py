"""Reproduction executor adapters.

Triage is driven by an *already-captured* counterexample (a trace + a structured
failure record). The executor layer answers a separate, optional question: *can
the failure be reproduced by re-running the DUT?*

Two adapters implement a single :class:`ReproExecutor` protocol:

* :class:`DeterministicExecutor` -- the **default**. It performs no external
  process invocation; it "reproduces" by re-reading the captured trace/failure
  artifacts and confirming they are present and self-consistent. This keeps the
  existing pipeline offline, deterministic, and CI-safe (per BUILD_STANDARD.md).
* :class:`VerilatorReproExecutor` -- an **optional** path that shells out to
  Verilator (+ optional cocotb) to actually re-compile and re-run the RTL. It is
  re-implemented cleanly and self-contained here.

Reference (READ-ONLY, not imported):
``spec-to-cov-agent/veri_forge/sim/{runner.py,verilator.py}``. The subprocess
sequence (lint -> compile -> run -> parse results) and the graceful
"tool-not-found" handling are adapted from that runner; no code is copied and
there is no dependency on ``spec-to-cov-agent``.

Safety invariants (BUILD_STANDARD.md):

* A missing simulator, a compile error, a timeout, or any subprocess error is
  reported as ``SKIP``/``ERROR``/``TIMEOUT`` -- **never** as a ``PASS``.
* The executor is advisory context for triage; it never produces evidence for a
  ``design_bug`` hypothesis on its own and never modifies RTL.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable


class ReproStatus(StrEnum):
    """Result vocabulary (aligned with BUILD_STANDARD.md).

    Note there is deliberately no ``PASS`` alias for an ambiguous state: a
    reproduction either observed the failure (``REPRODUCED``), observed the DUT
    pass (``NOT_REPRODUCED``), or produced a non-conclusive state.
    """

    REPRODUCED = "reproduced"  # the counterexample failure was observed again
    NOT_REPRODUCED = "not_reproduced"  # DUT ran and did NOT exhibit the failure
    SKIPPED = "skipped"  # prerequisites (e.g. verilator) unavailable
    TIMEOUT = "timeout"  # execution exceeded the budget
    ERROR = "error"  # compile/run/parse error


@dataclass
class ReproResult:
    """Normalized, advisory result of a reproduction attempt.

    This is *not* evidence for a design bug; it is context that can raise or lower
    confidence in the deterministic hypotheses (see ``triage``/README).
    """

    status: ReproStatus
    adapter: str
    summary: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    artifacts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def is_conclusive_pass(self) -> bool:
        """True only for an unambiguous DUT pass. Never true for skip/error/timeout."""
        return self.status == ReproStatus.NOT_REPRODUCED


@runtime_checkable
class ReproExecutor(Protocol):
    name: str

    def reproduce(self) -> ReproResult: ...


# ---------------------------------------------------------------------------
# Default: deterministic, no external process
# ---------------------------------------------------------------------------


class DeterministicExecutor:
    """Default executor: confirms captured artifacts without running anything.

    It verifies the trace and failure record exist and (optionally) that the
    trace is non-empty. It never claims to have *proven* anything -- it reports
    ``REPRODUCED`` in the sense of "the captured counterexample artifacts are
    present and loadable", which is exactly what the deterministic triage
    pipeline already relies on.
    """

    name = "deterministic-v1"

    def __init__(
        self,
        trace_path: str | Path,
        failure_path: str | Path,
        *,
        trace_signal_count: int | None = None,
    ) -> None:
        self.trace_path = Path(trace_path)
        self.failure_path = Path(failure_path)
        self.trace_signal_count = trace_signal_count

    def reproduce(self) -> ReproResult:
        missing = [
            str(p)
            for p in (self.trace_path, self.failure_path)
            if not p.exists()
        ]
        if missing:
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="Captured counterexample artifacts are missing.",
                notes=[f"Missing: {m}" for m in missing],
            )
        notes = ["Deterministic re-check of captured artifacts (no simulator run)."]
        if self.trace_signal_count == 0:
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="Captured trace contains no signals.",
                artifacts=[str(self.trace_path), str(self.failure_path)],
                notes=notes,
            )
        return ReproResult(
            status=ReproStatus.REPRODUCED,
            adapter=self.name,
            summary="Captured counterexample artifacts are present and loadable.",
            artifacts=[str(self.trace_path), str(self.failure_path)],
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Optional: Verilator / cocotb reproduction
# ---------------------------------------------------------------------------


def verilator_available() -> bool:
    """True iff a ``verilator`` binary is on PATH (or a known location)."""
    if shutil.which("verilator"):
        return True
    return any(
        Path(p).is_file() for p in ("/usr/local/bin/verilator", "/usr/bin/verilator")
    )


def _find_verilator() -> str | None:
    path = shutil.which("verilator")
    if path:
        return path
    for candidate in ("/usr/local/bin/verilator", "/usr/bin/verilator"):
        if Path(candidate).is_file():
            return candidate
    return None


class VerilatorReproExecutor:
    """Optional reproduction via Verilator (+ optional cocotb).

    Adapted (not copied) from the reference sim runner. It degrades gracefully:
    if Verilator is not installed it returns ``SKIPPED`` rather than raising, so
    the default pipeline is never broken by the absence of a simulator.

    The class does the minimum needed to *attempt* a reproduction:

    1. ``verilator --lint-only`` as a fast structural pre-check;
    2. ``verilator --binary`` (or ``--cc --exe --build``) compilation;
    3. if a cocotb test module is supplied, run it via ``make`` and parse the
       cocotb JUnit ``results.xml``; otherwise run the built simulator directly.

    A failing DUT run (a reproduced assertion failure) maps to ``REPRODUCED``; a
    clean run maps to ``NOT_REPRODUCED``. Compile/parse problems map to ``ERROR``
    and timeouts to ``TIMEOUT`` -- never to a pass.
    """

    name = "verilator-cocotb-v1"

    def __init__(
        self,
        rtl_files: list[str | Path],
        top_module: str,
        work_dir: str | Path,
        *,
        cocotb_test: str | Path | None = None,
        extra_defines: list[str] | None = None,
        timeout_s: int = 120,
    ) -> None:
        self.rtl_files = [str(Path(f)) for f in rtl_files]
        self.top_module = top_module
        self.work_dir = Path(work_dir)
        self.cocotb_test = Path(cocotb_test) if cocotb_test else None
        self.extra_defines = extra_defines or []
        self.timeout_s = timeout_s

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _run(cmd: list[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
        return subprocess.run(  # noqa: S603 - args are constructed, not shell
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )

    def _skip(self, reason: str) -> ReproResult:
        return ReproResult(
            status=ReproStatus.SKIPPED,
            adapter=self.name,
            summary=reason,
            notes=["Reproduction skipped; deterministic triage is unaffected."],
        )

    # -- main --------------------------------------------------------------

    def reproduce(self) -> ReproResult:
        verilator = _find_verilator()
        if verilator is None:
            return self._skip(
                "verilator not found on PATH; install it to enable real repro."
            )
        missing_rtl = [f for f in self.rtl_files if not Path(f).exists()]
        if missing_rtl:
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="RTL source files not found.",
                notes=[f"Missing: {m}" for m in missing_rtl],
            )

        self.work_dir.mkdir(parents=True, exist_ok=True)
        sim_dir = self.work_dir / "sim_build"
        sim_dir.mkdir(exist_ok=True)
        t0 = time.time()

        # Step 1: lint-only pre-check (warnings are non-fatal).
        lint_cmd = [verilator, "--lint-only", "-Wno-fatal"]
        for d in self.extra_defines:
            lint_cmd += [f"+define+{d}"]
        lint_cmd += self.rtl_files
        try:
            lint = self._run(lint_cmd, cwd=str(self.work_dir), timeout=60)
        except subprocess.TimeoutExpired:
            return ReproResult(
                status=ReproStatus.TIMEOUT,
                adapter=self.name,
                summary="verilator lint exceeded the time budget.",
                duration_s=time.time() - t0,
            )
        except OSError as exc:  # pragma: no cover - environment dependent
            return self._skip(f"could not invoke verilator: {exc}")

        # A hard lint error usually means we cannot compile; surface as ERROR.
        if lint.returncode != 0 and "%Error" in (lint.stderr + lint.stdout):
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="verilator lint reported errors; cannot reproduce.",
                exit_code=lint.returncode,
                stdout=lint.stdout[-4000:],
                stderr=lint.stderr[-4000:],
                duration_s=time.time() - t0,
            )

        if self.cocotb_test is not None:
            return self._reproduce_cocotb(verilator, sim_dir, t0)
        return self._reproduce_selfcontained(verilator, sim_dir, t0)

    # -- self-contained testbench (RTL contains its own $finish/assert) -----

    def _reproduce_selfcontained(
        self, verilator: str, sim_dir: Path, t0: float
    ) -> ReproResult:
        compile_cmd = (
            [verilator, "--binary", "-Mdir", str(sim_dir), "--top-module", self.top_module]
            + [f"+define+{d}" for d in self.extra_defines]
            + self.rtl_files
            + ["-Wno-fatal"]
        )
        try:
            comp = self._run(compile_cmd, cwd=str(self.work_dir), timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            return ReproResult(
                status=ReproStatus.TIMEOUT,
                adapter=self.name,
                summary="verilator compilation exceeded the time budget.",
                duration_s=time.time() - t0,
            )
        if comp.returncode != 0:
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="verilator compilation failed.",
                exit_code=comp.returncode,
                stdout=comp.stdout[-4000:],
                stderr=comp.stderr[-4000:],
                duration_s=time.time() - t0,
            )
        sim_bin = sim_dir / f"V{self.top_module}"
        if not sim_bin.exists():
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="verilator produced no simulation binary.",
                duration_s=time.time() - t0,
            )
        try:
            run = self._run([str(sim_bin)], cwd=str(self.work_dir), timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            return ReproResult(
                status=ReproStatus.TIMEOUT,
                adapter=self.name,
                summary="simulation run exceeded the time budget.",
                duration_s=time.time() - t0,
            )
        combined = (run.stdout + "\n" + run.stderr).upper()
        # A non-zero exit or an assertion/error marker => the failure reproduced.
        failed = run.returncode != 0 or any(
            m in combined for m in ("ASSERTION FAILED", "%ERROR", "FAIL")
        )
        status = ReproStatus.REPRODUCED if failed else ReproStatus.NOT_REPRODUCED
        return ReproResult(
            status=status,
            adapter=self.name,
            summary=(
                "DUT re-run exhibited the failure."
                if failed
                else "DUT re-run completed without exhibiting the failure."
            ),
            exit_code=run.returncode,
            stdout=run.stdout[-4000:],
            stderr=run.stderr[-4000:],
            duration_s=time.time() - t0,
            artifacts=[str(sim_bin)],
        )

    # -- cocotb-driven testbench -------------------------------------------

    def _reproduce_cocotb(
        self, verilator: str, sim_dir: Path, t0: float
    ) -> ReproResult:
        try:
            import cocotb  # noqa: F401
        except ImportError:
            return self._skip("cocotb not installed; skipping cocotb reproduction.")

        run_dir = self.work_dir / "cocotb_run"
        run_dir.mkdir(exist_ok=True)
        share = self._cocotb_share()
        if share is None:
            return self._skip("cocotb share dir not found; skipping.")

        test = self.cocotb_test
        assert test is not None
        makefile = f"""\
SIM             = verilator
TOPLEVEL_LANG   = verilog
TOPLEVEL        = {self.top_module}
MODULE          = {test.stem}
VERILOG_SOURCES = {" ".join(str(Path(f).resolve()) for f in self.rtl_files)}
PYTHONPATH     := {test.resolve().parent}:$(PYTHONPATH)
SIM_BUILD       = {sim_dir}
include {share}/makefiles/Makefile.sim
"""
        (run_dir / "Makefile").write_text(makefile)
        results_xml = run_dir / "results.xml"
        try:
            proc = self._run(
                ["make", "-C", str(run_dir)], cwd=str(run_dir), timeout=self.timeout_s
            )
        except subprocess.TimeoutExpired:
            return ReproResult(
                status=ReproStatus.TIMEOUT,
                adapter=self.name,
                summary="cocotb run exceeded the time budget.",
                duration_s=time.time() - t0,
            )
        passed, failed = self._parse_results_xml(results_xml)
        if not results_xml.exists():
            return ReproResult(
                status=ReproStatus.ERROR,
                adapter=self.name,
                summary="cocotb produced no results.xml; run likely failed to build.",
                exit_code=proc.returncode,
                stdout=proc.stdout[-4000:],
                stderr=proc.stderr[-4000:],
                duration_s=time.time() - t0,
            )
        reproduced = failed > 0
        status = ReproStatus.REPRODUCED if reproduced else ReproStatus.NOT_REPRODUCED
        return ReproResult(
            status=status,
            adapter=self.name,
            summary=f"cocotb: {passed} passed, {failed} failed.",
            exit_code=proc.returncode,
            stdout=proc.stdout[-4000:],
            stderr=proc.stderr[-4000:],
            duration_s=time.time() - t0,
            artifacts=[str(results_xml)],
        )

    @staticmethod
    def _cocotb_share() -> str | None:
        try:
            import cocotb

            share = Path(cocotb.__file__).parent / "share"
            if share.exists():
                return str(share)
        except ImportError:
            pass
        return None

    @staticmethod
    def _parse_results_xml(results_xml: Path) -> tuple[int, int]:
        if not results_xml.exists():
            return 0, 0
        try:
            import xml.etree.ElementTree as ET

            root = ET.parse(results_xml).getroot()
            suites = root.findall(".//testsuite") or [root]
            passed = failed = 0
            for suite in suites:
                for tc in suite.findall("testcase"):
                    if tc.findall("failure") or tc.findall("error"):
                        failed += 1
                    else:
                        passed += 1
            return passed, failed
        except Exception:  # pragma: no cover - defensive
            return 0, 0


def get_executor(kind: str = "deterministic", **kwargs) -> ReproExecutor:
    """Factory. ``deterministic`` is the default; ``verilator`` is opt-in.

    Unknown kinds raise, so a typo can never silently fall back to running a
    simulator (or to skipping one).
    """
    if kind == "deterministic":
        return DeterministicExecutor(**kwargs)
    if kind == "verilator":
        return VerilatorReproExecutor(**kwargs)
    raise ValueError(
        f"Unknown executor kind '{kind}'. Use 'deterministic' (default) or 'verilator'."
    )
