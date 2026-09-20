from __future__ import annotations

from security_property_agent.grounding import ground
from security_property_agent.models import (
    MatchKind,
    SecurityCategory,
    SecurityRequirement,
)


def test_exact_symbols_resolved_with_evidence(manifest):
    req = SecurityRequirement(
        requirement_id="R1",
        category=SecurityCategory.ACCESS_CONTROL,
        text="wr_commit must imply wr_grant.",
        signals=["wr_commit", "wr_grant"],
    )
    g = ground(req, manifest)
    resolved = {s.term: s for s in g.symbols if s.match_kind is MatchKind.EXACT}
    assert "wr_commit" in resolved
    assert "wr_grant" in resolved
    assert resolved["wr_commit"].evidence  # evidence recorded


def test_unknown_signal_is_unresolved_not_invented(manifest):
    req = SecurityRequirement(
        requirement_id="R1",
        category=SecurityCategory.ACCESS_CONTROL,
        text="totally_made_up_signal must be low.",
        signals=["totally_made_up_signal"],
    )
    g = ground(req, manifest)
    assert "totally_made_up_signal" in g.unresolved_terms
    # It is present as an UNRESOLVED ref, never fabricated as a real symbol.
    ref = next(s for s in g.symbols if s.term == "totally_made_up_signal")
    assert ref.match_kind is MatchKind.UNRESOLVED
    assert ref.symbol is None


def test_no_trust_boundary_declared_raises_ambiguity(manifest):
    req = SecurityRequirement(
        requirement_id="R1",
        category=SecurityCategory.ACCESS_CONTROL,
        text="wr_commit must imply wr_grant.",
        signals=["wr_commit", "wr_grant"],
    )
    g = ground(req, manifest)
    assert any("trust boundary" in a for a in g.ambiguities)


def test_clock_reset_come_from_manifest(manifest):
    req = SecurityRequirement(
        requirement_id="R1",
        category=SecurityCategory.ACCESS_CONTROL,
        text="wr_commit must imply wr_grant.",
        signals=["wr_commit"],
    )
    g = ground(req, manifest)
    assert "clk" in g.clock_candidates
    assert "rst_n" in g.reset_candidates
