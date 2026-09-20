from __future__ import annotations

import json

from typer.testing import CliRunner

from sva_intent_engine.cli import app
from sva_intent_engine.models import Requirement, RTLManifest, RTLSymbol
from sva_intent_engine.pipeline import run_full

runner = CliRunner()


def _man() -> RTLManifest:
    return RTLManifest(
        design_top="dut",
        clock_candidates=["clk"],
        reset_candidates=["rst_n"],
        symbols=[
            RTLSymbol(symbol_id="s_clk", name="clk", kind="clock"),
            RTLSymbol(
                symbol_id="s_rstn", name="rst_n", kind="reset",
                signal_type="active_low",
            ),
            RTLSymbol(symbol_id="s_full", name="full", kind="port"),
            RTLSymbol(symbol_id="s_overflow", name="overflow", kind="reg"),
        ],
    )


def test_unresolved_term_blocks_emission():
    # 'ghost' has no symbol -> emission must stop for that clause.
    req = Requirement(
        requirement_id="r",
        source_text="When ghost is high, overflow must be low on the next cycle.",
    )
    report = run_full(req, _man())
    assert all(not v.emitted for v in report.validations)


def test_ambiguity_clause_not_emitted():
    req = Requirement(requirement_id="r", source_text="grant must arrive soon.")
    report = run_full(req, _man())
    # vague -> ambiguity -> no intent built
    assert report.intents == []


def test_review_report_contains_non_claims():
    req = Requirement(
        requirement_id="r",
        source_text="When full is high, overflow must be low on the next cycle.",
    )
    report = run_full(req, _man())
    assert any("CANDIDATE" in nc for nc in report.non_claims)
    assert len(report.checklist) >= 5


def test_cli_demo_runs():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "TOTAL candidate properties emitted: 5" in result.stdout


def test_cli_ingest_json(tmp_path):
    f = tmp_path / "req.md"
    f.write_text("# r\nWhen full is high, overflow must be low on the next cycle.\n")
    result = runner.invoke(app, ["ingest", str(f)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["clauses"][0]["kind"] == "design_guarantee"


def test_cli_generate_end_to_end(tmp_path):
    rf = tmp_path / "req.md"
    rf.write_text("# r\nWhen full is high, overflow must be low on the next cycle.\n")
    mf = tmp_path / "man.json"
    mf.write_text(_man().model_dump_json())
    result = runner.invoke(app, ["generate", str(rf), str(mf)])
    assert result.exit_code == 0
    assert "assert property" in result.stdout
    assert "|=>" in result.stdout
