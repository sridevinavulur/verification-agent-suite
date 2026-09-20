from __future__ import annotations

from sva_intent_engine.decompose import decompose
from sva_intent_engine.models import ClauseKind, Requirement


def _req(text: str) -> Requirement:
    return Requirement(requirement_id="r", source_text=text)


def test_splits_on_sentence_boundaries():
    d = decompose(_req("full is high. empty is low."))
    assert len(d.clauses) == 2


def test_classifies_design_guarantee():
    d = decompose(_req("grant must be high."))
    assert d.clauses[0].kind == ClauseKind.DESIGN_GUARANTEE


def test_classifies_environment_assumption():
    d = decompose(_req("Assume valid is stable while ready is low."))
    assert d.clauses[0].kind == ClauseKind.ENVIRONMENT_ASSUMPTION


def test_classifies_cover_objective():
    d = decompose(_req("The FIFO should be able to reach full within 5 cycles."))
    assert d.clauses[0].kind == ClauseKind.COVER_OBJECTIVE


def test_flags_vague_terms_as_ambiguity():
    d = decompose(_req("grant must arrive soon."))
    c = d.clauses[0]
    assert c.kind == ClauseKind.AMBIGUITY
    assert "soon" in c.vague_terms


def test_flags_unsupported_performance_requirement():
    d = decompose(_req("The throughput must exceed the budget."))
    assert d.clauses[0].kind == ClauseKind.UNSUPPORTED


def test_extracts_explicit_range_bound():
    d = decompose(_req("When a is high, b must be high within 1 to 3 cycles."))
    c = d.clauses[0]
    assert (c.min_delay, c.max_delay) == (1, 3)
    assert c.timing_relation == "bounded_response"


def test_extracts_next_cycle_bound():
    d = decompose(_req("When a is high, b must be low on the next cycle."))
    c = d.clauses[0]
    assert (c.min_delay, c.max_delay) == (1, 1)
    assert c.timing_relation == "next_cycle"


def test_never_infers_missing_bound():
    d = decompose(_req("When a is high, b must be high."))
    c = d.clauses[0]
    assert c.min_delay is None and c.max_delay is None


def test_never_infers_clock_or_reset():
    d = decompose(_req("grant must be high within 2 cycles."))
    c = d.clauses[0]
    assert c.clock is None
    assert c.reset_behavior is None


def test_extracts_trigger_and_consequent():
    d = decompose(_req("When valid and ready are high, grant must be high."))
    c = d.clauses[0]
    assert c.trigger == "valid and ready are high"
    assert "grant" in (c.consequent or "")


def test_extracts_unless_guard():
    d = decompose(_req("When a is high, b must be high unless reset is asserted."))
    c = d.clauses[0]
    assert c.guard is not None and "reset" in c.guard
