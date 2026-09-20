from __future__ import annotations

from pathlib import Path

import pytest

from sva_intent_engine.io_utils import load_manifest, load_requirement
from sva_intent_engine.models import RTLManifest, RTLSymbol

ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = ROOT / "examples" / "requirements"
MAN_DIR = ROOT / "examples" / "rtl_manifests"

EXAMPLE_STEMS = [
    "ready_valid",
    "fifo_overflow",
    "fifo_underflow",
    "reset_state",
    "counter_saturate",
]


@pytest.fixture
def example_stems() -> list[str]:
    return EXAMPLE_STEMS


@pytest.fixture
def load_example():
    def _load(stem: str):
        req = load_requirement(REQ_DIR / f"{stem}.md")
        man = load_manifest(MAN_DIR / f"{stem}.json")
        return req, man

    return _load


@pytest.fixture
def small_manifest() -> RTLManifest:
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
            RTLSymbol(
                symbol_id="s_valid", name="valid", kind="port", direction="input",
                aliases=["vld"],
            ),
            RTLSymbol(symbol_id="s_grant", name="grant", kind="port", direction="output"),
        ],
    )
