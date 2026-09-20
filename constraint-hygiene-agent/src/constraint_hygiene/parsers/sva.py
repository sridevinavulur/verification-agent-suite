"""Deterministic, constrained parser for SVA assume/assert/cover directives.

Scope (intentionally narrow, but real):
    * ``property NAME; ... endproperty`` blocks referenced by a directive, OR
    * inline immediate/concurrent forms:
          assume property (@(posedge clk) EXPR);
          assert property (@(posedge clk) disable iff (!rst_n) EXPR);
          cover  property (@(posedge clk) EXPR);
          NAME_a: assume property (EXPR);
    * one-line ``assume(EXPR);`` immediate assumptions.

Everything the parser cannot understand is *skipped*, never guessed at. From
each parsed directive we deterministically extract:
    * referenced identifiers (signals),
    * constant equality facts  (sig == CONST),
    * boolean literal facts     (sig / !sig used as a top-level conjunct).

These facts are what the contradiction detector consumes. We do not attempt a
full SVA semantics; we extract exactly the structural facts the hygiene checks
need and label them as such.
"""

from __future__ import annotations

import re

from ..models import Property, SvaKind

# A SystemVerilog identifier (no hierarchical refs in this subset).
_IDENT = r"[A-Za-z_][A-Za-z0-9_$]*"

# SV keywords / operators we must NOT treat as signal identifiers.
_KEYWORDS = {
    "property",
    "endproperty",
    "assume",
    "assert",
    "cover",
    "posedge",
    "negedge",
    "disable",
    "iff",
    "if",
    "else",
    "and",
    "or",
    "not",
    "throughout",
    "within",
    "until",
    "s_until",
    "always",
    "eventually",
    "nexttime",
}
# Note: clock/reset signals (e.g. clk, rst_n) are intentionally NOT keywords;
# they are real signals. The clocking/`disable iff` prefix is stripped before
# fact/signal extraction so they do not leak into property bodies.

# Verilog numeric literal, e.g. 1'b0, 4'hF, 8'd12, 0, 42.
_NUMBER = r"(?:[0-9]+'[bBoOdDhH][0-9a-fA-FxXzZ_]+|[0-9]+)"

_DIRECTIVE_KIND = {
    "assume": SvaKind.ASSUME,
    "assert": SvaKind.ASSERT,
    "cover": SvaKind.COVER,
}


def _strip_comments(text: str) -> str:
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _balanced_parens(s: str, open_idx: int) -> int:
    """Return index just after the ')' matching the '(' at ``open_idx``."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _clock_and_body(inner: str) -> str:
    """Strip a leading clocking/disable-iff prefix, returning the property body.

    Handles ``@(posedge clk) disable iff (!rst_n) EXPR`` -> ``EXPR``.
    """
    body = inner.strip()
    # Remove clocking event @(...).
    m = re.match(r"@\s*\(", body)
    if m:
        end = _balanced_parens(body, m.end() - 1)
        if end != -1:
            body = body[end:].strip()
    # Remove `disable iff (...)`.
    m = re.match(r"disable\s+iff\s*\(", body)
    if m:
        end = _balanced_parens(body, m.end() - 1)
        if end != -1:
            body = body[end:].strip()
    return body.rstrip(";").strip()


def extract_signals(expr: str) -> list[str]:
    """Deterministically extract referenced identifiers, in first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    # Remove numeric literals first so bases like 'b0 do not leak identifiers.
    scrubbed = re.sub(_NUMBER, " ", expr)
    for m in re.finditer(_IDENT, scrubbed):
        tok = m.group(0)
        if tok in _KEYWORDS:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _split_top_level_conjuncts(expr: str) -> list[str]:
    """Split on top-level ``&&`` (and ``and``) not nested in parens."""
    parts: list[str] = []
    depth = 0
    buf = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif depth == 0 and expr[i : i + 2] == "&&":
            parts.append("".join(buf))
            buf = []
            i += 2
            continue
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def extract_facts(expr: str) -> tuple[dict[str, str], dict[str, bool]]:
    """Extract constant-equality facts and boolean-literal facts.

    Only *top-level conjuncts* produce facts, because that is the only case
    where the fact is unconditionally implied by the assumption.  This keeps the
    contradiction detector sound with respect to what it claims (it never claims
    more than the structure guarantees).
    """
    equalities: dict[str, str] = {}
    booleans: dict[str, bool] = {}

    for conj in _split_top_level_conjuncts(expr):
        c = conj.strip()
        # Drop one layer of wrapping parens: (foo) -> foo
        while c.startswith("(") and c.endswith(")") and _balanced_parens(c, 0) == len(c):
            c = c[1:-1].strip()

        # sig == CONST  /  sig === CONST
        m = re.fullmatch(rf"({_IDENT})\s*===?\s*({_NUMBER})", c)
        if m:
            equalities[m.group(1)] = _normalize_const(m.group(2))
            continue
        # sig != CONST -> not an equality fact we track (weaker), skip.

        # !sig  or  ~sig
        m = re.fullmatch(rf"[!~]\s*({_IDENT})", c)
        if m and m.group(1) not in _KEYWORDS:
            booleans[m.group(1)] = False
            continue

        # bare sig  (treated as sig == 1)
        m = re.fullmatch(_IDENT, c)
        if m and c not in _KEYWORDS:
            booleans[c] = True
            continue

    return equalities, booleans


