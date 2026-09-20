"""Deterministic identifier extraction from RHS expression *text*.

The manifest keeps expression right-hand sides as verbatim source strings (the
subset parser does not build an AST).  For structural data-flow we only need
the set of identifiers referenced, and -- for bit-slice awareness -- whether a
reference is bit-sliced.  We extract identifiers with a small tokenizer that:

* ignores Verilog numeric literals such as ``1'b0``, ``8'hFF``, ``42``;
* ignores Verilog keywords/operators;
* treats ``foo[..]`` as a reference to ``foo``.

This is intentionally simple and conservative.  It is a heuristic, but a
*deterministic* one: same input text always yields the same identifier set.
"""

from __future__ import annotations

import re

# A Verilog based literal, e.g.  8'hFF   4'b1010   1'bx   'd10
_BASED_LITERAL = re.compile(r"\b\d*\s*'\s*[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_]+")
# A plain decimal number.
_DECIMAL = re.compile(r"\b\d[\d_]*\b")
# An identifier, possibly hierarchical (a.b.c). We capture the whole dotted
# name so the leading segment can be taken as the local reference.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*")

_KEYWORDS = frozenset(
    {
        "posedge",
        "negedge",
        "or",
        "and",
        "if",
        "else",
        "begin",
        "end",
        "case",
        "endcase",
        "default",
        "signed",
        "unsigned",
    }
)


def referenced_identifiers(expr: str) -> set[str]:
    """Return the set of signal identifiers referenced in ``expr``.

    Hierarchical names ``a.b`` contribute their *leading* segment ``a`` (the
    local instance/net), which is what matters for in-module data flow.
    """

    # Strip based literals first so their base char (b/h/...) isn't an ident.
    cleaned = _BASED_LITERAL.sub(" ", expr)
    cleaned = _DECIMAL.sub(" ", cleaned)
    idents: set[str] = set()
    for m in _IDENT.finditer(cleaned):
        name = m.group(0)
        if name in _KEYWORDS:
            continue
        head = name.split(".")[0]
        idents.add(head)
    return idents


def is_bit_sliced(expr: str, signal: str) -> bool:
    """True if ``signal`` appears with a ``[..]`` selection in ``expr``."""

    pat = re.compile(re.escape(signal) + r"\s*\[")
    return bool(pat.search(expr))


def base_signal(lhs: str) -> str:
    """Return the base signal name from an LHS that may be indexed/sliced."""

    m = _IDENT.match(lhs.strip())
    return m.group(0) if m else lhs.strip()
