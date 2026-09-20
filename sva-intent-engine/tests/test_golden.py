from __future__ import annotations

import json
from pathlib import Path

import pytest

from sva_intent_engine.pipeline import run_full

ROOT = Path(__file__).resolve().parents[1]
GOLD_INTENT = ROOT / "examples" / "golden_intent"
GOLD_SVA = ROOT / "examples" / "golden_sva"


def _canonical(intent) -> dict:
    d = intent.model_dump(mode="json")
    d.pop("provenance", None)
    return d


@pytest.mark.parametrize(
    "stem",
    ["ready_valid", "fifo_overflow", "fifo_underflow", "reset_state", "counter_saturate"],
)
def test_golden_intent_matches(stem, load_example):
    req, man = load_example(stem)
    report = run_full(req, man)
    got = [_canonical(i) for i in report.intents]
    expected = json.loads((GOLD_INTENT / f"{stem}.json").read_text())
    assert got == expected


@pytest.mark.parametrize(
    "stem",
    ["ready_valid", "fifo_overflow", "fifo_underflow", "reset_state", "counter_saturate"],
)
def test_golden_sva_matches(stem, load_example):
    req, man = load_example(stem)
    report = run_full(req, man)
    emitted = [v.candidate.sva_text for v in report.validations if v.emitted]
    got = "\n\n".join(emitted) + "\n"
    expected = (GOLD_SVA / f"{stem}.sva").read_text()
    assert got == expected


def test_all_examples_emit_one_property(load_example, example_stems):
    for stem in example_stems:
        req, man = load_example(stem)
        report = run_full(req, man)
        emitted = sum(1 for v in report.validations if v.emitted)
        assert emitted == 1, f"{stem} emitted {emitted}"
