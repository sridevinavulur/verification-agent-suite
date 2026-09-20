from reset_intent_agent.agent import analyze_rtl_text
from reset_intent_agent.analyzer import (
    _polarity_from_edge,
    _polarity_from_guard,
    _vote_polarity,
)
from reset_intent_agent.models import PolarityEvidence, ResetPolarity, ResetSync


# -- polarity primitives ----------------------------------------------------
def test_polarity_from_guard_active_low():
    pol, _ = _polarity_from_guard("!rst_n", "rst_n")
    assert pol == ResetPolarity.ACTIVE_LOW


def test_polarity_from_guard_active_high():
    pol, _ = _polarity_from_guard("rst", "rst")
    assert pol == ResetPolarity.ACTIVE_HIGH


def test_polarity_from_edge():
    assert _polarity_from_edge("negedge")[0] == ResetPolarity.ACTIVE_LOW
    assert _polarity_from_edge("posedge")[0] == ResetPolarity.ACTIVE_HIGH


def test_vote_conflict_yields_unknown():
    ev = [
        PolarityEvidence(kind="a", detail="", votes_polarity=ResetPolarity.ACTIVE_LOW),
        PolarityEvidence(kind="b", detail="", votes_polarity=ResetPolarity.ACTIVE_HIGH),
    ]
    pol, notes = _vote_polarity(ev)
    assert pol == ResetPolarity.UNKNOWN
    assert any("conflict" in n for n in notes)


def test_vote_no_evidence_never_infers():
    pol, notes = _vote_polarity([])
    assert pol == ResetPolarity.UNKNOWN
    assert any("not inferred silently" in n for n in notes)


# -- end-to-end analysis ----------------------------------------------------
def test_async_active_low_counter():
    src = """
    module c(input clk, input rst_n, input en, output reg [7:0] count);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) count <= 8'b0;
        else if (en) count <= count + 1'b1;
    endmodule
    """
    m = analyze_rtl_text(src)
    rc = {c.signal: c for c in m.reset_candidates}
    assert "rst_n" in rc
    assert rc["rst_n"].polarity == ResetPolarity.ACTIVE_LOW
    assert rc["rst_n"].sync == ResetSync.ASYNCHRONOUS
    # 'en' must not be a reset candidate
    assert "en" not in rc
    # reset target has the constant reset value
    tgt = {t.register_name: t for t in m.reset_targets}
    assert tgt["count"].reset_value == "8'b0"


def test_sync_active_high_multi_reg_domain():
    src = """
    module s(input clk, input rst, output reg q, output reg v);
      always @(posedge clk) begin
        if (rst) begin q <= 1'b0; v <= 1'b0; end
        else begin q <= 1'b1; v <= 1'b1; end
      end
    endmodule
    """
    m = analyze_rtl_text(src)
    rc = m.reset_candidates[0]
    assert rc.polarity == ResetPolarity.ACTIVE_HIGH
    assert rc.sync == ResetSync.SYNCHRONOUS
    assert len(m.reset_domains) == 1
    assert set(m.reset_domains[0].members) == {"q", "v"}
    assert m.reset_domains[0].heuristic is True


def test_ambiguous_polarity_not_inferred():
    # named _n but used in a positive bare guard -> conflicting -> unknown
    src = """
    module a(input clk, input rst_n, output reg [3:0] q);
      always @(posedge clk)
        if (rst_n) q <= 4'h0;
        else q <= q + 1'b1;
    endmodule
    """
    m = analyze_rtl_text(src)
    rc = m.reset_candidates[0]
    assert rc.polarity == ResetPolarity.UNKNOWN
    assert any(a.signal == "rst_n" for a in m.ambiguities)
    assert any(r.category == "polarity" and r.severity.value == "high" for r in m.risks)


def test_no_reset_flags_high_risk():
    src = """
    module n(input clk, input [7:0] d, output reg [7:0] q);
      always @(posedge clk) q <= d;
    endmodule
    """
    m = analyze_rtl_text(src)
    assert not m.reset_candidates
    assert any(r.category == "no_reset" and r.severity.value == "high" for r in m.risks)


def test_reset_domain_crossing_detected():
    src = """
    module d(input clk, input rst_a_n, input rst_b, input [7:0] din,
             output reg [7:0] reg_a, output reg [7:0] reg_b);
      always @(posedge clk or negedge rst_a_n)
        if (!rst_a_n) reg_a <= 8'h0; else reg_a <= din;
      always @(posedge clk)
        if (rst_b) reg_b <= 8'h0; else reg_b <= reg_a;
    endmodule
    """
    m = analyze_rtl_text(src)
    assert len(m.reset_domains) == 2
    assert len(m.domain_crossings) == 1
    cr = m.domain_crossings[0]
    assert cr.from_register == "reg_a"
    assert cr.to_register == "reg_b"
    assert cr.heuristic is True
    assert any(r.category == "rdc" for r in m.risks)
    assert any(r.category == "mixed_sync" for r in m.risks)


def test_recommendations_present():
    src = """
    module c(input clk, input rst_n, output reg q);
      always @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 1'b0; else q <= 1'b1;
    endmodule
    """
    m = analyze_rtl_text(src)
    kinds = {r.kind for r in m.recommendations}
    assert "cover" in kinds
    assert "directed_test" in kinds
