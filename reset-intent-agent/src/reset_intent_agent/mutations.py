"""Reset-defect mutation operators.

Applies textual mutations to RTL that model classic reset bugs, so a reviewer
(or a downstream mutation-scoring tool) can check whether the generated
candidate SVA / recommendations would surface the defect.

Operators (real source transforms, stable IDs):
  * ``reset_polarity_flip``  — flip the guard between active-high/active-low
  * ``reset_value_change``   — change a reset value constant (0 <-> 1)
  * ``reset_removal``        — drop the reset branch entirely

Each mutant records the exact source change. This is a defect *injector*; it
does not, on its own, classify detection (that requires an execution adapter,
which is out of scope for v0.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Mutant:
    mutant_id: str
    operator: str
    description: str
    original_line: str
    mutated_line: str
    mutated_source: str


_GUARD_NEG_RE = re.compile(r"if\s*\(\s*!\s*([A-Za-z_]\w*)\s*\)")
_GUARD_POS_RE = re.compile(r"if\s*\(\s*([A-Za-z_]\w*)\s*\)")
_RESET_ASSIGN_RE = re.compile(
    r"([A-Za-z_]\w*)\s*<=\s*(\d+'[bBhHdD][0-9a-fA-F]+|\d+|'?[01])\s*;"
)
_RESET_HINT = ("rst", "reset")


def _is_reset_ident(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _RESET_HINT)


def mutate_polarity_flip(source: str) -> list[Mutant]:
    mutants: list[Mutant] = []
    idx = 0
    for m in _GUARD_NEG_RE.finditer(source):
        sig = m.group(1)
        if not _is_reset_ident(sig):
            continue
        idx += 1
        orig = m.group(0)
        mutated = f"if ({sig})"
        mutants.append(
            _make(source, m, "reset_polarity_flip", idx, orig, mutated,
                  f"flip active-low reset guard on '{sig}' to active-high")
        )
    for m in _GUARD_POS_RE.finditer(source):
        sig = m.group(1)
        if not _is_reset_ident(sig):
            continue
        idx += 1
        orig = m.group(0)
        mutated = f"if (!{sig})"
        mutants.append(
            _make(source, m, "reset_polarity_flip", idx, orig, mutated,
                  f"flip active-high reset guard on '{sig}' to active-low")
        )
    return mutants


def mutate_reset_value(source: str) -> list[Mutant]:
    """Flip a reset value constant 0<->1 for a register in a reset branch."""
    mutants: list[Mutant] = []
    idx = 0
    # only mutate assignments that are inside a reset context (guard nearby above)
    for m in _RESET_ASSIGN_RE.finditer(source):
        if not _preceded_by_reset_guard(source, m.start()):
            continue
        val = m.group(2)
        flipped = _flip_const(val)
        if flipped is None:
            continue
        idx += 1
        orig = m.group(0)
        mutated = orig.replace(val, flipped, 1)
        mutants.append(
            _make(source, m, "reset_value_change", idx, orig, mutated,
                  f"change reset value of '{m.group(1)}' {val} -> {flipped}")
        )
    return mutants


def mutate_reset_removal(source: str) -> list[Mutant]:
    """Remove an active-low/high reset guard, keeping only the else branch body."""
    mutants: list[Mutant] = []
    idx = 0
    for m in _GUARD_NEG_RE.finditer(source):
        if not _is_reset_ident(m.group(1)):
            continue
        idx += 1
        orig = m.group(0)
        mutated = "if (1'b0)"  # guard never fires -> reset branch dead
        mutants.append(
            _make(source, m, "reset_removal", idx, orig, mutated,
                  f"disable reset guard on '{m.group(1)}' (reset branch dead)")
        )
    return mutants


ALL_OPERATORS = {
    "reset_polarity_flip": mutate_polarity_flip,
    "reset_value_change": mutate_reset_value,
    "reset_removal": mutate_reset_removal,
}


def generate_mutants(source: str, operators: list[str] | None = None) -> list[Mutant]:
    ops = operators or list(ALL_OPERATORS)
    out: list[Mutant] = []
    for name in ops:
        fn = ALL_OPERATORS.get(name)
        if fn:
            out.extend(fn(source))
    # stabilise IDs across the whole set
    for i, mut in enumerate(out, 1):
        mut.mutant_id = f"M{i:03d}"
    return out


# --------------------------------------------------------------------------- #
def _make(source, match, operator, idx, orig, mutated, desc) -> Mutant:
    mutated_source = source[: match.start()] + mutated + source[match.end():]
    return Mutant(
        mutant_id=f"{operator}_{idx}",
        operator=operator,
        description=desc,
        original_line=orig,
        mutated_line=mutated,
        mutated_source=mutated_source,
    )


def _flip_const(val: str) -> str | None:
    v = val.strip().strip("'")
    if v in ("0", "1"):
        return "1" if v == "0" else "0"
    m = re.match(r"(\d+)'([bBhHdD])([0-9a-fA-F]+)", val)
    if m and m.group(3) in ("0", "1"):
        new = "1" if m.group(3) == "0" else "0"
        return f"{m.group(1)}'{m.group(2)}{new}"
    return None


def _preceded_by_reset_guard(source: str, pos: int) -> bool:
    window = source[max(0, pos - 200):pos]
    for m in _GUARD_NEG_RE.finditer(window):
        if _is_reset_ident(m.group(1)):
            return True
    for m in _GUARD_POS_RE.finditer(window):
        if _is_reset_ident(m.group(1)):
            return True
    return False
