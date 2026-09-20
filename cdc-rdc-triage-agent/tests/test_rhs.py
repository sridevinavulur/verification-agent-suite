from __future__ import annotations

from cdc_rdc_triage.rhs import base_signal, is_bit_sliced, referenced_identifiers


def test_ignores_based_literals() -> None:
    assert referenced_identifiers("{WIDTH{1'b0}}") == {"WIDTH"}
    assert referenced_identifiers("8'hFF") == set()
    assert referenced_identifiers("a + 1'b1") == {"a"}


def test_ignores_plain_numbers() -> None:
    assert referenced_identifiers("wr_ptr + 1") == {"wr_ptr"}
    assert referenced_identifiers("42") == set()


def test_multiple_identifiers() -> None:
    assert referenced_identifiers("wr_en & ~full") == {"wr_en", "full"}


def test_ignores_keywords() -> None:
    assert referenced_identifiers("posedge clk or negedge rst") == {"clk", "rst"}


def test_bit_slice_detection() -> None:
    assert is_bit_sliced("mem[rd_ptr]", "mem") is True
    assert is_bit_sliced("mem[rd_ptr]", "rd_ptr") is False
    assert is_bit_sliced("a + b", "a") is False


def test_hierarchical_head() -> None:
    assert referenced_identifiers("u_sub.data_out") == {"u_sub"}


def test_base_signal() -> None:
    assert base_signal("wr_ptr[3:0]") == "wr_ptr"
    assert base_signal("q") == "q"
