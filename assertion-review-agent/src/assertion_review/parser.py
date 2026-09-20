"""Constrained SVA parser.

This is a *deliberately constrained* parser for a subset of SystemVerilog
Assertions. It is NOT a full SystemVerilog front-end. It recognises the common
concurrent-assertion shapes used in reviews:

    assert property (@(posedge clk) disable iff (rst) a |-> b);
    assert property (@(posedge clk) a |=> b ##[1:3] c);
    LABEL: assert property (@(posedge clk) ... );
    property P; @(posedge clk) disable iff (!rst_n) a |-> b; endproperty
    assume property (@(posedge clk) x == 0);
    cover  property (@(posedge clk) a ##1 b);

Anything it cannot classify is still captured as a :class:`ParsedProperty`
with a raw body so downstream checks can operate on the text. Fields that
cannot be determined are left ``None`` (never guessed).

Limitations are documented in the README under "Parser limitations".
"""

from __future__ import annotations

import re

from .models import (
    ImplicationStyle,
    ParsedProperty,
    PropertyKind,
    SourceLocation,
)

# ---------------------------------------------------------------------------
# Comment / string stripping while preserving line numbers.
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments, replacing them with spaces so that
    character offsets and (crucially) newlines are preserved."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            if j == -1:
                j = n
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            if j == -1:
                j = n
            else:
                j += 2
            # preserve newlines inside the block comment
            out.append("".join("\n" if c == "\n" else " " for c in text[i:j]))
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")

# SystemVerilog / SVA keywords we never treat as signal identifiers.
_KEYWORDS = {
    "assert",
    "assume",
    "cover",
    "property",
    "endproperty",
    "sequence",
    "endsequence",
    "disable",
    "iff",
    "posedge",
    "negedge",
    "edge",
    "and",
    "or",
    "not",
    "if",
    "else",
    "throughout",
    "within",
    "intersect",
    "first_match",
    "s_eventually",
    "s_until",
    "s_until_with",
    "eventually",
    "until",
    "until_with",
    "nexttime",
    "s_nexttime",
    "always",
    "label",
    "begin",
    "end",
    "module",
    "endmodule",
}


# Sized/based literals: 4'hA, 1'b0, 8'd255, 'b1, 12'sh0FF ...
_SIZED_LITERAL_RE = re.compile(r"\d*'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_]+")
# Bare decimal numbers.
_NUMBER_RE = re.compile(r"\b\d+\b")


def _extract_identifiers(expr: str) -> list[str]:
    # Strip literals first so their base part (e.g. 'b0' from 1'b0) is not
    # mistaken for a signal identifier.
    cleaned = _SIZED_LITERAL_RE.sub(" ", expr)
    cleaned = _NUMBER_RE.sub(" ", cleaned)
    ids: list[str] = []
    seen: set[str] = set()
    for m in _IDENT_RE.finditer(cleaned):
        tok = m.group(0)
        if tok in _KEYWORDS:
            continue
        if tok not in seen:
            seen.add(tok)
            ids.append(tok)
    return ids


def _find_matching_paren(text: str, open_idx: int) -> int:
    """Given index of a '(', return index of the matching ')' or -1."""
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _line_col(text: str, idx: int) -> tuple[int, int]:
    line = text.count("\n", 0, idx) + 1
    last_nl = text.rfind("\n", 0, idx)
    col = idx - last_nl if last_nl != -1 else idx + 1
    return line, col


# clock:  @(posedge clk)  or @(negedge clk_n)
_CLOCK_RE = re.compile(r"@\s*\(\s*(?:posedge|negedge|edge)?\s*([A-Za-z_][A-Za-z0-9_$]*)")
# disable iff (expr)
_DISABLE_RE = re.compile(r"disable\s+iff\s*\(")


