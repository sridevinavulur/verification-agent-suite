from __future__ import annotations

import json

from sva_intent_engine.llm_adapter import MockLLMAdapter
from sva_intent_engine.schema_export import EXPORTS, export_all


def test_export_all_writes_schemas(tmp_path):
    written = export_all(tmp_path)
    assert len(written) == len(EXPORTS)
    for p in written:
        data = json.loads(p.read_text())
        assert "properties" in data or "$defs" in data


def test_mock_llm_is_deterministic_and_offline():
    adapter = MockLLMAdapter(canned={"hi": "there"})
    assert adapter.provider == "mock"
    assert adapter.propose("hi") == "there"
    # unknown prompt returns a fixed marker, never a signal name
    out = adapter.propose("what is the clock?")
    assert "mock-llm" in out
