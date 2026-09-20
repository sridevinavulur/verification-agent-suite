"""Tests for the deterministic triage engine and its safety invariants."""

import pytest

from cx_triage.models import (
    AssertionFailure,
    HypothesisCategory,
    RTLIntentManifest,
)
from cx_triage.parser import load_json_trace, parse_vcd_file
from cx_triage.triage import TriageEngine


def _load_toy(examples_dir):
    trace = parse_vcd_file(examples_dir / "toy_counter" / "counter_fail.vcd")
    failure = AssertionFailure.model_validate_json(
        (examples_dir / "toy_counter" / "failure.json").read_text()
    )
    manifest = RTLIntentManifest.model_validate_json(
        (examples_dir / "toy_counter" / "manifest.json").read_text()
    )
    return trace, failure, manifest


def test_antecedent_and_divergence_cycles(examples_dir):
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    assert report.antecedent_cycle == 2  # first en outside reset
    assert report.first_divergence_cycle == 6  # count_advanced=0 after en&stall


def test_design_bug_is_top_with_evidence(examples_dir):
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    top = report.top_hypothesis()
    assert top.category == HypothesisCategory.DESIGN_BUG
    assert top.evidence  # never evidence-free
    assert 0.0 < top.confidence <= 0.75


def test_alternatives_always_retained(examples_dir):
    """Safety: a design-bug conclusion never hides alternatives."""
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    cats = {h.category for h in report.hypotheses}
    assert HypothesisCategory.DESIGN_BUG in cats
    assert HypothesisCategory.PROPERTY_ISSUE in cats
    assert len(report.hypotheses) >= 2


def test_cone_includes_bug_source_stall(examples_dir):
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    # The actual bug is the `stall` gating; it must appear in the cone.
    assert "tb.stall" in report.rtl_cone


def test_hypotheses_ranked_by_confidence(examples_dir):
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    confs = [h.confidence for h in report.hypotheses]
    assert confs == sorted(confs, reverse=True)


def test_citations_include_property_and_cone(examples_dir):
    trace, failure, manifest = _load_toy(examples_dir)
    report = TriageEngine(trace, failure, manifest).run("cmd", [])
    files = {(c.file, c.symbol) for c in report.citations}
    assert (failure.source_file, "p_inc") in files
    assert any(sym == "tb.stall" for _, sym in files)


def test_no_design_bug_when_antecedent_never_fires(examples_dir):
    """A failing property with an inactive antecedent is NOT a design bug."""
    trace = load_json_trace(examples_dir / "env_gap" / "trace.json")
    failure = AssertionFailure.model_validate_json(
        (examples_dir / "env_gap" / "failure.json").read_text()
    )
    report = TriageEngine(trace, failure, None).run("cmd", [])
    cats = [h.category for h in report.hypotheses]
    assert HypothesisCategory.DESIGN_BUG not in cats
    assert report.top_hypothesis().category == HypothesisCategory.ENVIRONMENT_ISSUE


def test_reset_active_at_divergence_yields_reset_hypothesis():
    """If reset is active where a consequent 'fails', flag reset, not design bug."""
    trace = load_json_trace(
        {
            "timescale": "1ns",
            "signals": {
                "clk": {"width": 1, "samples": [[0, "0"], [5, "1"], [10, "0"], [15, "1"]]},
                "rst": {"width": 1, "samples": [[0, "1"]]},  # reset stuck active
                "a": {"width": 1, "samples": [[0, "1"]]},  # antecedent high
                "c": {"width": 1, "samples": [[0, "0"]]},  # consequent low
            },
        }
    )
    failure = AssertionFailure(
        property_name="p",
        source_file="f.sva",
        source_line=1,
        clock="clk",
        reset="rst",
        reset_active_high=True,
        antecedent_signal="a",
        consequent_signal="c",
        implication="non_overlapping",
        delay_min=1,
        delay_max=1,
    )
    report = TriageEngine(trace, failure, None).run("cmd", [])
    # Antecedent activations are all under reset -> no divergence, no design bug.
    assert report.first_divergence_cycle is None
    cats = [h.category for h in report.hypotheses]
    assert HypothesisCategory.DESIGN_BUG not in cats


def test_missing_signals_flagged_as_modeling_and_unresolved():
    trace = load_json_trace(
        {"timescale": "1ns", "signals": {"clk": {"width": 1, "samples": [[0, "0"], [5, "1"]]}}}
    )
    failure = AssertionFailure(
        property_name="p",
        source_file="f.sva",
        source_line=1,
        clock="clk",
        antecedent_signal="missing_a",
        consequent_signal="missing_c",
    )
    report = TriageEngine(trace, failure, None).run("cmd", [])
    cats = [h.category for h in report.hypotheses]
    assert HypothesisCategory.MODELING_ISSUE in cats
    assert any("missing" in q for q in report.unresolved_questions)


def test_invariant_style_divergence():
    """No antecedent -> invariant: first cycle consequent != 1 is the divergence."""
    trace = load_json_trace(
        {
            "timescale": "1ns",
            "signals": {
                "clk": {"width": 1, "samples": [[0, "0"], [5, "1"], [10, "0"], [15, "1"]]},
                "c": {"width": 1, "samples": [[0, "1"], [15, "0"]]},
            },
        }
    )
    failure = AssertionFailure(
        property_name="inv",
        source_file="f.sva",
        source_line=1,
        clock="clk",
        consequent_signal="c",
    )
    report = TriageEngine(trace, failure, None).run("cmd", [])
    assert report.first_divergence_cycle == 1  # posedge at t=15, c=0


def test_no_clock_edges_reported_unresolved():
    trace = load_json_trace(
        {"timescale": "1ns", "signals": {"clk": {"width": 1, "samples": [[0, "0"]]}}}
    )
    failure = AssertionFailure(
        property_name="p", source_file="f.sva", source_line=1, clock="clk",
        consequent_signal="clk",
    )
    report = TriageEngine(trace, failure, None).run("cmd", [])
    assert any("edges" in q for q in report.unresolved_questions)


def test_delay_range_validation():
    with pytest.raises(ValueError):
        AssertionFailure(
            property_name="p", source_file="f.sva", source_line=1, clock="clk",
            delay_min=3, delay_max=1,
        )
