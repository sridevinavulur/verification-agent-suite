"""Tests for canonical RTL Intent Manifest interop (task 3)."""

import json

from cx_triage.manifest_adapter import from_canonical_manifest, load_manifest
from cx_triage.models import AssertionFailure, RTLIntentManifest
from cx_triage.triage import TriageEngine


def _canonical_path(examples_dir):
    return examples_dir / "toy_counter" / "manifest_canonical.json"


def test_native_fixture_still_loads(examples_dir):
    """Back-compat: the repo's native manifest fixture is unchanged behavior."""
    p = examples_dir / "toy_counter" / "manifest.json"
    m = load_manifest(p)
    assert isinstance(m, RTLIntentManifest)
    assert m.design_top == "counter"
    assert "tb.count" in m.symbols
    # Native drivers are taken verbatim (self-loop preserved as authored).
    assert "tb.stall" in m.symbols["tb.count"].drivers


def test_canonical_manifest_detected_and_projected(examples_dir):
    m = load_manifest(_canonical_path(examples_dir))
    assert m.design_top == "counter"
    # Symbols are qualified as <top>.<name> by default.
    assert set(m.symbols) == {
        "counter.clk",
        "counter.rst",
        "counter.en",
        "counter.stall",
        "counter.count",
    }
    count = m.symbols["counter.count"]
    assert count.kind == "reg"
    # Fan-in reconstructed from procedure condition + RHS signals; self-loop dropped.
    assert count.drivers == ["counter.en", "counter.rst", "counter.stall"]
    assert m.symbols["counter.clk"].is_clock is True
    assert m.symbols["counter.rst"].is_reset is True


def test_canonical_unqualified_names(examples_dir):
    doc = json.loads(_canonical_path(examples_dir).read_text())
    m = from_canonical_manifest(doc, qualify=False)
    assert set(m.symbols["count"].drivers) == {"en", "rst", "stall"}


def test_canonical_manifest_drives_cone_traversal(examples_dir):
    """The projected manifest feeds the real cone traversal end-to-end."""
    m = load_manifest(_canonical_path(examples_dir))
    failure = AssertionFailure(
        property_name="p_inc",
        source_file="examples/toy_counter/counter.sva",
        source_line=11,
        clock="counter.clk",
        reset="counter.rst",
        antecedent_signal="counter.en",
        consequent_signal="counter.count",
        implication="non_overlapping",
        delay_min=1,
        delay_max=1,
    )
    # Minimal trace: no divergence needed; we only exercise cone + citations.
    from cx_triage.parser import load_json_trace

    trace = load_json_trace(
        {
            "timescale": "1ns",
            "signals": {
                "counter.clk": {"width": 1, "samples": [[0, "0"], [5, "1"]]},
            },
        }
    )
    report = TriageEngine(trace, failure, m).run("cmd", [])
    # The bug source `stall` must be reachable in the cone of `count`.
    assert "counter.stall" in report.rtl_cone
    assert "counter.count" in report.rtl_cone
    # Citations reference the projected source locations.
    cited = {c.symbol for c in report.citations}
    assert "counter.stall" in cited


def test_self_loop_dropped_and_foreign_refs_skipped():
    """A registered feedback (count uses count) never creates a self driver."""
    doc = {
        "top": "m",
        "modules": [
            {
                "name": "m",
                "location": {"file": "m.sv", "line": 1, "col": 1, "end_line": 9, "end_col": 1},
                "ports": [
                    {"name": "q", "direction": "output", "net_kind": "reg",
                     "location": {"file": "m.sv", "line": 2, "col": 1,
                                  "end_line": 2, "end_col": 5}},
                ],
                "continuous_assigns": [
                    {"lhs": "q", "rhs": "q & external_thing",
                     "location": {"file": "m.sv", "line": 3, "col": 1,
                                  "end_line": 3, "end_col": 5}},
                ],
            }
        ],
        "parser": {"adapter": "t", "adapter_version": "0"},
        "provenance": {"tool_version": "0"},
    }
    m = from_canonical_manifest(doc)
    # q's only RHS refs are itself (dropped) and a foreign name (skipped) -> no drivers.
    assert m.symbols["m.q"].drivers == []
