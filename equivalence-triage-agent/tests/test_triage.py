from __future__ import annotations

from eq_triage.models import (
    CauseCategory,
    EquivalenceStatus,
    Provenance,
    SourceMap,
)
from eq_triage.parser import load_manifest, parse_equivalence_log
from eq_triage.triage import TriageEngine


def _engine(example_dir):
    log = parse_equivalence_log(
        (example_dir / "equivalence.eqlog").read_text(),
        source_path=str(example_dir / "equivalence.eqlog"),
    )
    ref = load_manifest(example_dir / "ref_manifest.json")
    rev = load_manifest(example_dir / "rev_manifest.json")
    smap = SourceMap.model_validate_json(
        (example_dir / "source_map.json").read_text()
    )
    return TriageEngine(log, ref, rev, smap)


def _prov():
    return Provenance(tool_version="0.1.0")


def _causes(group):
    return {c.category for c in group.likely_causes}


def test_status_is_echoed_not_inferred(toy_alu):
    report = _engine(toy_alu).run(_prov())
    assert report.reported_status is EquivalenceStatus.NOT_EQUIVALENT
    assert any("status" in e for e in report.status_evidence)


def test_signature_grouping_collapses_bit_indices(toy_alu):
    report = _engine(toy_alu).run(_prov())
    # result[7], result[6] share a signature (both have CEX + fanin);
    # result[5], result[4] share another (no CEX). So grouping < 5 distinct.
    assert len(report.groups) < report.mismatch_count
    total_members = sum(g.count for g in report.groups)
    assert total_members == report.mismatch_count


def test_width_cause_detected(toy_alu):
    report = _engine(toy_alu).run(_prov())
    width_group = next(g for g in report.groups if g.width_ref != g.width_rev)
    assert CauseCategory.WIDTH in _causes(width_group)
    wc = next(c for c in width_group.likely_causes
              if c.category is CauseCategory.WIDTH)
    assert wc.confidence >= 0.8
    assert wc.is_heuristic is True


def test_polarity_cause_detected(toy_alu):
    report = _engine(toy_alu).run(_prov())
    assert any(CauseCategory.POLARITY in _causes(g) for g in report.groups)


def test_config_delta_surfaced_and_warned(toy_alu):
    report = _engine(toy_alu).run(_prov())
    assert report.has_config_differences
    assert any("configuration" in w.lower() for w in report.warnings)
    # a config_constraint cause should appear somewhere
    assert any(CauseCategory.CONFIG_CONSTRAINT in _causes(g)
               for g in report.groups)


def test_reset_comparison(toy_alu):
    report = _engine(toy_alu).run(_prov())
    rc = report.reset_comparison
    assert rc.polarity_differs is True
    assert rc.sync_differs is True


def test_ranked_locations_prioritize_compare_points(toy_alu):
    report = _engine(toy_alu).run(_prov())
    width_group = next(g for g in report.groups if g.width_ref != g.width_rev)
    top = width_group.ranked_locations[0]
    assert top.score >= 3.0
    assert "direct compare point" in top.reasons
    # mapped location resolved for the reference result signal
    assert top.location is not None


def test_state_encoding_and_gating_counter(toy_counter):
    report = _engine(toy_counter).run(_prov())
    all_causes = set()
    for g in report.groups:
        all_causes |= _causes(g)
    assert CauseCategory.STATE_ENCODING in all_causes
    assert CauseCategory.GATING in all_causes
    assert CauseCategory.WIDTH in all_causes


def test_debug_packet_built(toy_alu):
    report = _engine(toy_alu).run(
        _prov(), repro_command="eq-triage demo toy_alu"
    )
    dp = report.debug_packet
    assert dp is not None
    assert dp.repro_command == "eq-triage demo toy_alu"
    assert dp.focus_compare_points
    # config-diff step must be first when configs differ
    assert "Reconcile configuration" in dp.suggested_next_steps[0]


def test_inconclusive_status_warns_and_no_false_claim():
    log = parse_equivalence_log(
        "EQLOG/1\ntool: t\nreference: a\nrevised: b\nstatus: TIMEOUT\n"
        "compare_points: 0/5\n"
    )
    report = TriageEngine(log).run(_prov())
    assert report.reported_status is EquivalenceStatus.TIMEOUT
    assert any("advisory" in w.lower() for w in report.warnings)


def test_equivalent_log_has_no_mismatch_groups(toy_alu):
    log = parse_equivalence_log(
        (toy_alu / "equivalent.eqlog").read_text()
    )
    report = TriageEngine(log).run(_prov())
    assert report.reported_status is EquivalenceStatus.EQUIVALENT
    assert report.groups == []


def test_determinism_same_input_same_output(toy_alu):
    r1 = _engine(toy_alu).run(_prov())
    r2 = _engine(toy_alu).run(_prov())
    assert r1.model_dump_json() == r2.model_dump_json()
