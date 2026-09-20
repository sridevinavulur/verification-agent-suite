"""Interop tests: consume the canonical rtl-intent-ingestor manifest.

These prove the reviewer produces correct grounding results when fed the REAL
canonical RTL Intent Manifest (produced by ``rtl-intent-ingestor``), not just the
reviewer's own hand-written fixture format. The canonical fixture in
``examples/manifests/fifo_queue.canonical.json`` is a verbatim copy of the
ingestor's ``examples/expected/fifo_queue.json`` output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from assertion_review.models import ResetPolarity, RtlIntentManifest, SignalRole
from assertion_review.review import review_file, review_text
from assertion_review.rtl_intent_adapter import (
    from_rtl_intent_manifest,
    load_manifest,
)

REPO = Path(__file__).resolve().parent.parent
CANON = REPO / "examples" / "manifests" / "fifo_queue.canonical.json"
FIXTURE = REPO / "examples" / "manifests" / "fifo.manifest.json"
GOOD_FIFO = REPO / "examples" / "good" / "fifo_good.sv"


def test_adapter_projects_canonical_manifest():
    m = load_manifest(str(CANON))
    assert isinstance(m, RtlIntentManifest)
    assert m.top == "fifo_queue"
    assert m.clock_candidates == ["clk"]
    assert m.reset_candidates == ["rst"]

    by = m.by_name()
    # Clock/reset candidacy overrides raw port direction.
    assert by["clk"].role is SignalRole.CLOCK
    assert by["rst"].role is SignalRole.RESET
    # Ports keep their direction role.
    assert by["wr_en"].role is SignalRole.INPUT
    assert by["full"].role is SignalRole.OUTPUT
    # Internal nets (not ports) become INTERNAL.
    assert by["wr_ptr"].role is SignalRole.INTERNAL
    assert by["do_write"].role is SignalRole.INTERNAL


def test_adapter_width_from_integer_range_only():
    m = load_manifest(str(CANON))
    by = m.by_name()
    # canonical fifo ranges are parameter expressions ("WIDTH - 1"), which the
    # producer does not evaluate -> width stays the safe default of 1.
    assert by["wr_data"].width == 1
    assert by["rd_data"].width == 1


def test_auto_detect_selects_canonical_vs_fixture():
    # Canonical manifest is detected and adapted.
    canon = load_manifest(str(CANON), manifest_format="auto")
    assert canon.top == "fifo_queue"
    # Reviewer's own fixture still loads unchanged (back-compat).
    fixture = load_manifest(str(FIXTURE), manifest_format="auto")
    assert fixture.top == "fifo"
    # Forcing fixture format on the canonical file must fail (extra keys).
    with pytest.raises(ValidationError):
        load_manifest(str(CANON), manifest_format="fixture")


def test_review_grounds_against_canonical_manifest():
    """The reviewer grounds SVA identifiers against the canonical manifest."""
    m = load_manifest(str(CANON))
    report = review_text(
        GOOD_FIFO.read_text(), source_file=str(GOOD_FIFO), manifest=m
    )
    assert report.manifest_top == "fifo_queue"
    assert report.property_count == 3

    undeclared = {
        f.property_name or f.message
        for f in report.findings
        if f.check_id.value == "UNDECLARED_SIGNAL"
    }
    # clk/rst/full/empty are declared in fifo_queue; push/pop are NOT, so the
    # reviewer must flag exactly those two as undeclared.
    joined = " ".join(
        f.message for f in report.findings if f.check_id.value == "UNDECLARED_SIGNAL"
    )
    assert "push" in joined
    assert "pop" in joined
    assert undeclared  # at least one undeclared finding present


def test_cli_paths_agree_on_canonical_manifest():
    auto = review_file(str(GOOD_FIFO), manifest_path=str(CANON), manifest_format="auto")
    forced = review_file(
        str(GOOD_FIFO), manifest_path=str(CANON), manifest_format="canonical"
    )
    assert [f.check_id for f in auto.findings] == [f.check_id for f in forced.findings]


def test_from_rtl_intent_manifest_module_selection():
    import json

    data = json.loads(CANON.read_text())
    m = from_rtl_intent_manifest(data, module="fifo_queue")
    assert m.top == "fifo_queue"
    # Reset polarity is carried verbatim from the producer heuristic.
    assert m.by_name()["rst"].reset_polarity is ResetPolarity.UNKNOWN