def _normalize_const(tok: str) -> str:
    """Normalize a numeric literal to a canonical decimal string when possible."""
    t = tok.replace("_", "")
    m = re.fullmatch(r"(\d+)'([bBoOdDhH])([0-9a-fA-FxXzZ]+)", t)
    if not m:
        # plain decimal
        return str(int(t)) if t.isdigit() else t
    base_char = m.group(2).lower()
    digits = m.group(3)
    if any(x in digits.lower() for x in ("x", "z")):
        return f"{base_char}:{digits.lower()}"  # keep x/z distinct, uncomparable
    base = {"b": 2, "o": 8, "d": 10, "h": 16}[base_char]
    try:
        return str(int(digits, base))
    except ValueError:
        return tok


def parse_sva(text: str, filename: str = "<input>") -> list[Property]:
    """Parse all assume/assert/cover directives from SVA text."""
    text = _strip_comments(text)
    line_starts = _line_start_offsets(text)

    # First, collect named property blocks: property NAME; BODY endproperty
    named: dict[str, str] = {}
    for m in re.finditer(
        rf"\bproperty\s+({_IDENT})\s*(?:\([^)]*\))?\s*;(.*?)\bendproperty\b",
        text,
        flags=re.DOTALL,
    ):
        named[m.group(1)] = _clock_and_body(m.group(2))

    props: list[Property] = []
    seen_spans: list[tuple[int, int]] = []

    # Directives of the form: [LABEL:] KIND property (INNER);
    for m in re.finditer(
        rf"(?:({_IDENT})\s*:\s*)?\b(assume|assert|cover)\s+property\s*\(",
        text,
    ):
        kind = _DIRECTIVE_KIND[m.group(2)]
        label = m.group(1)
        open_paren = m.end() - 1
        close = _balanced_parens(text, open_paren)
        if close == -1:
            continue
        inner = text[open_paren + 1 : close - 1]
        seen_spans.append((m.start(), close))
        body = _clock_and_body(inner)
        # If body is just a property name, resolve it.
        stripped = body.strip()
        if stripped in named:
            body = named[stripped]
        name = label or f"{kind.value}_{_line_of(m.start(), line_starts)}"
        props.append(_make_property(name, kind, body, filename, _line_of(m.start(), line_starts)))

    # Immediate one-liners: [LABEL:] assume(EXPR);  (no `property` keyword)
    for m in re.finditer(rf"(?:({_IDENT})\s*:\s*)?\b(assume|assert)\s*\(", text):
        # Skip if this position was already consumed by a `property` directive.
        pos = m.start()
        if any(s <= pos < e for s, e in seen_spans):
            continue
        kind = _DIRECTIVE_KIND[m.group(2)]
        open_paren = m.end() - 1
        close = _balanced_parens(text, open_paren)
        if close == -1:
            continue
        inner = text[open_paren + 1 : close - 1]
        body = _clock_and_body(inner)
        name = m.group(1) or f"{kind.value}_{_line_of(pos, line_starts)}"
        props.append(_make_property(name, kind, body, filename, _line_of(pos, line_starts)))

    props.sort(key=lambda p: (p.line, p.name))
    return props


def _make_property(name: str, kind: SvaKind, body: str, filename: str, line: int) -> Property:
    equalities, booleans = extract_facts(body)
    return Property(
        name=name,
        kind=kind,
        expr=body.strip(),
        signals=extract_signals(body),
        equalities=equalities,
        boolean_facts=booleans,
        file=filename,
        line=line,
    )


def _line_start_offsets(text: str) -> list[int]:
    offs = [0]
    for i, c in enumerate(text):
        if c == "\n":
            offs.append(i + 1)
    return offs


def _line_of(pos: int, line_starts: list[int]) -> int:
    # binary-ish search; lists are tiny so linear is fine and deterministic.
    line = 1
    for i, start in enumerate(line_starts):
        if start > pos:
            break
        line = i + 1
    return line
