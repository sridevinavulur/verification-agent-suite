from reset_intent_agent.agent import analyze_rtl_text
from reset_intent_agent.models import ResetPolarity, SvaStatus


def _analyze(src):
    return analyze_rtl_text(src)


def test_candidate_sva_is_always_candidate():
    src = """
    module c(input clk, input rst_n, output reg q);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 1'b0; else q <= 1'b1;
    endmodule
    """
    m = _analyze(src)
    assert m.candidate_sva
    for p in m.candidate_sva:
        assert p.status == SvaStatus.CANDIDATE
        assert "verified" not in p.sva_text.lower()


def test_active_low_renders_negated_expr():
    src = """
    module c(input clk, input rst_n, output reg q);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 1'b0; else q <= 1'b1;
    endmodule
    """
    p = _analyze(src).candidate_sva[0]
    assert p.reset_polarity == ResetPolarity.ACTIVE_LOW
    assert "(!rst_n)" in p.sva_text
    assert "|->" in p.sva_text
    assert "q == 1'b0" in p.sva_text


def test_active_high_renders_plain_expr():
    src = """
    module c(input clk, input rst, output reg q);
      always @(posedge clk)
        if (rst) q <= 1'b0; else q <= 1'b1;
    endmodule
    """
    p = _analyze(src).candidate_sva[0]
    assert p.reset_polarity == ResetPolarity.ACTIVE_HIGH
    assert "(rst)" in p.sva_text


def test_unknown_polarity_emits_review_placeholder():
    src = """
    module a(input clk, input rst_n, output reg q);
      always @(posedge clk)
        if (rst_n) q <= 1'b0; else q <= q;
    endmodule
    """
    p = _analyze(src).candidate_sva[0]
    assert p.reset_polarity == ResetPolarity.UNKNOWN
    assert "REVIEW" in p.sva_text
    assert any("UNKNOWN" in n for n in p.review_notes)


def test_clock_selected_for_property():
    src = """
    module c(input my_clk, input rst_n, output reg q);
      always @(posedge my_clk or negedge rst_n)
        if (!rst_n) q <= 1'b0; else q <= 1'b1;
    endmodule
    """
    p = _analyze(src).candidate_sva[0]
    assert "@(posedge my_clk)" in p.sva_text
