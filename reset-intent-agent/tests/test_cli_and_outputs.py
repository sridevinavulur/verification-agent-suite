import json

from typer.testing import CliRunner

from reset_intent_agent.agent import analyze_rtl_file
from reset_intent_agent.cli import app
from reset_intent_agent.graph import to_dot
from reset_intent_agent.models import ResetIntentManifest
from reset_intent_agent.report import render_markdown

runner = CliRunner()


def test_cli_analyze_valid_json(rtl_dir):
    res = runner.invoke(app, ["analyze", str(rtl_dir / "counter_async_low.sv")])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    # round-trips through the model
    ResetIntentManifest.model_validate(data)
    assert data["design_top"] == "counter_async_low"


def test_cli_graph_dot(rtl_dir):
    res = runner.invoke(app, ["graph", str(rtl_dir / "dual_reset_domains.sv")])
    assert res.exit_code == 0
    assert res.output.startswith("digraph")
    assert "RDC?" in res.output  # crossing rendered


def test_cli_report_markdown(rtl_dir):
    res = runner.invoke(app, ["report", str(rtl_dir / "ambiguous_polarity.sv")])
    assert res.exit_code == 0
    assert "HEURISTIC" in res.output
    assert "not inferred silently" in res.output.lower() or "unknown" in res.output.lower()


def test_cli_sva(rtl_dir):
    res = runner.invoke(app, ["sva", str(rtl_dir / "counter_async_low.sv")])
    assert res.exit_code == 0
    assert "assert property" in res.output
    assert "status=candidate" in res.output


def test_cli_mutate(rtl_dir):
    res = runner.invoke(app, ["mutate", str(rtl_dir / "counter_async_low.sv")])
    assert res.exit_code == 0
    assert "reset_polarity_flip" in res.output
    assert "reset_value_change" in res.output


def test_cli_schema():
    res = runner.invoke(app, ["schema"])
    assert res.exit_code == 0
    schema = json.loads(res.output)
    assert schema["title"] == "ResetIntentManifest"


def test_dot_is_deterministic(rtl_dir):
    m = analyze_rtl_file(rtl_dir / "dual_reset_domains.sv")
    assert to_dot(m.reset_graph) == to_dot(m.reset_graph)


def test_report_contains_candidate_sva(rtl_dir):
    m = analyze_rtl_file(rtl_dir / "sync_high_regs.sv")
    md = render_markdown(m)
    assert "CANDIDATE" in md
    assert "assert property" in md


def test_manifest_has_provenance_with_hash(rtl_dir):
    m = analyze_rtl_file(rtl_dir / "counter_async_low.sv")
    assert m.provenance.tool == "reset-intent-agent"
    assert m.provenance.input_sha256  # sha recorded
