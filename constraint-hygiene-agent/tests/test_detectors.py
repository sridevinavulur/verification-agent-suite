"""Behavioral tests: the detectors must flag bad patterns and pass good ones."""

from constraint_hygiene.analysis.contradictions import find_contradictions
from constraint_hygiene.analysis.ownership import classify_signals
from constraint_hygiene.analysis.usage import (
    find_output_constraints,
    find_unused_assumptions,
)
from constraint_hygiene.models import FindingCode
from constraint_hygiene.parsers.manifest import load_manifest
from constraint_hygiene.parsers.sva import parse_sva


def _props(text):
    return parse_sva(text)


def test_boolean_contradiction_detected():
    props = _props("a: assume property (x); b: assume property (!x);")
    findings = find_contradictions(props)
    assert len(findings) == 1
    assert findings[0].code is FindingCode.CONTRADICTION
    assert findings[0].signals == ["x"]


def test_constant_conflict_detected():
    props = _props(
        "a: assume property (mode == 2'b01); b: assume property (mode == 2'b10);"
    )
    findings = find_contradictions(props)
    assert len(findings) == 1
    assert findings[0].code is FindingCode.CONSTANT_CONFLICT


def test_no_false_contradiction_when_consistent():
    props = _props(
        "a: assume property (mode == 2'b01); b: assume property (mode == 2'b01);"
    )
    assert find_contradictions(props) == []


def test_xz_values_not_reported_as_contradiction():
    # 2'bx0 has an x -> uncomparable, must not be flagged.
    props = _props("a: assume property (m == 2'b0x); b: assume property (m == 2'b10);")
    assert find_contradictions(props) == []


def test_unused_assumption_flagged():
    props = _props(
        """
        a: assume property (spare == 0);
        chk: assert property (req |-> gnt);
        """
    )
    findings = find_unused_assumptions(props)
    assert [f.properties for f in findings] == [["a"]]


def test_used_assumption_not_flagged():
    props = _props(
        """
        a: assume property (req);
        chk: assert property (req |-> gnt);
        """
    )
    assert find_unused_assumptions(props) == []


def test_output_and_internal_constraints_flagged(manifest_path):
    view = load_manifest(manifest_path)
    props = _props(
        """
        a: assume property (out_valid);
        b: assume property (state == 2'b00);
        c: assume property (ghost_sig);
        """
    )
    signals = {s for p in props for s in p.signals}
    ownership = classify_signals(signals, view)
    findings = find_output_constraints(props, ownership)
    codes = {f.code for f in findings}
    assert FindingCode.OUTPUT_CONSTRAINT in codes
    assert FindingCode.INTERNAL_STATE_CONSTRAINT in codes
    assert FindingCode.UNKNOWN_SIGNAL in codes


def test_legal_input_assumption_not_flagged(manifest_path):
    view = load_manifest(manifest_path)
    props = _props("a: assume property (in_valid);")
    signals = {s for p in props for s in p.signals}
    ownership = classify_signals(signals, view)
    assert find_output_constraints(props, ownership) == []
