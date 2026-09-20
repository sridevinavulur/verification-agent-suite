"""Built-in example reports (public toy data only).

These double as CLI demos, example generators, and deterministic fixtures for
golden tests. Timestamps are hard-coded strings so output is reproducible.
"""
from __future__ import annotations

from .models import (
    CoveragePoint,
    Finding,
    Provenance,
    ReportModel,
    Section,
    Stat,
    Status,
    Table,
)


def coverage_report() -> ReportModel:
    """A coverage-closure-style report (metrics, history, unreachability)."""
    return ReportModel(
        title="Coverage Closure Report — dut_alu",
        subtitle="Regression coverage summary",
        provenance=Provenance(
            tool="coverage-closure-agent",
            tool_version="0.3.1",
            git_sha="abc1234",
            command="cca close --top dut_alu --seed 7",
            seed=7,
            input_hashes={"rtl": "sha256:deadbeef", "plan": "sha256:c0ffee"},
            runtime_seconds=412.5,
            peak_memory_mb=1830.0,
            status=Status.PASS,
            timestamp="2026-09-20T10:00:00Z",
        ),
        stats=[
            Stat(label="Line", value=92.4, unit="%", status=Status.PASS),
            Stat(label="Toggle", value=81.0, unit="%", status=Status.WARN),
            Stat(label="Branch", value=88.7, unit="%", status=Status.WARN),
            Stat(label="Tests Pass", value="248/250", status=Status.WARN),
            Stat(label="Closure", value="NEAR", status=Status.WARN),
        ],
        coverage_history=[
            CoveragePoint(label=0, metrics={"line": 71.2, "toggle": 55.0, "branch": 63.1}),
            CoveragePoint(label=1, metrics={"line": 84.9, "toggle": 70.3, "branch": 79.8}),
            CoveragePoint(label=2, metrics={"line": 92.4, "toggle": 81.0, "branch": 88.7}),
        ],
        sections=[
            Section(
                heading="Toggle Unreachability Analysis",
                status=Status.INFO,
                body="Signals below are architecturally unreachable and are excluded "
                "from the effective coverage ceiling. These exclusions are "
                "heuristic and should be reviewed by a human.",
                tables=[
                    Table(
                        columns=["Signal", "Direction", "Category", "Explanation"],
                        rows=[
                            ["alu.dbg_mode", "1->0", "Hardwired", "Tied off in this config"],
                            ["alu.spare[3]", "0->1", "Dead Code", "Never driven in RTL"],
                            ["ctr.q[15]", "0->1", "Counter Ceiling", "Max count < 2^15"],
                        ],
                    )
                ],
            ),
        ],
        findings=[
            Finding(
                id="COV-001",
                title="Branch coverage below signoff threshold (90%)",
                severity="medium",
                status=Status.FAIL,
                category="coverage-gap",
                description="Branch coverage of 88.7% is under the 90% signoff bar.",
                suggested_fix="Add directed tests for the error-injection FSM path.",
                location="dut_alu/control_fsm.sv:142",
                heuristic=False,
            ),
        ],
    )


def findings_report() -> ReportModel:
    """A findings/triage-style report (severity-classified issues)."""
    return ReportModel(
        title="Counterexample Triage Report — fifo_ctrl",
        subtitle="Formal property failures, classified",
        provenance=Provenance(
            tool="counterexample-triage-agent",
            tool_version="0.2.0",
            git_sha="def5678",
            command="cxt triage --cex cex_dump/",
            seed="n/a",
            runtime_seconds=37.2,
            status=Status.FAIL,
            timestamp="2026-09-20T11:30:00Z",
        ),
        stats=[
            Stat(label="Findings", value=4),
            Stat(label="Critical", value=1, status=Status.FAIL),
            Stat(label="Properties", value=12),
            Stat(label="Proven", value=8, status=Status.PASS),
        ],
        sections=[
            Section(
                heading="Summary",
                status=Status.FAIL,
                body="8 of 12 properties were PROVEN. 4 produced counterexamples "
                "and are classified below. No result was upgraded to PASS from a "
                "TIMEOUT or INCONCLUSIVE outcome.",
                bullets=[
                    "1 critical: real design bug (overflow write).",
                    "1 high: likely design bug, needs designer confirm.",
                    "2 low/info: over-constrained property (spec gap).",
                ],
            ),
        ],
        findings=[
            Finding(
                id="CEX-1",
                title="FIFO write accepted while full — data overwrite",
                severity="critical",
                status=Status.FAIL,
                category="design-bug",
                description="wr_en asserted with full=1 overwrites tail entry.",
                suggested_fix="Gate wr_en with !full in the write path.",
                location="fifo_ctrl.sv:88",
            ),
            Finding(
                id="CEX-2",
                title="Empty flag deasserts one cycle late after reset",
                severity="high",
                status=Status.FAIL,
                category="design-bug",
                description="empty stays low for 1 cycle post-reset.",
                location="fifo_ctrl.sv:51",
            ),
            Finding(
                id="CEX-3",
                title="Property assumes single-clock; DUT is dual-clock",
                severity="low",
                status=Status.INCONCLUSIVE,
                category="spec-gap",
                description="Over-constrained assumption; not a design bug.",
                heuristic=True,
            ),
            Finding(
                id="CEX-4",
                title="Liveness property compiled but not proven (bound reached)",
                severity="info",
                status=Status.COMPILED,
                category="proof-scope",
                description="Bounded proof hit depth limit; not a sound pass.",
                heuristic=False,
            ),
        ],
        tables=[
            Table(
                title="Property Outcomes",
                columns=["Property", "Result", "Depth"],
                rows=[
                    ["p_no_overflow", "FAIL", "7"],
                    ["p_empty_after_reset", "FAIL", "2"],
                    ["p_fair_grant", "COMPILED", "20 (bound)"],
                    ["p_ptr_wrap", "PASS", "full"],
                ],
                note="Result vocabulary per BUILD_STANDARD.md.",
            ),
        ],
    )
