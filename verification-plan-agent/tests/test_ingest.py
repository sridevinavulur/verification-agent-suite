"""Tests for input loading and canonical-manifest projection."""

from __future__ import annotations

import json
from pathlib import Path

from vplan_agent.ingest import (
    load_manifest_view,
    load_spec,
    project_manifest,
)


def test_project_manifest_uses_canonical_fields():
    manifest = {
        "top": "m",
        "modules": [
            {
                "name": "m",
                "ports": [
                    {"name": "clk", "direction": "input"},
                    {"name": "q", "direction": "output"},
                ],
                "reset_candidates": [{"signal": "rst_n"}],
                "clock_candidates": [{"signal": "clk"}],
                "registers": [{"name": "a"}, {"name": "b"}],
                "nets": [{"name": "mem", "is_memory": True}],
            }
        ],
    }
    view = project_manifest(manifest)
    assert view.top == "m"
    mod = view.modules[0]
    assert [p.name for p in mod.ports] == ["clk", "q"]
    assert mod.reset_candidate_signals == ["rst_n"]
    assert mod.clock_candidate_signals == ["clk"]
    assert mod.register_count == 2
    assert mod.has_memory is True


def test_project_manifest_ignores_extra_fields():
    # The real ingestor emits confidence/rationale/location etc.
    manifest = {
        "modules": [
            {
                "name": "m",
                "location": {"file": "f", "line": 1, "col": 1, "end_line": 1, "end_col": 1},
                "ports": [{"name": "clk", "direction": "input", "net_kind": "wire",
                           "location": {"file": "f", "line": 1, "col": 1, "end_line": 1, "end_col": 1}}],
                "reset_candidates": [{"signal": "rst", "confidence": 1.0,
                                      "polarity": "unknown", "sync": "unknown"}],
            }
        ],
    }
    view = project_manifest(manifest)
    assert view.modules[0].ports[0].name == "clk"
    assert view.modules[0].reset_candidate_signals == ["rst"]


def test_bundled_manifest_conforms_to_canonical_schema():
    root = Path(__file__).resolve().parent.parent
    schema_path = (
        root.parent / "rtl-intent-ingestor" / "schemas" / "manifest.schema.json"
    )
    manifest_path = root / "examples" / "fifo_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    view = project_manifest(manifest)
    # Required top-level keys of the canonical schema are present in our example.
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        for key in schema.get("required", []):
            assert key in manifest, f"canonical-required key {key!r} missing"
    assert view.top == "sync_fifo"
    assert view.modules[0].has_memory is True


def test_load_manifest_view_none_is_empty():
    view = load_manifest_view(None)
    assert view.modules == []


def test_load_spec_example():
    root = Path(__file__).resolve().parent.parent
    spec = load_spec(root / "examples" / "fifo_spec.json")
    assert spec.design_name == "sync_fifo"
    assert len(spec.requirements) == 6
