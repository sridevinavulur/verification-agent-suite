"""Tests for the OPTIONAL real-coverage ingestion path.

These prove the Verilator ``.dat`` + lcov ``.info`` ingester and the heuristic
unreachability classifier work, and that their normalized output flows straight
into the existing deterministic triage engine -- without touching the default
mock pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from coverage_closure_agent.cli import app
from coverage_closure_agent.models import CoverageKind, TriageInputs
from coverage_closure_agent.real_coverage import (
    REAL_COV_FORMAT_VERSION,
    UNREACHABILITY_CATEGORIES,
    classify_unreachable,
    extract_toggle_coverage,
    ingest_real_coverage,
    ingest_real_inputs,
    parse_coverage_dat,
    parse_lcov,
)
from coverage_closure_agent.triage import TriageEngine

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "real"
DAT = EXAMPLES / "sample_coverage.dat"
INFO = EXAMPLES / "sample.info"

runner = CliRunner()


# --- Verilator .dat parsing ------------------------------------------------


def test_parse_coverage_dat_counts():
    counts = parse_coverage_dat(DAT)
    assert counts["top.dut.fifo.wr_ptr__0"] == 42
    assert counts["top.dut.fifo.full__1"] == 0
    assert counts["top.dut.counter.to_cnt__0"] == 0
    # 12 C-lines in the fixture.
    assert len(counts) == 12


def test_parse_coverage_dat_missing_file_is_empty():
    assert parse_coverage_dat(EXAMPLES / "nope.dat") == {}


def test_extract_toggle_coverage():
    counts = parse_coverage_dat(DAT)
    covered, total, uncovered = extract_toggle_coverage(counts)
    assert total > covered  # some transitions are uncovered
    assert ("top.dut.fifo.full", "1->0") in uncovered
    assert ("top.dut.fifo.wr_ptr", "0->1") not in uncovered  # covered (42)


# --- lcov .info parsing ----------------------------------------------------


def test_parse_lcov_lines_and_branches():
    items = parse_lcov(INFO)
    ids = {it.coverage_id: it for it in items}
    # DA line records
    assert ids["cov.fifo.line.10"].hits == 42
    assert ids["cov.fifo.line.20"].hits == 0  # uncovered line -> hole
    assert ids["cov.fifo.line.20"].kind == CoverageKind.STATEMENT
    # BRDA branch records; taken='-' means not taken -> 0
    assert ids["cov.fifo.branch.20.0.1"].hits == 0
    assert ids["cov.fifo.branch.20.0.0"].hits == 42
    assert ids["cov.fifo.branch.20.0.1"].kind == CoverageKind.BRANCH


def test_parse_lcov_missing_file_is_empty():
    assert parse_lcov(EXAMPLES / "nope.info") == []


# --- Heuristic unreachability classifier -----------------------------------


def test_classify_unreachable_categories():
    assert classify_unreachable("top.dut.pad.PREADY", "0->1") == "hardwired_constant"
    assert classify_unreachable("top.dut.misc.reserved", "0->1") == "dead_code"
    assert classify_unreachable("top.dut.arbiter.dead_branch", "0->1") == "dead_code"
    assert classify_unreachable("top.dut.counter.to_cnt", "0->1") == "counter_ceiling"
    assert classify_unreachable("top.dut.arbiter.clksel", "0->1") == "arch_limit"
    assert classify_unreachable("top.dut.fifo.full", "1->0") == "unknown"


def test_classify_unreachable_returns_known_vocab():
    for sig in ["PREADY", "reserved", "to_cnt", "clksel", "spec_gap", "random_sig"]:
        assert classify_unreachable(sig) in UNREACHABILITY_CATEGORIES


# --- Normalized CoverageDB output ------------------------------------------


def test_ingest_real_coverage_shape():
    cov = ingest_real_coverage(dat_path=DAT, lcov_path=INFO)
    assert cov.format_version == REAL_COV_FORMAT_VERSION
    assert cov.tool == "verilator+lcov"
    assert len(cov.items) > 0
    # Deterministic ordering by coverage_id.
    ids = [it.coverage_id for it in cov.items]
    assert ids == sorted(ids)


def test_ingest_marks_structural_unreachable_as_exclusion():
    cov = ingest_real_coverage(dat_path=DAT)
    excluded = {it.coverage_id for it in cov.items if it.exclusion_pragma}
    # PREADY (hardwired) + reserved (dead_code) uncovered toggles get flagged.
    assert any("PREADY" in i for i in excluded)
    assert any("reserved" in i for i in excluded)
    # A covered signal is never flagged.
    covered = [it for it in cov.items if it.hits > 0]
    assert all(not it.exclusion_pragma for it in covered)


def test_ingest_deterministic():
    a = ingest_real_coverage(dat_path=DAT, lcov_path=INFO)
    b = ingest_real_coverage(dat_path=DAT, lcov_path=INFO)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


# --- Full bundle flows into triage -----------------------------------------


def test_ingest_real_inputs_is_valid_bundle():
    bundle = ingest_real_inputs(dat_path=DAT, lcov_path=INFO)
    assert isinstance(bundle, TriageInputs)
    # Empty-but-valid companion manifests.
    assert bundle.tests.tests == []
    assert bundle.requirements.links == []
    # RTL modules derived from observed coverage.
    module_names = {m.name for m in bundle.rtl.modules}
    assert {"fifo", "arbiter", "counter", "pad"} <= module_names


def test_normalized_output_flows_into_triage():
    bundle = ingest_real_inputs(dat_path=DAT, lcov_path=INFO)
    report = TriageEngine(seed=0).run(bundle)
    holes = [it for it in bundle.coverage.items if not it.is_covered]
    assert report.scope_provenance.total_holes == len(holes)
    assert len(report.classifications) == len(holes)
    # Structural-unreachable points route to likely_unreachable (inspect/waiver).
    cats = {c.coverage_id: c.category.value for c in report.classifications}
    preadys = [cid for cid in cats if "PREADY" in cid]
    assert preadys and all(cats[cid] == "likely_unreachable" for cid in preadys)
    # Every classification is still heuristic + human-gated (never a closure claim).
    assert all(c.is_heuristic for c in report.classifications)
    assert len(report.human_review_queue) == len(holes)
    assert len(report.independent_measurement) == len(holes)


# --- CLI subcommand --------------------------------------------------------


def test_cli_ingest_real_emits_bundle(tmp_path):
    out = tmp_path / "bundle.json"
    result = runner.invoke(
        app,
        ["ingest-real", "--dat", str(DAT), "--lcov", str(INFO), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    # Re-validates as a proper inputs bundle.
    TriageInputs.model_validate(data)
    assert data["coverage"]["format_version"] == REAL_COV_FORMAT_VERSION


def test_cli_ingest_real_then_triage():
    result = runner.invoke(
        app, ["ingest-real", "--dat", str(DAT), "--triage"]
    )
    assert result.exit_code == 0, result.output
    # The final JSON object printed is a triage report.
    assert "classifications" in result.output
    assert "scope_provenance" in result.output


def test_cli_ingest_real_requires_a_source():
    result = runner.invoke(app, ["ingest-real"])
    assert result.exit_code != 0
