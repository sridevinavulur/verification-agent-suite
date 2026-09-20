"""Interop tests: consume the canonical rtl-intent-ingestor manifest.

These prove the grounding engine produces correct results when fed the REAL
canonical RTL Intent Manifest (produced by ``rtl-intent-ingestor``), not just the
engine's own hand-written fixture. The canonical fixture in
``examples/rtl_manifests/valid_ready.canonical.json`` is a verbatim copy of the
ingestor's ``examples/expected/valid_ready.json`` output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sva_intent_engine.decompose import decompose
from sva_intent_engine.grounding import ground_clause
from sva_intent_engine.io_utils import load_manifest as io_load_manifest
from sva_intent_engine.models import Requirement, ResetPolarity, RTLManifest
from sva_intent_engine.rtl_intent_adapter import (
    from_rtl_intent_manifest,
    load_manifest,
)

REPO = Path(__file__).resolve().parent.parent
CANON = REPO / "examples" / "rtl_manifests" / "valid_ready.canonical.json"
FIXTURE = REPO / "examples" / "rtl_manifests" / "ready_valid.json"


def test_adapter_projects_canonical_manifest():
    m = load_manifest(str(CANON))
    assert isinstance(m, RTLManifest)
    assert m.design_top == "vr_top"
    assert m.clock_candidates == ["clk"]
    assert m.reset_candidates == ["rst_n"]

    clk = m.by_name("clk")
    rstn = m.by_name("rst_n")
    assert clk is not None and clk.kind == "clock"
    assert rstn is not None and rstn.kind == "reset"
    # Producer's heuristic reset polarity is carried into signal_type.
    assert rstn.signal_type == "active_low"
    # A declared port keeps its direction; an internal net does not.
    start = m.by_name("start")
    assert start is not None and start.direction == "input"
    valid = m.by_name("valid")
    assert valid is not None and valid.kind == "wire" and valid.direction is None


def test_adapter_width_unknown_for_parameter_range():
    m = load_manifest(str(CANON))
    # out_data / data widths are parameter expressions ("WIDTH - 1"); the
    # producer does not evaluate them, so width stays unknown (None), not a guess.
    data = m.by_name("data")
    assert data is not None and data.width is None
    # A plain unsized 1-bit signal gets width 1.
    assert m.by_name("start").width == 1


def test_symbol_ids_are_unique():
    m = load_manifest(str(CANON))
    ids = [s.symbol_id for s in m.symbols]
    assert len(ids) == len(set(ids))


def test_auto_detect_selects_canonical_vs_fixture():
    canon = load_manifest(str(CANON), manifest_format="auto")
    assert canon.design_top == "vr_top"
    # Engine's own fixture still loads unchanged (back-compat).
    fixture = load_manifest(str(FIXTURE), manifest_format="auto")
    assert fixture.design_top == "handshake"
    # io_utils.load_manifest (the CLI entry point) auto-detects too.
    canon_io = io_load_manifest(CANON)
    assert canon_io.design_top == "vr_top"
    fixture_io = io_load_manifest(FIXTURE)
    assert fixture_io.design_top == "handshake"
    # Forcing fixture format on the canonical file must fail (extra keys).
    with pytest.raises(ValidationError):
        load_manifest(str(CANON), manifest_format="fixture")


def test_grounding_end_to_end_against_canonical_manifest():
    """Real interop: decompose a requirement and ground it on the canonical manifest."""
    m = io_load_manifest(CANON)
    req = Requirement(
        requirement_id="vr1",
        source_text="When valid and ready are high, start must be high within 1 to 3 cycles.",
        origin_path="<test>",
    )
    decomp = decompose(req)
    assert decomp.clauses, "requirement should decompose to >=1 clause"

    res = ground_clause(decomp.clauses[0], m)
    assert res.design_top == "vr_top"
    # Clock/reset selected from the canonical candidate lists.
    assert res.clock_reset.clock_signal == "clk"
    assert res.clock_reset.reset_signal == "rst_n"
    assert res.clock_reset.reset_polarity is ResetPolarity.ACTIVE_LOW
    # valid/ready/start all exist in the canonical design and resolve exactly.
    resolved = {tg.term: tg.best().symbol_name for tg in res.term_groundings if tg.best()}
    assert resolved.get("valid") == "valid"
    assert resolved.get("ready") == "ready"
    assert resolved.get("start") == "start"


def test_grounding_blocks_on_unknown_term():
    m = io_load_manifest(CANON)
    req = Requirement(
        requirement_id="vr2",
        source_text="When valid is high, teleport must be high.",
        origin_path="<test>",
    )
    decomp = decompose(req)
    res = ground_clause(decomp.clauses[0], m)
    # 'teleport' is not in the canonical design -> recorded as unresolved.
    assert "teleport" in res.unresolved_terms
    assert not res.fully_resolved


def test_from_rtl_intent_manifest_module_selection():
    data = json.loads(CANON.read_text())
    m = from_rtl_intent_manifest(data, module="vr_top")
    assert m.design_top == "vr_top"
