from assertion_mutation_agent.sva import parse_properties


def test_parse_property_block():
    text = """
    property p_x;
        @(posedge clk) disable iff (!rst_n) (count <= 8'hFF);
    endproperty
    a_x : assert property (p_x);
    """
    props = parse_properties(text)
    names = [p.name for p in props]
    assert names == ["p_x"]  # labeled assert instancing p_x is de-duplicated
    assert "count" in props[0].referenced_signals
    assert "rst_n" in props[0].referenced_signals


def test_comments_do_not_create_phantom_properties():
    text = """
    // this property suite covers reset
    /* property NAME_IN_COMMENT foo endproperty */
    property real_one;
        @(posedge clk) (a == b);
    endproperty
    """
    props = parse_properties(text)
    assert [p.name for p in props] == ["real_one"]


def test_inline_labeled_assert_with_signals():
    text = "chk : assert property (@(posedge clk) (ready |-> valid));"
    props = parse_properties(text)
    assert props[0].name == "chk"
    assert set(props[0].referenced_signals) >= {"ready", "valid"}


def test_sva_keywords_not_treated_as_signals():
    text = "property p; @(posedge clk) disable iff (rst) (x); endproperty"
    props = parse_properties(text)
    sigs = props[0].referenced_signals
    assert "disable" not in sigs and "iff" not in sigs and "posedge" not in sigs
    assert "x" in sigs and "rst" in sigs