def _split_implication(body: str) -> tuple[str | None, str | None, ImplicationStyle]:
    """Split a property body into antecedent / consequent at the top-level
    implication operator, ignoring operators nested in parentheses."""
    depth = 0
    i = 0
    n = len(body)
    while i < n - 1:
        c = body[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            if body[i : i + 3] == "|->":
                return body[:i].strip(), body[i + 3 :].strip(), ImplicationStyle.OVERLAPPING
            if body[i : i + 3] == "|=>":
                return body[:i].strip(), body[i + 3 :].strip(), ImplicationStyle.NON_OVERLAPPING
        i += 1
    return None, body.strip() or None, ImplicationStyle.NONE


_KIND_MAP = {
    "assert": PropertyKind.ASSERT,
    "assume": PropertyKind.ASSUME,
    "cover": PropertyKind.COVER,
}


def _parse_inline_assertions(clean: str, file: str) -> list[ParsedProperty]:
    """Parse `<label>: (assert|assume|cover) property ( ... );` forms."""
    props: list[ParsedProperty] = []
    pat = re.compile(
        r"(?:([A-Za-z_][A-Za-z0-9_$]*)\s*:\s*)?\b(assert|assume|cover)\s+property\s*\("
    )
    for m in pat.finditer(clean):
        open_paren = m.end() - 1
        close_paren = _find_matching_paren(clean, open_paren)
        if close_paren == -1:
            continue
        inner = clean[open_paren + 1 : close_paren]
        label = m.group(1)
        kind = _KIND_MAP[m.group(2)]
        line, col = _line_col(clean, m.start())
        props.append(_build_property(label, kind, inner, file, line, col))
    return props


_PROP_BLOCK_RE = re.compile(
    r"\bproperty\s+([A-Za-z_][A-Za-z0-9_$]*)\s*;(.*?)\bendproperty", re.DOTALL
)
_USE_RE = re.compile(
    r"(?:([A-Za-z_][A-Za-z0-9_$]*)\s*:\s*)?\b(assert|assume|cover)\s+property\s*\(\s*"
    r"([A-Za-z_][A-Za-z0-9_$]*)\s*\)"
)


def _parse_property_blocks(clean: str, file: str) -> list[ParsedProperty]:
    """Parse named `property NAME; ... endproperty` blocks, attaching the
    assert/assume/cover kind if a matching `assert property(NAME)` is present."""
    # Map property-name -> kind based on usage sites.
    usage_kind: dict[str, PropertyKind] = {}
    for u in _USE_RE.finditer(clean):
        usage_kind[u.group(3)] = _KIND_MAP[u.group(2)]

    props: list[ParsedProperty] = []
    for m in _PROP_BLOCK_RE.finditer(clean):
        name = m.group(1)
        inner = m.group(2)
        line, col = _line_col(clean, m.start())
        kind = usage_kind.get(name, PropertyKind.ASSERT)
        props.append(_build_property(name, kind, inner, file, line, col))
    return props


def _build_property(
    label: str | None,
    kind: PropertyKind,
    inner: str,
    file: str,
    line: int,
    col: int,
) -> ParsedProperty:
    raw = inner.strip()

    clock = None
    cm = _CLOCK_RE.search(inner)
    if cm:
        clock = cm.group(1)

    disable_iff = None
    dm = _DISABLE_RE.search(inner)
    if dm:
        open_idx = dm.end() - 1
        close_idx = _find_matching_paren(inner, open_idx)
        if close_idx != -1:
            disable_iff = inner[open_idx + 1 : close_idx].strip()

    # Body = everything after clock and disable-iff clauses.
    body = inner
    if cm:
        # remove the clocking event @(...)
        ce = _find_matching_paren(inner, inner.index("(", cm.start()))
        if ce != -1:
            body = inner[:cm.start()] + inner[ce + 1 :]
    if dm:
        dstart = body.find("disable")
        if dstart != -1:
            op = body.find("(", dstart)
            cp = _find_matching_paren(body, op)
            if cp != -1:
                body = body[:dstart] + body[cp + 1 :]
    body = body.strip().rstrip(";").strip()

    ant, cons, impl = _split_implication(body)

    ids = _extract_identifiers(body)
    if disable_iff:
        ids += [i for i in _extract_identifiers(disable_iff) if i not in ids]

    snippet = " ".join(inner.split())
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."

    return ParsedProperty(
        name=label,
        kind=kind,
        clock=clock,
        disable_iff=disable_iff,
        antecedent=ant,
        consequent=cons,
        implication=impl,
        body=body,
        location=SourceLocation(file=file, line=line, column=col, snippet=snippet),
        identifiers=ids,
        raw=raw,
    )


def parse_sva(text: str, file: str = "<memory>") -> list[ParsedProperty]:
    """Parse an SVA source string into a list of :class:`ParsedProperty`.

    Named ``property ... endproperty`` blocks are preferred; inline
    ``assert property(...)`` statements that merely *reference* a named
    property are not double-counted.
    """
    clean = _strip_comments(text)

    props: list[ParsedProperty] = []
    props.extend(_parse_property_blocks(clean, file))

    referenced = set(_USE_RE.findall(clean))
    referenced_names = {r[2] for r in referenced}

    # Inline assertions, but skip those that just reference a named property.
    for p in _parse_inline_assertions(clean, file):
        inner = p.raw
        # If the inner body is exactly a bare property name reference, skip it.
        stripped = inner.strip().rstrip(";").strip()
        if stripped in referenced_names:
            continue
        props.append(p)

    props.sort(key=lambda p: (p.location.line, p.location.column))
    return props
