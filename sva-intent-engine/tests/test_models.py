from __future__ import annotations

import pytest
from pydantic import ValidationError

from sva_intent_engine.models import (
    AtomicClause,
    ClauseKind,
    Provenance,
    SourceSpan,
    TemporalIntent,
)


def _prov():
    return Provenance(stage="test")


def test_sourcespan_rejects_reversed():
    with pytest.raises(ValidationError):
        SourceSpan(start=5, end=2, text="x")


def test_atomic_clause_rejects_bad_delays():
    with pytest.raises(ValidationError):
        AtomicClause(
            clause_id="r.c0",
            requirement_id="r",
            kind=ClauseKind.DESIGN_GUARANTEE,
            source_span=SourceSpan(start=0, end=1, text="x"),
            min_delay=5,
            max_delay=2,
            confidence=0.5,
            rationale="test",
        )


def test_temporal_intent_rejects_bad_delays():
    with pytest.raises(ValidationError):
        TemporalIntent(
            requirement_id="r",
            clause_id="r.c0",
            source_text="x",
            design_top="dut",
            property_kind="assert",
            property_form="bounded_response",
            render_template_id="bounded_response",
            min_delay=9,
            max_delay=1,
            confidence=0.5,
            provenance=_prov(),
        )


def test_strict_model_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Requirement_bad = Provenance(stage="x", bogus_field=1)  # noqa: N806
        assert Requirement_bad is None


def test_confidence_bounds_enforced():
    with pytest.raises(ValidationError):
        AtomicClause(
            clause_id="r.c0",
            requirement_id="r",
            kind=ClauseKind.AMBIGUITY,
            source_span=SourceSpan(start=0, end=1, text="x"),
            confidence=1.5,
            rationale="bad",
        )
