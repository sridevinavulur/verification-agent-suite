"""Property-mutation tests.

These validate that our candidate properties are *mutable* in meaning: each
applicable operator changes the property text. A property that cannot be mutated
by any operator (no relations, no implication, no delay, no reset) is a red flag
worth surfacing -- we assert the whole suite produces a healthy number of
distinct mutants and that no mutant equals its original.
"""

from __future__ import annotations

import pytest

from protocol_contract_agent import mutation
from protocol_contract_agent.generator import generate_contract
from tests.conftest import ALL_NAMES, _pair


def test_flip_relational():
    m = mutation.flip_relational("count <= 16")
    assert m is not None
    assert m.mutated == "count >= 16"
    # symmetric swap, not left unchanged
    assert m.mutated != m.original


def test_flip_relational_eq_ne():
    m = mutation.flip_relational("empty == (count == 0)")
    assert m is not None
    assert "!=" in m.mutated
    assert "==" not in m.mutated.replace("!=", "")


def test_flip_implication_both_directions():
    m = mutation.flip_implication("a |-> b")
    assert m.mutated == "a |=> b"
    m2 = mutation.flip_implication("a |=> b")
    assert m2.mutated == "a |-> b"
    # a body with both should still change
    m3 = mutation.flip_implication("(a) |-> ##[1:3] (b)")
    assert "|=>" in m3.mutated


def test_shift_delay_range_and_single():
    m = mutation.shift_delay("(a) |-> ##[1:3] (b)")
    assert "##[1:4]" in m.mutated
    m2 = mutation.shift_delay("(a) |-> ##2 (b)")
    assert "##3" in m2.mutated


def test_flip_reset_pol():
    m = mutation.flip_reset_pol("@(posedge clk) disable iff (!rst_n) x")
    assert "disable iff (rst_n)" in m.mutated
    m2 = mutation.flip_reset_pol("@(posedge clk) disable iff (rst) x")
    assert "disable iff (!rst)" in m2.mutated


def test_operator_not_applicable_returns_none():
    # no relational operators
    assert mutation.flip_relational("a && b") is None
    # no implication
    assert mutation.flip_implication("count <= 16") is None
    # no delay
    assert mutation.shift_delay("a |-> b") is None
    # no reset
    assert mutation.flip_reset_pol("@(posedge clk) a |-> b") is None


@pytest.mark.parametrize("name", ALL_NAMES)
def test_generated_properties_are_mutable(name):
    """Every generated contract yields at least one non-trivial mutant, and no
    mutant is identical to its source."""
    req, man = _pair(name)
    c = generate_contract(req, man)
    total = 0
    for p in c.properties:
        for mut in mutation.mutate_all(p.sva_text):
            assert mut.mutated != mut.original, (
                f"{p.name} operator {mut.operator} produced no change"
            )
            total += 1
    assert total > 0, f"{name}: no mutants generated for any property"


def test_no_two_distinct_properties_collide_after_mutation():
    """A mutation should not accidentally turn one property into a copy of another
    emitted property (which would mask a real bug)."""
    for name in ALL_NAMES:
        req, man = _pair(name)
        c = generate_contract(req, man)
        originals = {p.sva_text for p in c.properties}
        for p in c.properties:
            others = originals - {p.sva_text}
            for mut in mutation.mutate_all(p.sva_text):
                assert mut.mutated not in others, (
                    f"{name}: mutating {p.name} collided with another property"
                )
