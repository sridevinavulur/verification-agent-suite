"""Behavioral tests for the structural detectors -- these assert the *meaning*
of the findings, not just golden bytes."""

from __future__ import annotations

from pathlib import Path

from cdc_rdc_triage import __version__
from cdc_rdc_triage.analyze import analyze_manifest
from cdc_rdc_triage.report_models import CrossingKind, Severity, SyncEvidence
from cdc_rdc_triage.serialize import load_manifest


def _report(examples_dir: Path, name: str):
    manifest = load_manifest(examples_dir / f"{name}.manifest.json")
    return analyze_manifest(manifest, tool_version=__version__)


def _find(report, src, dst):
    for c in report.all_crossings():
        if c.src_signal == src and c.dst_signal == dst:
            return c
    return None


def test_detects_multi_bit_unsynchronized_cdc(examples_dir: Path) -> None:
    report = _report(examples_dir, "cdc_sync")
    c = _find(report, "bus_a", "bus_b")
    assert c is not None, "expected the bus_a->bus_b CDC crossing to be detected"
    assert c.kind == CrossingKind.cdc
    assert c.multi_bit is True
    assert c.width_bits == 8
    assert c.sync_evidence == SyncEvidence.none_found
    assert c.severity == Severity.high
    assert c.src_domain.clock == "clk_a"
    assert c.dst_domain.clock == "clk_b"
    assert c.src_location is not None and c.dst_location is not None


def test_detects_two_ff_synchronizer(examples_dir: Path) -> None:
    report = _report(examples_dir, "cdc_sync")
    c = _find(report, "flag_a", "sync_ff1")
    assert c is not None, "expected the flag_a->sync_ff1 CDC crossing to be detected"
    assert c.kind == CrossingKind.cdc
    assert c.sync_evidence in (
        SyncEvidence.two_ff_candidate,
        SyncEvidence.multi_ff_candidate,
    )
    assert c.sync_depth is not None and c.sync_depth >= 2
    # a synchronizer candidate must be lower priority than an unsynchronized one
    assert c.risk_score < _find(report, "bus_a", "bus_b").risk_score


def test_detects_reset_domain_crossing(examples_dir: Path) -> None:
    report = _report(examples_dir, "rdc_example")
    c = _find(report, "src_reg", "dst_reg")
    assert c is not None, "expected an RDC crossing src_reg->dst_reg"
    assert c.kind == CrossingKind.rdc
    assert c.src_domain.clock == c.dst_domain.clock  # same clock
    assert c.src_domain.reset != c.dst_domain.reset  # different reset


def test_single_clock_has_no_crossings(examples_dir: Path) -> None:
    report = _report(examples_dir, "single_clock")
    assert report.summary["total_crossings"] == 0


def test_no_false_crossing_within_same_domain(examples_dir: Path) -> None:
    # sync_ff2 <= sync_ff1 is same-domain and must NOT be a crossing
    report = _report(examples_dir, "cdc_sync")
    assert _find(report, "sync_ff1", "sync_ff2") is None


def test_report_never_claims_clean(examples_dir: Path) -> None:
    # A zero-crossing report must NOT be presented as a clean/signoff result.
    report = _report(examples_dir, "single_clock")
    assert report.summary["total_crossings"] == 0
    # The disclaimer explicitly denies signoff quality...
    disc = report.disclaimer.lower()
    assert "not a cdc/rdc signoff" in disc
    # ...and every "clean" mention in the report is inside a *non-claim* (a
    # negation), never a positive verdict field.
    for n in report.non_claims:
        if "clean" in n.lower():
            assert n.lower().startswith("does not")
