import json

from reset_intent_agent.agent import analyze_manifest_file
from reset_intent_agent.manifest_adapter import parsed_modules_from_manifest
from reset_intent_agent.models import ResetPolarity, ResetSync


def test_manifest_interop_counter(manifest_dir):
    m = analyze_manifest_file(manifest_dir / "counter_manifest.json")
    assert m.design_top == "counter_async_low"
    rc = {c.signal: c for c in m.reset_candidates}
    assert "rst_n" in rc
    assert rc["rst_n"].polarity == ResetPolarity.ACTIVE_LOW
    assert rc["rst_n"].sync == ResetSync.ASYNCHRONOUS
    tgt = {t.register_name: t for t in m.reset_targets}
    assert tgt["count"].reset_value == "8'b0"


def test_manifest_ports_mapped(manifest_dir):
    data = json.loads((manifest_dir / "counter_manifest.json").read_text())
    mods = parsed_modules_from_manifest(data)
    assert mods[0].name == "counter_async_low"
    names = {p.name for p in mods[0].ports}
    assert {"clk", "rst_n", "en", "count"} <= names


def test_manifest_candidate_sva_generated(manifest_dir):
    m = analyze_manifest_file(manifest_dir / "counter_manifest.json")
    assert m.candidate_sva
    p = m.candidate_sva[0]
    assert "(!rst_n)" in p.sva_text
    assert p.status.value == "candidate"
