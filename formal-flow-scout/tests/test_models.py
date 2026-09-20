"""Contract tests for the Pydantic models (strictness, schema export)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from formal_flow_scout.models import (
    CoiReport,
    EdgeKind,
    GraphEdge,
    PropertySet,
    Soundness,
)


def test_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        PropertySet.model_validate(
            {"properties": [], "unexpected_field": 1}
        )


def test_property_set_roundtrip():
    ps = PropertySet.model_validate(
        {"properties": [{"name": "p", "signals": [{"name": "x"}]}]}
    )
    assert ps.properties[0].signals[0].role == "asserted"  # default


def test_edge_kind_values_stable_order():
    # cpp_bridge relies on the enumeration order for the int encoding.
    assert list(EdgeKind) == [
        EdgeKind.COMB,
        EdgeKind.SEQ,
        EdgeKind.CLOCK,
        EdgeKind.RESET,
        EdgeKind.HIER,
    ]


def test_graph_edge_rejects_negative_ids():
    with pytest.raises(ValidationError):
        GraphEdge(src=-1, dst=0, kind=EdgeKind.COMB)


def test_report_schema_exports():
    schema = CoiReport.model_json_schema()
    assert schema["title"] == "CoiReport"


def test_soundness_enum_values():
    assert Soundness.UNPROVEN.value == "UNPROVEN"
    assert Soundness.HEURISTIC.value == "HEURISTIC"
    assert Soundness.SOUND.value == "SOUND"
