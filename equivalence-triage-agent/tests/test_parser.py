from __future__ import annotations

import pytest

from eq_triage.models import EquivalenceStatus, MismatchKind
from eq_triage.parser import (
    LogParseError,
    load_manifest,
    normalize_manifest,
    parse_equivalence_log,
)


def test_parse_toy_alu_log(toy_alu):
    log = parse_equivalence_log((toy_alu / "equivalence.eqlog").read_text())
    assert log.tool == "mock-lec"
    assert log.status is EquivalenceStatus.NOT_EQUIVALENT
    assert log.reference_design == "ref_alu"
    assert log.revised_design == "rev_alu"
    assert log.compare_points_matched == 9
    assert log.compare_points_total == 13
    assert len(log.mismatches) == 5
    # config delta must be surfaced
    keys = {d.key for d in log.config_deltas}
    assert "reset_polarity" in keys


def test_parse_widths_and_kind(toy_alu):
    log = parse_equivalence_log((toy_alu / "equivalence.eqlog").read_text())
    state = next(m for m in log.mismatches if m.name == "result_reg")
    assert state.kind is MismatchKind.STATE
    assert state.ref_width == 8
    assert state.rev_width == 4


def test_parse_cex_attachment_and_first_diff(toy_alu):
    log = parse_equivalence_log((toy_alu / "equivalence.eqlog").read_text())
    state = next(m for m in log.mismatches if m.name == "result_reg")
    assert state.counterexample is not None
    assert state.counterexample.first_diff_time == 0
    diff_sigs = state.counterexample.diff_signals()
    assert "rst_n" in diff_sigs


def test_parse_rejects_non_eqlog():
    with pytest.raises(LogParseError):
        parse_equivalence_log("not a log\n")


def test_parse_rejects_unknown_status():
    txt = (
        "EQLOG/1\ntool: t\nreference: a\nrevised: b\nstatus: MAYBE\n"
    )
    with pytest.raises(LogParseError):
        parse_equivalence_log(txt)


def test_parse_rejects_cex_for_unknown_cp():
    txt = (
        "EQLOG/1\ntool: t\nreference: a\nrevised: b\nstatus: NOT_EQUIVALENT\n"
        "cex: ghost @0 s ref=0 rev=1\n"
    )
    with pytest.raises(LogParseError):
        parse_equivalence_log(txt)


def test_parse_missing_required_header():
    txt = "EQLOG/1\ntool: t\nreference: a\nstatus: EQUIVALENT\n"
    with pytest.raises(LogParseError):
        parse_equivalence_log(txt)


def test_local_manifest_load(toy_alu):
    m = load_manifest(toy_alu / "ref_manifest.json")
    assert m.top == "ref_alu"
    assert m.signal_widths["result"] == 8
    assert m.reset.polarity.value == "active_low"


def test_canonical_manifest_normalization():
    canonical = {
        "provenance": {"tool_version": "0.1.0"},
        "parser": {"adapter": "builtin", "adapter_version": "0.1.0"},
        "top": "m",
        "modules": [
            {
                "name": "m",
                "location": {"file": "m.v", "line": 1, "col": 1,
                             "end_line": 1, "end_col": 1},
                "ports": [
                    {"name": "d", "direction": "output",
                     "range": {"msb": "7", "lsb": "0"},
                     "location": {"file": "m.v", "line": 1, "col": 1,
                                  "end_line": 1, "end_col": 1}}
                ],
                "reset_candidates": [
                    {"signal": "rst_n", "confidence": 0.9,
                     "polarity": "active_low", "sync": "asynchronous"}
                ],
            }
        ],
    }
    m = normalize_manifest(canonical)
    assert m.top == "m"
    assert m.signal_widths["d"] == 8
    assert m.reset.signal == "rst_n"
    assert m.reset.polarity.value == "active_low"
    assert m.reset.sync.value == "asynchronous"
