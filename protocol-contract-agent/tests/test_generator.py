"""End-to-end generator + safety-rule tests."""

from __future__ import annotations

import pytest

from protocol_contract_agent.generator import (
    _all_referenced_grounded,
    generate_contract,
)
from protocol_contract_agent.models import (
    ContractRequest,
    PropertyKind,
    ProtocolKind,
)
from tests.conftest import ALL_NAMES, _pair


@pytest.mark.parametrize("name", ALL_NAMES)
def test_generate_all_examples(name):
    req, man = _pair(name)
    c = generate_contract(req, man)
    assert c.protocol.value == name
    assert c.properties, f"{name} produced no properties"
    assert c.checklist, f"{name} produced no checklist"


@pytest.mark.parametrize("name", ALL_NAMES)
def test_every_property_is_grounded(name):
    """Safety: every property references only grounded symbols."""
    req, man = _pair(name)
    c = generate_contract(req, man)
    assert _all_referenced_grounded(c)
    for p in c.properties:
        assert p.referenced_symbols, f"{p.name} references no symbols"
        for s in p.referenced_symbols:
            assert s.symbol_id
            # symbol_id namespaces to the module
            assert s.symbol_id.startswith(c.module + ".")


def test_missing_required_role_blocks_generation(valid_ready_pair):
    _, man = valid_ready_pair
    req = ContractRequest(
        protocol=ProtocolKind.VALID_READY,
        module="vr_producer",
        roles={"valid": "out_valid"},  # missing 'ready'
        clock="clk",
        reset="rst_n",
    )
    c = generate_contract(req, man)
    assert not c.properties  # blocked, nothing fabricated
    codes = {w.code for w in c.warnings}
    assert "missing_required_role" in codes


def test_unknown_reset_polarity_skips_polarity_properties(fifo_pair):
    req, man = fifo_pair
    # wipe the reset candidate polarity by not binding a reset and clearing cands
    mod = man.module("sync_fifo")
    mod.reset_candidates = []
    req2 = req.model_copy(update={"reset": "rst_n"})
    c = generate_contract(req2, man)
    # reset polarity now unknown -> reset_empty guarantee must be skipped
    names = {p.name for p in c.properties}
    assert "p_sync_fifo_reset_empty" not in names
    codes = {w.code for w in c.warnings}
    assert "reset_polarity_unknown" in codes


def test_assume_never_silently_constrains_output(req_grant_pair):
    """req/grant: the req-stable assumption guard references grant (a DUT output).
    It must be flagged for review, not silently accepted."""
    req, man = req_grant_pair
    c = generate_contract(req, man)
    assumes = [a for a in c.assumptions if not a.ownership_ok]
    assert assumes, "expected an assumption referencing a non-input to be flagged"
    assert any(a.review_reason for a in assumes)
    assert any(w.code == "assume_on_output" for w in c.warnings)


def test_no_latency_bound_omits_grant_latency():
    _, man = _pair("req_grant")
    req = ContractRequest(
        protocol=ProtocolKind.REQ_GRANT,
        module="arbiter",
        roles={"req": "req0", "grant": "gnt0"},
        clock="clk",
        reset="rst",
        # no max_delay
    )
    c = generate_contract(req, man)
    names = {p.name for p in c.properties}
    assert "p_arbiter_grant_latency" not in names
    assert any(w.code == "no_latency_bound" for w in c.warnings)


def test_fifo_models_multiple_outstanding_not_single():
    req, man = _pair("fifo")
    c = generate_contract(req, man)
    count_bound = next(p for p in c.properties if p.name.endswith("count_bound"))
    assert "count <= 16" in count_bound.sva_text
    assert "MULTIPLE outstanding" in count_bound.description


def test_credit_no_send_without_credit_is_assert():
    req, man = _pair("credit")
    c = generate_contract(req, man)
    p = next(p for p in c.properties if p.name.endswith("no_send_without_credit"))
    assert p.property_kind == PropertyKind.ASSERT
    assert "credits == 0" in p.sva_text


def test_dependencies_are_recorded():
    req, man = _pair("req_grant")
    c = generate_contract(req, man)
    dep = next((d for d in c.dependencies if d.property_name.endswith("grant_latency")), None)
    assert dep is not None
    assert any(x.endswith("no_spurious_grant") for x in dep.depends_on)


def test_module_not_found_raises():
    _, man = _pair("fifo")
    req = ContractRequest(protocol=ProtocolKind.FIFO, module="nope",
                          roles={"push": "a", "pop": "b"})
    with pytest.raises(ValueError):
        generate_contract(req, man)


def test_limitations_present_on_every_contract():
    for name in ALL_NAMES:
        req, man = _pair(name)
        c = generate_contract(req, man)
        assert c.limitations
        assert any("CANDIDATE" in lim for lim in c.limitations)


def test_provenance_records_protocol_and_module():
    req, man = _pair("interrupt")
    c = generate_contract(req, man, git_sha="deadbeef", command="test")
    assert c.provenance.git_sha == "deadbeef"
    assert c.provenance.protocol == ProtocolKind.INTERRUPT
    assert c.provenance.manifest_module == "irq_ctrl"


def test_output_role_produces_guarantee_not_assumption(valid_ready_pair):
    """valid is a DUT output here -> valid-stable is a guarantee, not an assume."""
    req, man = valid_ready_pair
    c = generate_contract(req, man)
    vs = next(p for p in c.properties if p.name.endswith("valid_stable"))
    assert vs.property_kind == PropertyKind.ASSERT
    assert vs.role == "guarantee"


def test_input_valid_produces_assumption():
    """If 'valid' is an input, valid-stable must be an assumption on the env."""
    _, man = _pair("valid_ready")
    mod = man.module("vr_producer")
    # flip out_valid to an input for this scenario
    for p in mod.ports:
        if p.name == "out_valid":
            p.direction = p.direction.INPUT
    req = ContractRequest(
        protocol=ProtocolKind.VALID_READY,
        module="vr_producer",
        roles={"valid": "out_valid", "ready": "out_ready"},
        clock="clk", reset="rst_n",
    )
    c = generate_contract(req, man)
    vs = next(p for p in c.properties if "valid_stable" in p.name)
    assert vs.property_kind == PropertyKind.ASSUME


def test_reset_state_property_has_no_disable_iff(fifo_pair):
    req, man = fifo_pair
    c = generate_contract(req, man)
    rp = next(p for p in c.properties if p.name.endswith("reset_empty"))
    assert "disable iff" not in rp.sva_text
    assert "(!rst_n) |->" in rp.sva_text
