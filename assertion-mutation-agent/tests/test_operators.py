"""Tests for each mutation operator: real source transforms, not stubs."""

from assertion_mutation_agent.models import MutationOperator
from assertion_mutation_agent.operators import generate_mutants


def _by_op(mutants, op):
    return [m for m in mutants if m.operator == op]


def test_relational_flip_transforms_source():
    src = "assign y = (a < b);"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RELATIONAL_FLIP)
    assert len(ms) == 1
    assert ms[0].diff.mutated_text == ">"
    assert "a > b" in ms[0].mutated_source


def test_relational_flip_does_not_touch_nonblocking_assign():
    # '<=' here is a nonblocking assignment, not a relational operator.
    src = "always @(posedge clk) begin q <= d; end"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RELATIONAL_FLIP)
    assert ms == []


def test_relational_flip_detects_relational_le():
    src = "assign y = (a <= b);"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RELATIONAL_FLIP)
    assert len(ms) == 1
    assert ms[0].diff.mutated_text == ">="


def test_boolean_negation_wraps_condition():
    src = "always @(*) if (a && b) c = 1;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.BOOLEAN_NEGATION)
    assert len(ms) == 1
    assert "!(a && b)" in ms[0].mutated_source
    assert set(ms[0].mutated_signals) == {"a", "b"}


def test_enable_removal_forces_true():
    src = "always @(posedge clk) if (en) q <= d;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.ENABLE_REMOVAL)
    assert len(ms) == 1
    assert "if (1'b1)" in ms[0].mutated_source
    assert ms[0].mutated_signals == ["en"]


def test_enable_removal_ignores_non_enable_conditions():
    src = "always @(posedge clk) if (foo) q <= d;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.ENABLE_REMOVAL)
    assert ms == []


def test_reset_polarity_flip():
    src = "always @(posedge clk or negedge rst_n) begin end"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RESET_POLARITY_FLIP)
    assert len(ms) == 1
    assert ms[0].diff.original_text == "negedge"
    assert ms[0].diff.mutated_text == "posedge"
    assert ms[0].mutated_signals == ["rst_n"]


def test_reset_value_change_binary():
    src = "always @(posedge clk) if (!rst_n) q <= 4'b0000;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RESET_VALUE_CHANGE)
    assert len(ms) == 1
    assert ms[0].diff.mutated_text == "4'b1111"


def test_reset_value_change_toggle_bit():
    src = "always @(posedge clk) if (!rst_n) q <= 0;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.RESET_VALUE_CHANGE)
    assert len(ms) == 1
    assert ms[0].diff.mutated_text == "1"


def test_counter_incdec_change():
    src = "always @(posedge clk) count <= count + 1;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.COUNTER_INCDEC_CHANGE)
    assert len(ms) == 1
    assert "count - 1" in ms[0].mutated_source


def test_assign_operand_swap():
    src = "assign diff = a - b;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.ASSIGN_OPERAND_SWAP)
    assert len(ms) == 1
    assert "b - a" in ms[0].mutated_source
    assert set(ms[0].mutated_signals) == {"a", "b"}


def test_valid_ready_gating_removal():
    src = "assign fire = in_valid && out_ready;"
    ms = _by_op(
        generate_mutants("m", src), MutationOperator.VALID_READY_GATING_REMOVAL
    )
    assert len(ms) == 1
    assert "in_valid" in ms[0].mutated_source
    assert "out_ready" not in ms[0].mutated_source.split(";")[0]


def test_valid_ready_gating_ignores_generic_and():
    src = "assign x = foo && bar;"
    ms = _by_op(
        generate_mutants("m", src), MutationOperator.VALID_READY_GATING_REMOVAL
    )
    assert ms == []


def test_width_truncation_adds_bit_select():
    src = "always @(posedge clk) q <= d;"
    ms = _by_op(generate_mutants("m", src), MutationOperator.WIDTH_TRUNCATION)
    assert len(ms) == 1
    assert "d[0]" in ms[0].mutated_source


def test_generate_mutants_stable_ids():
    src = "assign y = (a < b);"
    a = generate_mutants("m", src)
    b = generate_mutants("m", src)
    assert [m.mutant_id for m in a] == [m.mutant_id for m in b]


def test_mutants_actually_change_source():
    src = open(
        _example_path("counter.v"), encoding="utf-8"
    ).read()
    ms = generate_mutants("counter", src)
    assert ms, "expected mutants on the toy benchmark"
    for m in ms:
        assert m.mutated_source != src


def _example_path(name: str) -> str:
    import pathlib

    return str(
        pathlib.Path(__file__).resolve().parent.parent / "examples" / name
    )
