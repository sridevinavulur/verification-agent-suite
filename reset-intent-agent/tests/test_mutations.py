from reset_intent_agent.mutations import (
    generate_mutants,
    mutate_polarity_flip,
    mutate_reset_removal,
    mutate_reset_value,
)

SRC = """
module c(input clk, input rst_n, output reg [7:0] count);
  always @(posedge clk or negedge rst_n)
    if (!rst_n) count <= 8'b0;
    else count <= count + 1'b1;
endmodule
"""


def test_polarity_flip_generates_mutant():
    muts = mutate_polarity_flip(SRC)
    assert len(muts) == 1
    m = muts[0]
    assert m.operator == "reset_polarity_flip"
    assert "if (rst_n)" in m.mutated_source
    assert "if (!rst_n)" not in m.mutated_source.split("if (rst_n)")[0][-15:]


def test_reset_value_change_flips_constant():
    muts = mutate_reset_value(SRC)
    assert len(muts) == 1
    m = muts[0]
    assert m.operator == "reset_value_change"
    assert "count <= 8'b1;" in m.mutated_source


def test_reset_removal_disables_guard():
    muts = mutate_reset_removal(SRC)
    assert len(muts) == 1
    assert "if (1'b0)" in muts[0].mutated_source


def test_generate_all_and_stable_ids():
    muts = generate_mutants(SRC)
    assert len(muts) == 3
    ids = [m.mutant_id for m in muts]
    assert ids == ["M001", "M002", "M003"]
    # every mutant differs from the original source
    for m in muts:
        assert m.mutated_source != SRC


def test_operator_filter():
    muts = generate_mutants(SRC, operators=["reset_polarity_flip"])
    assert all(m.operator == "reset_polarity_flip" for m in muts)


def test_non_reset_guard_not_mutated():
    src = "module m(input clk, input en, output reg q);\n" \
          "  always @(posedge clk) if (en) q <= 1'b0;\nendmodule"
    # 'en' is not reset-like -> no polarity/removal mutants
    assert mutate_polarity_flip(src) == []
    assert mutate_reset_removal(src) == []
