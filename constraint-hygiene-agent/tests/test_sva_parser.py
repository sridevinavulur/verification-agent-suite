from constraint_hygiene.parsers.sva import (
    extract_facts,
    extract_signals,
    parse_sva,
)


def test_parse_concurrent_directives():
    text = """
    am_a: assume property (@(posedge clk) disable iff (!rst_n) req == 1'b1);
    as_b: assert property (@(posedge clk) req |-> gnt);
    co_c: cover  property (@(posedge clk) gnt);
    """
    props = parse_sva(text)
    kinds = {p.name: p.kind.value for p in props}
    assert kinds == {"am_a": "assume", "as_b": "assert", "co_c": "cover"}


def test_clock_and_disable_iff_stripped_from_body():
    text = "a: assume property (@(posedge clk) disable iff (!rst_n) mode == 2'b01);"
    (p,) = parse_sva(text)
    assert p.expr == "mode == 2'b01"
    # clk and rst_n come from the prefix and must NOT be in the body signals.
    assert p.signals == ["mode"]


def test_named_property_block_resolution():
    text = """
    property p_stable;
      @(posedge clk) valid == 1'b1;
    endproperty
    am_use: assume property (p_stable);
    """
    (p,) = parse_sva(text)
    assert p.name == "am_use"
    assert p.boolean_facts == {"valid": True} or p.equalities == {"valid": "1"}


def test_immediate_assume_one_liner():
    (p,) = parse_sva("assume(en == 4'hF);")
    assert p.kind.value == "assume"
    assert p.equalities == {"en": "15"}


def test_extract_signals_excludes_keywords_and_numbers():
    sigs = extract_signals("@(posedge clk) foo && !bar || baz == 8'hAA")
    assert "posedge" not in sigs
    assert set(sigs) >= {"clk", "foo", "bar", "baz"}
    assert "AA" not in sigs  # numeric base literal not leaked


def test_extract_facts_boolean_and_constant():
    eq, bo = extract_facts("a && !b && mode == 2'b10")
    assert bo == {"a": True, "b": False}
    assert eq == {"mode": "2"}


def test_extract_facts_only_top_level_conjuncts():
    # Inside a disjunction the fact is NOT unconditional -> not extracted.
    eq, bo = extract_facts("(a || b) && c")
    assert bo == {"c": True}
    assert "a" not in bo and "b" not in bo


def test_constant_normalization():
    eq, _ = extract_facts("m == 4'b0010")
    assert eq == {"m": "2"}
