"""Tests for the constrained SVA parser."""

from __future__ import annotations

from assertion_review.models import ImplicationStyle, PropertyKind
from assertion_review.parser import parse_sva


def test_parses_named_property_block():
    src = """
    property p_req;
      @(posedge clk) disable iff (!rst_n) req |=> grant;
    endproperty
    assert property (p_req);
    """
    props = parse_sva(src)
    assert len(props) == 1
    p = props[0]
    assert p.name == "p_req"
    assert p.kind == PropertyKind.ASSERT
    assert p.clock == "clk"
    assert p.disable_iff == "!rst_n"
    assert p.antecedent == "req"
    assert p.consequent == "grant"
    assert p.implication == ImplicationStyle.NON_OVERLAPPING


def test_named_property_not_double_counted():
    src = """
    property p;
      @(posedge clk) a |-> b;
    endproperty
    assert property (p);
    """
    props = parse_sva(src)
    assert len(props) == 1


def test_inline_assert():
    src = "L1: assert property (@(posedge clk) disable iff (rst) x |-> y);"
    props = parse_sva(src)
    assert len(props) == 1
    p = props[0]
    assert p.name == "L1"
    assert p.clock == "clk"
    assert p.disable_iff == "rst"
    assert p.implication == ImplicationStyle.OVERLAPPING


def test_assume_and_cover_kinds():
    src = """
    a1: assume property (@(posedge clk) in_val == 0);
    c1: cover property (@(posedge clk) a ##1 b);
    """
    props = parse_sva(src)
    kinds = {p.name: p.kind for p in props}
    assert kinds["a1"] == PropertyKind.ASSUME
    assert kinds["c1"] == PropertyKind.COVER


def test_missing_clock_detected_as_none():
    src = "p2: assert property (disable iff (rst) a |-> b);"
    props = parse_sva(src)
    assert props[0].clock is None


def test_comments_stripped_line_numbers_preserved():
    src = "// header comment\n" "/* block\n comment */\n" "L: assert property (@(posedge clk) a |-> b);\n"
    props = parse_sva(src)
    assert len(props) == 1
    # The assertion is on line 4.
    assert props[0].location.line == 4


def test_sized_literals_not_treated_as_signals():
    src = "L: assert property (@(posedge clk) a |-> data == 8'hFF);"
    props = parse_sva(src)
    ids = props[0].identifiers
    assert "a" in ids
    assert "data" in ids
    assert "hFF" not in ids
    assert "b0" not in ids


def test_top_level_implication_split_ignores_parens():
    src = "L: assert property (@(posedge clk) (a || b) |-> (c && d));"
    p = parse_sva(src)[0]
    assert p.antecedent == "(a || b)"
    assert p.consequent == "(c && d)"
