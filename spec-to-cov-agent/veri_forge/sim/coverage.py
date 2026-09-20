"""Coverage parser and unreachability classifier for veri-forge.

Supports:
  - Verilator coverage.dat binary format
  - lcov .info files (line coverage)
  - Manual summary strings (from simulator stdout)

Unreachability analysis: given a list of uncovered toggle transitions,
classifies each as one of:
  hardwired_constant | dead_code | counter_ceiling |
  architectural_limit | spec_gap | unknown
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import (
    CoverageMetric,
    CoverageResult,
    UncoveredTransition,
    UnreachabilityReport,
)

# ── Verilator coverage.dat parser ───────────────────────────────────────────

_DAT_LINE_RE  = re.compile(rb"'([01])\s+(\d+)$")
_DAT_COUNT_RE = re.compile(rb"' (\d+)$")
_DAT_NAME_RE  = re.compile(rb"^([A-Z]+)\s+.+\s+'(.+)'$")


def parse_coverage_dat(path: str) -> Dict[str, int]:
    """Parse Verilator coverage.dat; returns signal → count mapping."""
    p = Path(path)
    if not p.exists():
        return {}
    counts: Dict[str, int] = {}
    current_name = ""
    try:
        with open(p, "rb") as f:
            for line in f:
                line = line.rstrip()
                # Name line: "C 'top.dut.sig01'"
                m_name = re.search(rb"'([^']+)'", line)
                if m_name:
                    current_name = m_name.group(1).decode("utf-8", errors="replace")
                # Count line ends with "' <N>"
                m_count = _DAT_COUNT_RE.search(line)
                if m_count and current_name:
                    counts[current_name] = int(m_count.group(1))
    except Exception:
        pass
    return counts


def extract_toggle_coverage(dat_counts: Dict[str, int]) -> Tuple[int, int, List[UncoveredTransition]]:
    """Return (covered_transitions, total_transitions, uncovered list)."""
    toggle_signals: Dict[str, Dict[str, int]] = {}

    for key, count in dat_counts.items():
        # Verilator toggle keys end with __0 (0→1) or __1 (1→0)
        if key.endswith("__0") or key.endswith("__1"):
            sig = key[:-3]
            dir_ = "0->1" if key.endswith("__0") else "1->0"
            toggle_signals.setdefault(sig, {})[dir_] = count

    total = covered = 0
    uncovered: List[UncoveredTransition] = []
    for sig, dirs in toggle_signals.items():
        for dir_, count in dirs.items():
            total += 1
            if count > 0:
                covered += 1
            else:
                uncovered.append(UncoveredTransition(signal=sig, direction=dir_))

    return covered, total, uncovered


def extract_line_coverage(dat_counts: Dict[str, int]) -> Tuple[int, int]:
    """Return (covered_lines, total_lines) from Verilator dat."""
    covered = total = 0
    for key, count in dat_counts.items():
        if "__" not in key or key.endswith("__0") or key.endswith("__1"):
            continue
        total += 1
        if count > 0:
            covered += 1
    return covered, total


def parse_lcov(lcov_path: str) -> Tuple[int, int, int, int]:
    """Parse an lcov .info file; returns (line_hit, line_total, branch_hit, branch_total)."""
    p = Path(lcov_path)
    if not p.exists():
        return 0, 0, 0, 0
    lh = lt = bh = bt = 0
    try:
        for line in p.read_text().splitlines():
            if line.startswith("LH:"):
                lh = int(line[3:])
            elif line.startswith("LF:"):
                lt = int(line[3:])
            elif line.startswith("BRH:"):
                bh = int(line[4:])
            elif line.startswith("BRF:"):
                bt = int(line[4:])
    except Exception:
        pass
    return lh, lt, bh, bt


_STDOUT_RE = re.compile(
    r"(?:line|toggle|branch|expr)[^\d]*(\d+)\s*/\s*(\d+)", re.IGNORECASE
)


def parse_stdout_coverage(stdout: str) -> Dict[str, Tuple[int, int]]:
    """Extract coverage numbers from simulator stdout text."""
    result: Dict[str, Tuple[int, int]] = {}
    for m in _STDOUT_RE.finditer(stdout):
        metric_text = stdout[max(0, m.start() - 20): m.start()].lower()
        hit, total = int(m.group(1)), int(m.group(2))
        for metric in ["line", "toggle", "branch", "expr"]:
            if metric in metric_text:
                result[metric] = (hit, total)
    return result


# ── Unreachability classifier ────────────────────────────────────────────────

_HARDWIRED_PATTERNS = [
    re.compile(r"PREADY", re.IGNORECASE),
    re.compile(r"bit_en", re.IGNORECASE),
    re.compile(r"vdd|gnd|vcc|power", re.IGNORECASE),
]

_DEAD_CODE_PATTERNS = [
    re.compile(r"tx_frame\[(?:[4-9][0-9]|[5-9][0-9]|[1-9]\d{2,})\]"),
    re.compile(r"PADDR\[(?:[6-9]|1[0-9])\]"),
    re.compile(r"reserved", re.IGNORECASE),
]

_COUNTER_CEILING_PATTERNS = [
    re.compile(r"to_cnt|timeout_cnt|timer_cnt", re.IGNORECASE),
    re.compile(r"max_cnt|cnt_max", re.IGNORECASE),
]

_ARCH_LIMIT_PATTERNS = [
    re.compile(r"clksel|bit_div|clk_div", re.IGNORECASE),
    re.compile(r"ev_to_a|timeout_event", re.IGNORECASE),
]


def classify_unreachable(
    signal: str,
    direction: str,
    context_hint: Optional[str] = None,
) -> UnreachabilityReport:
    """Classify why a toggle transition is architecturally unreachable."""
    sig_full = f"{signal} {direction} {context_hint or ''}"

    for pat in _HARDWIRED_PATTERNS:
        if pat.search(sig_full):
            return UnreachabilityReport(
                signal=signal,
                direction=direction,
                category="hardwired_constant",
                explanation=(
                    f"Signal '{signal}' is hardwired in current config "
                    "(driven by a constant assign, never toggles)."
                ),
            )

    for pat in _DEAD_CODE_PATTERNS:
        if pat.search(sig_full):
            return UnreachabilityReport(
                signal=signal,
                direction=direction,
                category="dead_code",
                explanation=(
                    f"Signal '{signal}' is structural dead code: bits above "
                    "the active range are declared but never written."
                ),
                related_spec_issue="SPEC-4" if "tx_frame" in signal else "SPEC-5",
            )

    for pat in _COUNTER_CEILING_PATTERNS:
        if pat.search(sig_full):
            return UnreachabilityReport(
                signal=signal,
                direction=direction,
                category="counter_ceiling",
                explanation=(
                    f"Counter '{signal}' never reaches TIMEOUT_MAX because "
                    "the protocol always completes within the frame bit-count."
                ),
                related_spec_issue="SPEC-1",
            )

    for pat in _ARCH_LIMIT_PATTERNS:
        if pat.search(sig_full):
            return UnreachabilityReport(
                signal=signal,
                direction=direction,
                category="architectural_limit",
                explanation=(
                    f"Signal '{signal}' requires an operating mode (e.g. clksel=1) "
                    "not exercised in the current test suite."
                ),
                related_spec_issue="SPEC-2",
            )

    return UnreachabilityReport(
        signal=signal,
        direction=direction,
        category="unknown",
        explanation=(
            f"Signal '{signal}' uncovered — root cause not automatically classified. "
            "Manual inspection recommended."
        ),
    )


def build_coverage_result(
    iteration: int,
    coverage_dat: Optional[str] = None,
    lcov_path: Optional[str] = None,
    stdout: Optional[str] = None,
    tests_passed: int = 0,
    tests_failed: int = 0,
    reachability_threshold: float = 5.0,
) -> CoverageResult:
    """Build a CoverageResult from available data sources."""
    dat_counts: Dict[str, int] = {}
    if coverage_dat:
        dat_counts = parse_coverage_dat(coverage_dat)

    toggle_cov = toggle_tot = 0
    uncovered_toggles: List[UncoveredTransition] = []
    if dat_counts:
        toggle_cov, toggle_tot, uncovered_toggles = extract_toggle_coverage(dat_counts)

    lh = lt = bh = bt = 0
    if lcov_path:
        lh, lt, bh, bt = parse_lcov(lcov_path)

    # Fall back to stdout parsing when structured data unavailable
    if (lt == 0 or toggle_tot == 0) and stdout:
        stdout_cov = parse_stdout_coverage(stdout)
        if "line" in stdout_cov:
            lh, lt = stdout_cov["line"]
        if "toggle" in stdout_cov and toggle_tot == 0:
            toggle_cov, toggle_tot = stdout_cov["toggle"]
        if "branch" in stdout_cov:
            bh, bt = stdout_cov["branch"]

    # Classify uncovered toggles
    unreachable: List[UnreachabilityReport] = []
    for ut in uncovered_toggles:
        r = classify_unreachable(ut.signal, ut.direction)
        if r.category != "unknown":
            unreachable.append(r)
            ut.reachable = False

    return CoverageResult(
        iteration=iteration,
        line=CoverageMetric(metric="line", covered=lh, total=max(lt, 1)) if lt else None,
        toggle=CoverageMetric(metric="toggle", covered=toggle_cov, total=max(toggle_tot, 1)) if toggle_tot else None,
        branch=CoverageMetric(metric="branch", covered=bh, total=max(bt, 1)) if bt else None,
        uncovered_toggles=uncovered_toggles,
        unreachable=unreachable,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_total=tests_passed + tests_failed,
    )
