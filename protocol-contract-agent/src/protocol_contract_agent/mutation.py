"""Property-mutation utilities for testing contract quality.

This is a *property-quality* evaluation aid, not proof of verification. Given a
rendered candidate property, apply small, well-defined mutation operators that
should change the property's meaning. A companion oracle (in tests) checks that
each mutation produces a *different* property text, and that mutations of a
guarantee/assumption do not accidentally coincide with another emitted property.

Operators (analogous to the Assertion Mutation Agent spec 5.8):
* flip_relational   : swap ``<=`` <-> ``>=`` , ``<`` <-> ``>`` , ``==`` <-> ``!=``
* negate_boolean    : wrap the antecedent/consequent in a negation
* flip_implication  : ``|->`` <-> ``|=>``
* shift_delay       : change ``##[a:b]`` -> ``##[a:b+1]``
* flip_reset_pol    : ``disable iff (!x)`` <-> ``disable iff (x)``

A mutation that does not apply returns ``None`` (invalid mutant), so tests can
distinguish "operator not applicable" from "meaning unchanged".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_REL_FLIPS = [
    ("<=", "\0LE\0"), (">=", "\0GE\0"),
    ("<", "\0LT\0"), (">", "\0GT\0"),
    ("==", "\0EQ\0"), ("!=", "\0NE\0"),
]


@dataclass
class Mutant:
    operator: str
    original: str
    mutated: str


def flip_relational(sva_text: str) -> Mutant | None:
    tmp = sva_text
    for op, tok in _REL_FLIPS:
        tmp = tmp.replace(op, tok)
    # swap tokens
    swap = {
        "\0LE\0": ">=", "\0GE\0": "<=",
        "\0LT\0": ">", "\0GT\0": "<",
        "\0EQ\0": "!=", "\0NE\0": "==",
    }
    out = tmp
    changed = False
    for tok, rep in swap.items():
        if tok in out:
            changed = True
        out = out.replace(tok, rep)
    if not changed or out == sva_text:
        return None
    return Mutant("flip_relational", sva_text, out)


def flip_implication(sva_text: str) -> Mutant | None:
    if "|->" in sva_text:
        out = sva_text.replace("|->", "\0IMP\0").replace("|=>", "|->").replace("\0IMP\0", "|=>")
    elif "|=>" in sva_text:
        out = sva_text.replace("|=>", "|->")
    else:
        return None
    if out == sva_text:
        return None
    return Mutant("flip_implication", sva_text, out)


def shift_delay(sva_text: str) -> Mutant | None:
    m = re.search(r"##\[(\d+):(\d+)\]", sva_text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        out = sva_text[: m.start()] + f"##[{lo}:{hi + 1}]" + sva_text[m.end():]
        return Mutant("shift_delay", sva_text, out)
    m2 = re.search(r"##(\d+)", sva_text)
    if m2:
        n = int(m2.group(1))
        out = sva_text[: m2.start()] + f"##{n + 1}" + sva_text[m2.end():]
        return Mutant("shift_delay", sva_text, out)
    return None


def flip_reset_pol(sva_text: str) -> Mutant | None:
    m = re.search(r"disable iff \((!?)([A-Za-z_][A-Za-z0-9_]*)\)", sva_text)
    if not m:
        return None
    bang, sig = m.group(1), m.group(2)
    new = "" if bang else "!"
    out = sva_text[: m.start()] + f"disable iff ({new}{sig})" + sva_text[m.end():]
    if out == sva_text:
        return None
    return Mutant("flip_reset_pol", sva_text, out)


ALL_OPERATORS = {
    "flip_relational": flip_relational,
    "flip_implication": flip_implication,
    "shift_delay": shift_delay,
    "flip_reset_pol": flip_reset_pol,
}


def mutate_all(sva_text: str) -> list[Mutant]:
    """Return all applicable mutants for a property body/text."""
    out: list[Mutant] = []
    for fn in ALL_OPERATORS.values():
        m = fn(sva_text)
        if m is not None:
            out.append(m)
    return out
