"""Grounding, generator, and LLM-authority-boundary tests."""

from __future__ import annotations

from pathlib import Path

from register_csr_agent.generators import (
    generate_directed_tests,
    generate_sva,
)
from register_csr_agent.grounding import ground
from register_csr_agent.llm_adapter import MockLLM, annotate_discrepancies
from register_csr_agent.models import Discrepancy, Severity
from register_csr_agent.parsers import load_register_map
from register_csr_agent.rtl_symbols import load_rtl_symbols

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "examples" / "register_maps"
RTL = ROOT / "examples" / "rtl_symbols"


def test_grounding_exact_and_unmatched():
    m = load_register_map(MAPS / "timer_block.yaml")
    rtl = load_rtl_symbols(RTL / "timer_block.json")
    rep = ground(m, rtl)
    matched = {r.manifest_name for r in rep.results if r.matched}
    assert {"CTRL", "LOAD", "COUNT", "STATUS"} <= matched
    assert rep.matched_count == rep.total_count


def test_grounding_intent_manifest_source():
    m = load_register_map(MAPS / "timer_block.json")
    rtl = load_rtl_symbols(RTL / "timer_block.intent.json")
    assert rtl.module == "timer_block"
    rep = ground(m, rtl)
    assert {r.rtl_symbol for r in rep.results if r.matched} >= {"CTRL", "LOAD", "COUNT"}
    assert "STATUS" in rep.unmatched_rtl  # in RTL, absent from this manifest


def test_grounding_no_false_positive():
    m = load_register_map(MAPS / "gpio_block.csv")
    rtl = load_rtl_symbols(RTL / "timer_block.json")  # unrelated RTL
    rep = ground(m, rtl)
    assert rep.matched_count == 0
    assert set(rep.unmatched_manifest) == {"DATA", "DIR", "INT_STAT"}


def test_sva_all_candidate_and_covers_access_types():
    m = load_register_map(MAPS / "timer_block.yaml")
    sva = generate_sva(m)
    assert all(s.status == "candidate" for s in sva)
    checks = {s.check for s in sva}
    assert {"reset_value", "readback", "illegal_write", "side_effects"} <= checks
    # W1C field yields a clear assertion
    w1c = [s for s in sva if "w1c_clear" in s.name]
    assert w1c and "== 'h0" in w1c[0].sva


def test_directed_tests_generated():
    m = load_register_map(MAPS / "timer_block.yaml")
    tests = generate_directed_tests(m)
    names = {t.name for t in tests}
    assert any("reset" in n for n in names)
    assert any("w1c" in n for n in names)


def test_llm_cannot_change_code_or_severity():
    d = Discrepancy(code="ADDR_OVERLAP", severity=Severity.ERROR, message="x")
    before = (d.code, d.severity, d.message)
    annotate_discrepancies([d], MockLLM())
    after = (d.code, d.severity, d.message)
    assert before == after
    assert d.explanation != ""  # only explanation added


def test_llm_does_not_fabricate_discrepancies():
    out = annotate_discrepancies([], MockLLM())
    assert out == []
