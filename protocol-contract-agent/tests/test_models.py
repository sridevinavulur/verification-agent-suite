"""Schema / model validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from protocol_contract_agent.models import (
    ContractRequest,
    GroundedSymbol,
    PortDirection,
    ProtocolKind,
    RtlManifest,
    SignalOwnership,
)


def test_manifest_view_ignores_extra_fields():
    # A real rtl-intent manifest has many fields we don't model; they must not
    # break validation.
    raw = {
        "schema_version": "0.1.0",
        "top": "m",
        "parser": {"adapter": "builtin", "adapter_version": "0.1.0"},
        "provenance": {"tool_version": "0.1.0", "git_sha": "abc"},
        "unresolved": [{"kind": "generate", "detail": "unsupported"}],
        "hierarchy": [],
        "modules": [
            {
                "name": "m",
                "location": {"file": "m.sv", "line": 1, "col": 1,
                             "end_line": 1, "end_col": 2},
                "procedure_summary": {"always_ff": 1},
                "procedures": [{"index": 0, "kind": "always_ff",
                                "location": {"file": "m.sv", "line": 1, "col": 1,
                                             "end_line": 1, "end_col": 2}}],
                "ports": [
                    {"name": "clk", "direction": "input", "net_kind": "wire",
                     "location": {"file": "m.sv", "line": 1, "col": 1,
                                  "end_line": 1, "end_col": 2}}
                ],
            }
        ],
    }
    man = RtlManifest.model_validate(raw)
    assert man.top == "m"
    assert man.module("m") is not None
    assert man.module("m").ports[0].direction == PortDirection.INPUT


def test_grounded_symbol_multibit():
    s = GroundedSymbol(name="d", symbol_id="m.d", ownership=SignalOwnership.DUT_OUTPUT,
                       width_msb="WIDTH-1", width_lsb="0")
    assert s.is_multibit is True
    single = GroundedSymbol(name="v", symbol_id="m.v", ownership=SignalOwnership.ENV_INPUT)
    assert single.is_multibit is False


def test_contract_request_requires_protocol():
    with pytest.raises(ValidationError):
        ContractRequest.model_validate({"module": "m"})


def test_contract_request_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ContractRequest.model_validate(
            {"protocol": "fifo", "module": "m", "bogus": 1}
        )


def test_protocol_kind_values():
    assert {k.value for k in ProtocolKind} == {
        "valid_ready", "req_grant", "fifo", "interrupt", "credit"
    }
