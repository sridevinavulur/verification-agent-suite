"""Canonical pydantic data models for the veri-forge pipeline.

Two complementary layers:
  1. RunConfig / RunContext / StageResult — lightweight pipeline bus
     (passed stage-to-stage, accumulates artefact paths and simple dicts)
  2. ParsedSpec / TestPlan / CoverageResult / Bug / SimResult — rich typed
     models that individual stages use internally and expose via StageResult.data
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Pipeline bus
# ═══════════════════════════════════════════════════════════════════════════════

class RunConfig(BaseModel):
    spec_path: Path
    rtl_dir: Optional[Path] = None
    top: str = ""
    out_dir: Path = Path("vf_out")
    simulator: str = "verilator"   # "verilator" | "vcs" | "xcelium"
    target_line_pct: float = 90.0
    target_toggle_pct: float = 80.0
    target_branch_pct: float = 85.0
    target_coverage: float = 90.0  # overall average target (used by closure loop)
    max_iter: int = 5
    skip_stages: List[int] = Field(default_factory=list)
    cravs_path: Optional[str] = None  # override CRAVS_PATH env var

    class Config:
        arbitrary_types_allowed = True


class StageResult(BaseModel):
    stage: int
    name: str
    status: str       # "pass" | "fail" | "skip" | "warn"
    summary: str
    artifacts: Dict[str, str] = Field(default_factory=dict)   # label → file path
    data: Dict[str, Any] = Field(default_factory=dict)


class RunContext(BaseModel):
    config: RunConfig
    run_dir: Path
    stage_results: List[StageResult] = Field(default_factory=list)

    # Accumulated pipeline state (stages write here)
    parsed_spec: Dict[str, Any] = Field(default_factory=dict)
    rtl_files: List[str] = Field(default_factory=list)
    sva_file: Optional[str] = None
    testplan: Dict[str, Any] = Field(default_factory=dict)
    cocotb_tests: List[str] = Field(default_factory=list)
    ref_model_file: Optional[str] = None
    bfm_file: Optional[str] = None
    test_file: Optional[str] = None
    sim_log: str = ""
    waveform_path: Optional[str] = None
    coverage_dat: Optional[str] = None
    lcov_file: Optional[str] = None
    coverage: Optional[Any] = None  # LegacyCoverageResult from coverage/parser.py
    bugs: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_history: List[Dict[str, Any]] = Field(default_factory=list)
    iteration: int = 0

    class Config:
        arbitrary_types_allowed = True

    def stage_dir(self, n: int, name: str) -> Path:
        d = self.run_dir / f"s{n:02d}_{name}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def last_stage(self, name: str) -> Optional[StageResult]:
        for r in reversed(self.stage_results):
            if r.name == name:
                return r
        return None

    def coverage_met(self) -> bool:
        if not self.coverage_history:
            return False
        last = self.coverage_history[-1]
        line_ok    = last.get("line_pct", 0)    >= self.config.target_line_pct
        toggle_ok  = last.get("toggle_pct", 0)  >= self.config.target_toggle_pct
        branch_ok  = last.get("branch_pct", 0)  >= self.config.target_branch_pct
        return line_ok and toggle_ok and branch_ok


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Rich models (used inside stages)
# ═══════════════════════════════════════════════════════════════════════════════

class SpecSource(BaseModel):
    type: str
    name: str
    location: str


class Signal(BaseModel):
    name: str
    direction: Optional[str] = None
    width: Optional[int] = None
    description: Optional[str] = None


class Interface(BaseModel):
    name: str
    protocol: Optional[str] = None
    role: Optional[str] = None
    signals: List[Signal] = Field(default_factory=list)
    clocks: List[str] = Field(default_factory=list)
    resets: List[str] = Field(default_factory=list)


class Protocol(BaseModel):
    type: str
    version: Optional[str] = None
    legal_transactions: List[str] = Field(default_factory=list)
    ordering_rules: List[str] = Field(default_factory=list)


class RegisterField(BaseModel):
    name: str
    bits: str
    access: str = "RW"
    reset_value: str = "0"
    description: Optional[str] = None


class Register(BaseModel):
    name: str
    offset: Optional[str] = None
    width: int = 32
    access: Optional[str] = None
    reset_value: Optional[str] = None
    fields: List[RegisterField] = Field(default_factory=list)
    description: Optional[str] = None


class ClockDomain(BaseModel):
    name: str
    freq_mhz: Optional[float] = None


class ResetDomain(BaseModel):
    name: str
    polarity: Optional[str] = "active_low"
    sync: Optional[bool] = None


class FsmState(BaseModel):
    name: str
    transitions: List[Dict[str, str]] = Field(default_factory=list)
    description: Optional[str] = None


class Fsm(BaseModel):
    name: str
    states: List[FsmState] = Field(default_factory=list)
    encoding: Optional[str] = None


class TestCase(BaseModel):
    name: str
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    description: str
    stimulus: str
    expected: str
    coverage_targets: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class TestPlan(BaseModel):
    dut_name: str
    goal_line_pct: float = 90.0
    goal_toggle_pct: float = 80.0
    test_cases: List[TestCase] = Field(default_factory=list)


class CoverageMetric(BaseModel):
    metric: str
    covered: int
    total: int

    @property
    def pct(self) -> float:
        return 100.0 * self.covered / max(self.total, 1)


class UncoveredTransition(BaseModel):
    signal: str
    direction: str
    reason: Optional[str] = None
    reachable: bool = True


class UnreachabilityReport(BaseModel):
    signal: str
    direction: str
    category: Literal[
        "hardwired_constant",
        "dead_code",
        "counter_ceiling",
        "architectural_limit",
        "spec_gap",
        "unknown",
    ]
    explanation: str
    related_spec_issue: Optional[str] = None


class CoverageSnapshot(BaseModel):
    iteration: int
    line_pct: float = 0.0
    toggle_pct: float = 0.0
    branch_pct: float = 0.0
    expr_pct: float = 0.0
    line_covered: int = 0
    line_total: int = 0
    toggle_covered: int = 0
    toggle_total: int = 0
    branch_covered: int = 0
    branch_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    uncovered_toggles: List[UncoveredTransition] = Field(default_factory=list)
    unreachable: List[UnreachabilityReport] = Field(default_factory=list)


class Bug(BaseModel):
    id: str
    severity: Literal["P0", "P1", "P2", "P3"] = "P2"
    failure_type: Literal["RTL_BUG", "SPEC_ISSUE", "TB_BUG", "TOOL_ISSUE"] = "RTL_BUG"
    test: str
    description: str
    root_cause: str
    suggested_fix: str
    status: Literal["open", "fixed", "wont_fix"] = "open"


class CoverageResult(BaseModel):
    """Rich coverage result returned by sim/coverage.py build_coverage_result()."""
    iteration: int = 0
    line: Optional[CoverageMetric] = None
    toggle: Optional[CoverageMetric] = None
    branch: Optional[CoverageMetric] = None
    uncovered_toggles: List[UncoveredTransition] = Field(default_factory=list)
    unreachable: List[UnreachabilityReport] = Field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0


class SimResult(BaseModel):
    success: bool
    exit_code: int
    tests_passed: int = 0
    tests_failed: int = 0
    stdout: str = ""
    stderr: str = ""
    results_xml: Optional[str] = None
    coverage_dat: Optional[str] = None
    log_file: Optional[str] = None
    compile_time_s: float = 0.0
    sim_time_s: float = 0.0
    error_message: Optional[str] = None
