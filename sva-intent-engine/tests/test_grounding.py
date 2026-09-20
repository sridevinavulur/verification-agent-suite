from __future__ import annotations

from sva_intent_engine.grounding import ground_clause, grounding_report
from sva_intent_engine.models import (
    AtomicClause,
    ClauseKind,
    MatchKind,
    ResetPolarity,
    SourceSpan,
)


def _clause(terms: list[str]) -> AtomicClause:
    return AtomicClause(
        clause_id="r.c0",
        requirement_id="r",
        kind=ClauseKind.DESIGN_GUARANTEE,
        source_span=SourceSpan(start=0, end=1, text="x"),
        referenced_terms=terms,
        confidence=0.8,
        rationale="t",
    )


def test_exact_match_scores_highest(small_manifest):
    g = ground_clause(_clause(["valid"]), small_manifest)
    tg = g.term_groundings[0]
    assert tg.resolved
    assert tg.matches[0].match_kind == MatchKind.EXACT
    assert tg.matches[0].score == 1.0


def test_alias_match_lower_than_exact(small_manifest):
    g = ground_clause(_clause(["vld"]), small_manifest)
    tg = g.term_groundings[0]
    assert tg.matches[0].match_kind == MatchKind.ALIAS
    assert tg.matches[0].score < 1.0


def test_absent_signal_is_unresolved(small_manifest):
    g = ground_clause(_clause(["nonexistent_sig"]), small_manifest)
    assert "nonexistent_sig" in g.unresolved_terms
    assert not g.fully_resolved


def test_glossary_alias_resolves(small_manifest):
    g = ground_clause(_clause(["go"]), small_manifest, glossary={"go": "valid"})
    tg = g.term_groundings[0]
    assert tg.resolved
    assert tg.matches[0].symbol_name == "valid"


def test_single_clock_candidate_selected(small_manifest):
    g = ground_clause(_clause(["valid"]), small_manifest)
    assert g.clock_reset.clock_signal == "clk"


def test_reset_polarity_from_lexical_evidence(small_manifest):
    g = ground_clause(_clause(["valid"]), small_manifest)
    assert g.clock_reset.reset_polarity == ResetPolarity.ACTIVE_LOW


def test_multiple_clocks_not_auto_selected(small_manifest):
    small_manifest.clock_candidates = ["clk", "clk2"]
    g = ground_clause(_clause(["valid"]), small_manifest)
    assert g.clock_reset.clock_signal is None
    assert "deferred" in g.clock_reset.clock_evidence


def test_case_insensitive_match_is_alias_tier(small_manifest):
    g = ground_clause(_clause(["VALID"]), small_manifest)
    tg = g.term_groundings[0]
    assert tg.resolved
    assert tg.matches[0].score < 1.0


def test_grounding_report_mentions_unresolved(small_manifest):
    g = ground_clause(_clause(["ghost"]), small_manifest)
    report = grounding_report(g)
    assert "UNRESOLVED" in report
