"""Tests for the optional VerilatorExecutor real-simulator adapter.

Tests split into two groups:
  * Always-run: executor SELECTION via the factory + the graceful-degradation
    path (no simulator required). These keep CI green with no Verilator.
  * Gated: the real compile+run classification, skipped automatically when the
    ``verilator`` binary is not installed (shutil.which guard).
"""

from __future__ import annotations

import shutil

import pytest

from assertion_mutation_agent.executor import get_executor
from assertion_mutation_agent.models import (
    Mutant,
    MutantStatus,
    MutationOperator,
    PropertyRef,
    SourceDiff,
    SourceLocation,
)
from assertion_mutation_agent.verilator_executor import (
    VerilatorExecutor,
    verilator_available,
)

COUNTER_RTL = """\
module counter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       en,
    input  wire       load,
    input  wire [7:0] load_val,
    output reg  [7:0] count,
    output wire       at_max
);
    localparam [7:0] MAX_COUNT = 8'hFF;
    assign at_max = (count == MAX_COUNT);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 8'h00;
        end else begin
            if (load) begin
                count <= load_val;
            end else if (en) begin
                if (count < MAX_COUNT) begin
                    count <= count + 1;
                end
            end
        end
    end
endmodule
"""

# A reset-value mutant: on reset `count` becomes 8'h01 instead of 8'h00, which
# directly violates the p_reset_zero property under real simulation -> DETECTED.
MUTATED_RTL = COUNTER_RTL.replace("count <= 8'h00;", "count <= 8'h01;")

# A mutant the suite does NOT catch: never increments (count > MAX is unreachable),
# so count stays low and neither p_reset_zero nor p_saturate fire -> SURVIVED.
SURVIVING_RTL = COUNTER_RTL.replace("count < MAX_COUNT", "count > MAX_COUNT")

PROPS = [
    PropertyRef(
        name="p_reset_zero",
        text=(
            "property p_reset_zero;\n"
            "    @(posedge clk) disable iff (rst_n) (count == 8'h00);\n"
            "endproperty"
        ),
        referenced_signals=["count", "rst_n"],
    ),
    PropertyRef(
        name="p_saturate",
        text=(
            "property p_saturate;\n"
            "    @(posedge clk) (at_max == (count == 8'hFF));\n"
            "endproperty"
        ),
        referenced_signals=["at_max", "count"],
    ),
]


def _mutant(mutated_source: str, mutant_id: str = "counter.relational_flip.1.deadbeef"):
    diff = SourceDiff(
        location=SourceLocation(file="counter.v", line=1, col_start=1, col_end=1),
        original_text="<",
        mutated_text=">",
        original_line="if (count < MAX_COUNT)",
        mutated_line="if (count > MAX_COUNT)",
    )
    return Mutant(
        mutant_id=mutant_id,
        operator=MutationOperator.RELATIONAL_FLIP,
        description="flip relational operator",
        diff=diff,
        mutated_signals=["count"],
        mutated_source=mutated_source,
    )


# --------------------------------------------------------------------------
# Always-run: executor selection + graceful degradation (no simulator needed)
# --------------------------------------------------------------------------


def test_factory_returns_verilator_executor():
    ex = get_executor("verilator")
    assert isinstance(ex, VerilatorExecutor)
    assert ex.name == "verilator"


def test_factory_still_defaults_to_mock():
    from assertion_mutation_agent.executor import MockExecutor

    assert isinstance(get_executor("mock"), MockExecutor)


def test_factory_unknown_still_raises():
    # Regression guard for the existing behavior: unknown names raise.
    with pytest.raises(ValueError):
        get_executor("verilator-formal")


def test_noop_mutation_is_invalid_without_simulator():
    # A no-op mutant is INVALID regardless of whether verilator exists; this
    # path never shells out.
    ex = VerilatorExecutor()
    m = _mutant(COUNTER_RTL)  # mutated_source == original -> no-op
    r = ex.classify(m, COUNTER_RTL, PROPS)
    assert r.status == MutantStatus.INVALID
    assert r.executor == "verilator"


def test_graceful_degradation_when_verilator_missing(monkeypatch):
    # Simulate verilator being absent from PATH: every real mutant -> ERROR,
    # never a fake PASS/DETECTED.
    monkeypatch.setattr(
        "assertion_mutation_agent.verilator_executor.shutil.which",
        lambda _name: None,
    )
    ex = VerilatorExecutor()
    m = _mutant(MUTATED_RTL)
    r = ex.classify(m, COUNTER_RTL, PROPS)
    assert r.status == MutantStatus.ERROR
    assert "verilator" in r.detail.lower()


def test_verilator_available_reflects_path(monkeypatch):
    monkeypatch.setattr(
        "assertion_mutation_agent.verilator_executor.shutil.which",
        lambda _name: None,
    )
    assert verilator_available() is False
    monkeypatch.setattr(
        "assertion_mutation_agent.verilator_executor.shutil.which",
        lambda _name: "/usr/bin/verilator",
    )
    assert verilator_available() is True


def test_inconclusive_when_no_property_text(monkeypatch):
    monkeypatch.setattr(
        "assertion_mutation_agent.verilator_executor.shutil.which",
        lambda _name: "/usr/bin/verilator",  # pretend present so we reach the check
    )
    ex = VerilatorExecutor()
    m = _mutant(MUTATED_RTL)
    empty_props = [PropertyRef(name="p", text="", referenced_signals=[])]
    r = ex.classify(m, COUNTER_RTL, empty_props)
    assert r.status == MutantStatus.INCONCLUSIVE


# --------------------------------------------------------------------------
# Gated: real compile + run (skipped when verilator is not installed)
# --------------------------------------------------------------------------

requires_verilator = pytest.mark.skipif(
    shutil.which("verilator") is None,
    reason="verilator binary not installed; real-sim test skipped (CI stays green)",
)


@requires_verilator
def test_real_baseline_passes():
    ex = VerilatorExecutor(timeout_s=180)
    assert ex._baseline_passes(COUNTER_RTL, [p.text for p in PROPS]) is True


@requires_verilator
def test_real_mutant_detected():
    ex = VerilatorExecutor(timeout_s=180)
    m = _mutant(MUTATED_RTL)
    r = ex.classify(m, COUNTER_RTL, PROPS)
    # The reset-value mutant must be caught by p_reset_zero.
    assert r.status == MutantStatus.DETECTED
    assert r.detected_by  # at least one property named


@requires_verilator
def test_real_mutant_survives_when_not_observed():
    ex = VerilatorExecutor(timeout_s=180)
    m = _mutant(SURVIVING_RTL, mutant_id="counter.relational_flip.2.5a1e5a1e")
    r = ex.classify(m, COUNTER_RTL, PROPS)
    assert r.status == MutantStatus.SURVIVED


@requires_verilator
def test_real_compile_failure_is_invalid():
    ex = VerilatorExecutor(timeout_s=180)
    broken = COUNTER_RTL.replace("count <= 8'h00;", "count <= ;")  # syntax error
    m = _mutant(broken, mutant_id="counter.relational_flip.99.badc0de")
    r = ex.classify(m, COUNTER_RTL, PROPS)
    # A mutant that does not elaborate is INVALID (excluded from score), not PASS.
    assert r.status == MutantStatus.INVALID
