"""Minimal SVA property extraction for the constrained subset.

We parse just enough to obtain, for each property/assert, its name and the set
of design identifiers it references. This is what the mock executor uses to
decide whether a property could observe a given mutation. It is intentionally
lexical, not a semantic SVA elaborator.
"""

from __future__ import annotations

import re

from .lexer import code_tokens, tokenize
from .models import PropertyRef

# SVA / Verilog keywords and macros that are NOT design signals.
_SVA_KEYWORDS = {
    "property", "endproperty", "assert", "assume", "cover", "sequence",
    "endsequence", "disable", "iff", "posedge", "negedge", "clocking",
    "endclocking", "default", "always", "always_ff", "always_comb", "module",
    "endmodule", "begin", "end", "if", "else", "and", "or", "not", "throughout",
    "within", "intersect", "first_match", "s_until", "until", "s_eventually",
    "eventually", "nexttime", "s_nexttime", "wire", "reg", "logic", "input",
    "output", "bind", "label", "b", "d", "h", "o",
}

# ``property NAME`` or ``NAME : assert property`` patterns.
_PROPERTY_DEF_RE = re.compile(r"\bproperty\s+([A-Za-z_]\w*)")
_LABEL_ASSERT_RE = re.compile(
    r"([A-Za-z_]\w*)\s*:\s*(?:assert|assume|cover)\b"
)


def _referenced_signals(body: str) -> list[str]:
    toks = code_tokens(tokenize(body))
    sigs: list[str] = []
    seen: set[str] = set()
    for t in toks:
        if t.kind != "ident":
            continue
        if t.value in _SVA_KEYWORDS:
            continue
        # skip an identifier immediately followed by '(' that is a property/seq
        # call rather than a signal? keep it simple: treat as reference anyway
        # only if not the property's own name handled by caller.
        if t.value not in seen:
            seen.add(t.value)
            sigs.append(t.value)
    return sigs


def _strip_comments(text: str) -> str:
    """Remove // line and /* */ block comments (so they never look like code)."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def parse_properties(text: str) -> list[PropertyRef]:
    """Extract named properties/assertions and their referenced signals.

    Two forms are recognized:
      1. ``property <name> ... endproperty``
      2. ``<label> : assert property ( ... );``
    """
    text = _strip_comments(text)
    props: list[PropertyRef] = []
    seen_names: set[str] = set()

    # Form 1: property ... endproperty blocks.
    for m in re.finditer(
        r"\bproperty\s+([A-Za-z_]\w*)(.*?)\bendproperty",
        text,
        re.DOTALL,
    ):
        name = m.group(1)
        body = m.group(2)
        signals = [s for s in _referenced_signals(body) if s != name]
        props.append(
            PropertyRef(name=name, text=m.group(0), referenced_signals=signals)
        )
        seen_names.add(name)

    # Form 2: labeled inline asserts (label : assert property ( ... );).
    for m in re.finditer(
        r"([A-Za-z_]\w*)\s*:\s*(assert|assume|cover)\s+property\s*\((.*?)\)\s*;",
        text,
        re.DOTALL,
    ):
        name = m.group(1)
        if name in seen_names:
            continue
        body = m.group(3)
        # If the body is just an instance of an already-parsed named property
        # (``a_x : assert property (p_x);``), skip it: p_x already carries the
        # real signal references. This avoids a duplicate entry that would only
        # reference the property name.
        if body.strip() in seen_names:
            continue
        signals = [s for s in _referenced_signals(body) if s != name]
        props.append(
            PropertyRef(name=name, text=m.group(0), referenced_signals=signals)
        )
        seen_names.add(name)

    return props
