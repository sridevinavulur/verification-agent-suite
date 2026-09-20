"""Grounding + ownership classification tests."""

from __future__ import annotations

import pytest

from protocol_contract_agent.grounding import (
    GroundingError,
    ground_signal,
    require_signal,
    resolve_clock,
    resolve_reset,
)
from protocol_contract_agent.models import (
    ResetPolarity,
    ResetSync,
    SignalOwnership,
)


def test_ownership_from_direction(fifo_pair):
    _, man = fifo_pair
    mod = man.module("sync_fifo")
    assert ground_signal(mod, "wr_en").ownership == SignalOwnership.ENV_INPUT
    assert ground_signal(mod, "full").ownership == SignalOwnership.DUT_OUTPUT
    # count is both a port(output) and a register -> port wins (output)
    assert ground_signal(mod, "count").ownership == SignalOwnership.DUT_OUTPUT


def test_require_signal_raises_when_absent(fifo_pair):
    _, man = fifo_pair
    mod = man.module("sync_fifo")
    with pytest.raises(GroundingError):
        require_signal(mod, "does_not_exist")


def test_resolve_clock_prefers_request(valid_ready_pair):
    _, man = valid_ready_pair
    mod = man.module("vr_producer")
    assert resolve_clock(mod, "clk").name == "clk"
    # falls back to best candidate when unspecified
    assert resolve_clock(mod, None).name == "clk"


def test_resolve_reset_uses_manifest_polarity_not_name(valid_ready_pair):
    _, man = valid_ready_pair
    mod = man.module("vr_producer")
    sym, pol, sync = resolve_reset(mod, "rst_n", None)
    assert sym.name == "rst_n"
    assert pol == ResetPolarity.ACTIVE_LOW
    assert sync == ResetSync.ASYNCHRONOUS


def test_resolve_reset_forced_polarity_overrides(valid_ready_pair):
    _, man = valid_ready_pair
    mod = man.module("vr_producer")
    _, pol, _ = resolve_reset(mod, "rst_n", ResetPolarity.ACTIVE_HIGH)
    assert pol == ResetPolarity.ACTIVE_HIGH


def test_resolve_reset_unknown_when_no_candidate():
    from protocol_contract_agent.models import MModule
    mod = MModule(name="m", ports=[])
    sym, pol, sync = resolve_reset(mod, None, None)
    assert sym is None
    assert pol == ResetPolarity.UNKNOWN
