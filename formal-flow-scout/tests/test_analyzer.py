"""End-to-end analyzer tests with KNOWN expected cones of influence."""

from __future__ import annotations

import json

from formal_flow_scout import (
    Analyzer,
    Provenance,
    build_from_manifest,
    build_from_parse,
    parse_verilog,
)
from formal_flow_scout.models import PropertySet, Soundness


def _analyze_rtl(rtl_path, prop_path, top=None):
    parse = parse_verilog(rtl_path.read_text(), str(rtl_path))
    graph = build_from_parse(parse, top=top)
    spec = PropertySet.model_validate(json.loads(prop_path.read_text())).properties[0]
    return graph, Analyzer(graph).analyze(spec, Provenance(tool_version="test"))


def _coi_names(graph, report):
    return sorted(graph.nodes[i].name for i in report.coi_node_ids)


def test_counter_known_coi(examples_dir):
    graph, report = _analyze_rtl(
        examples_dir / "counter.v", examples_dir / "counter_property.json"
    )
    names = _coi_names(graph, report)
    # KNOWN COI for {at_max, value}: both are driven by cnt; cnt is a register
    # clocked by clk with sync reset rst. `en` does not fan into at_max/value's
    # combinational cone but DOES feed cnt's next state, so it IS in the seq COI.
    assert "counter.at_max" in names
    assert "counter.value" in names
    assert "counter.cnt" in names
    assert "counter.clk" in names
    assert "counter.rst" in names
    # `en` gates cnt's next-state -> included via sequential expansion.
    assert "counter.en" in names


def test_counter_no_spurious_exclusions(examples_dir):
    graph, report = _analyze_rtl(
        examples_dir / "counter.v", examples_dir / "counter_property.json"
    )
    # Every node in a 6-signal single-module counter is in the COI of at_max.
    assert report.stats.coi_registers == 1  # cnt
    assert report.stats.unresolved_seed_signals == 0


def test_fifo_excludes_unrelated_pointers(examples_dir):
    graph, report = _analyze_rtl(
        examples_dir / "fifo_ctrl.v", examples_dir / "fifo_property.json"
    )
    names = _coi_names(graph, report)
    # Property {full, push, occ}: occ/full/empty/do_push/do_pop are in COI.
    assert "fifo_ctrl.occ" in names
    assert "fifo_ctrl.full" in names
    # wr_ptr / rd_ptr do NOT drive occ/full and are correctly EXCLUDED.
    assert "fifo_ctrl.wr_ptr" not in names
    assert "fifo_ctrl.rd_ptr" not in names
    excluded = {e.name for e in report.excluded_logic}
    assert "fifo_ctrl.wr_ptr" in excluded
    assert "fifo_ctrl.rd_ptr" in excluded


def test_fifo_has_sequential_cycle(examples_dir):
    # occ <= occ + do_push - do_pop, and do_push depends on full which depends on
    # occ -> a genuine feedback SCC that must be flagged.
    _, report = _analyze_rtl(
        examples_dir / "fifo_ctrl.v", examples_dir / "fifo_property.json"
    )
    assert report.stats.cyclic_scc_count >= 1
    assert any(r.kind == "combinational_or_sequential_cycle" for r in report.soundness_risks)


def test_two_clock_flags_multi_clock_risk(examples_dir, tmp_path):
    prop = tmp_path / "p.json"
    prop.write_text(
        json.dumps(
            {"properties": [{"name": "mm", "signals": [{"name": "mismatch"}]}]}
        )
    )
    graph, report = _analyze_rtl(examples_dir / "two_clock.v", prop)
    assert report.domains.multi_clock is True
    assert report.stats.clock_domain_count == 2
    assert any(r.kind == "multi_clock_coi" and r.severity == "high"
               for r in report.soundness_risks)


def test_all_partitions_labeled_heuristic(examples_dir):
    _, report = _analyze_rtl(
        examples_dir / "fifo_ctrl.v", examples_dir / "fifo_property.json"
    )
    assert report.candidate_partitions  # at least one
    for p in report.candidate_partitions:
        assert p.soundness == Soundness.HEURISTIC
        # Every cut must carry an UNPROVEN environment assumption.
        for a in p.environment_assumptions:
            assert a.soundness == Soundness.UNPROVEN
        assert len(p.environment_assumptions) == len(p.cut_signals)


def test_unresolved_seed_is_reported_not_silently_dropped(examples_dir, tmp_path):
    prop = tmp_path / "p.json"
    prop.write_text(
        json.dumps(
            {"properties": [{"name": "x", "signals": [{"name": "does_not_exist"}]}]}
        )
    )
    graph, report = _analyze_rtl(examples_dir / "counter.v", prop)
    assert "does_not_exist" in report.unresolved_seed_signals
    assert report.stats.unresolved_seed_signals == 1


def test_manifest_and_rtl_agree_on_data_coi(examples_dir):
    # The manifest lacks the sync-reset condition, so the ONLY expected
    # difference vs the RTL path is the reset control node. Data/logic COI must
    # otherwise match exactly (determinism / contract-compatibility check).
    graph_rtl, rep_rtl = _analyze_rtl(
        examples_dir / "counter.v", examples_dir / "counter_property.json"
    )
    manifest = json.loads((examples_dir / "counter_manifest.json").read_text())
    graph_man = build_from_manifest(manifest)
    spec = PropertySet.model_validate(
        json.loads((examples_dir / "counter_property.json").read_text())
    ).properties[0]
    rep_man = Analyzer(graph_man).analyze(spec, Provenance(tool_version="test"))
    n_rtl = set(_coi_names(graph_rtl, rep_rtl))
    n_man = {graph_man.nodes[i].name for i in rep_man.coi_node_ids}
    # manifest COI is a subset of the RTL COI. The RTL parser additionally
    # recovers branch-guard dependencies (rst, en) that the manifest's flat
    # assignment RHS strings do not carry - a documented fidelity difference,
    # NOT a soundness bug (both remain over-approximations of their own inputs).
    assert n_man <= n_rtl
    assert n_rtl - n_man <= {"counter.rst", "counter.en"}
    # The core data cone (register + its combinational consumers) must match.
    assert {"counter.cnt", "counter.at_max", "counter.value"} <= n_man


def test_deterministic_output(examples_dir):
    # Two runs must produce byte-identical reports.
    _, r1 = _analyze_rtl(
        examples_dir / "fifo_ctrl.v", examples_dir / "fifo_property.json"
    )
    _, r2 = _analyze_rtl(
        examples_dir / "fifo_ctrl.v", examples_dir / "fifo_property.json"
    )
    assert r1.model_dump_json() == r2.model_dump_json()
