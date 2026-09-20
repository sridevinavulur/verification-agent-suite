"""A tiny, deterministic lexer for a constrained synthesizable Verilog subset.

This is *not* a full Verilog parser. It tokenizes just enough structure to let
the mutation operators locate relational operators, boolean conditions, reset
edges, counter updates, assignments, and gating expressions with correct
1-based line/column positions. Comments and strings are tokenized so that
operators never mutate inside them.

Supported token kinds: whitespace, line/block comments, numbers (incl. sized
literals like ``4'b0010``), identifiers/keywords, operators, and punctuation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Order matters: longer operators must be tried before their prefixes.
_MULTI_CHAR_OPS = [
    "<<<", ">>>", "===", "!==",
    "<=", ">=", "==", "!=", "&&", "||", "<<", ">>", "->", "=>",
    "+:", "-:", "~&", "~|", "~^", "^~",
]

_SINGLE_CHAR_OPS = set("+-*/%<>=!&|^~?:.,;()[]{}@#")

_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
# Compiler directives / macro usage: `define, `timescale, `MACRO ...
_DIRECTIVE_RE = re.compile(r"`[A-Za-z_][A-Za-z0-9_$]*")
# Sized/based numbers (4'b1010, 8'hFF, 'd3) and plain decimals/reals.
_NUMBER_RE = re.compile(
    r"(\d+)?'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_]+"  # based literal
    r"|\d+\.\d+"  # real
    r"|\d[\d_]*"  # decimal
)
_WS_RE = re.compile(r"[ \t\r\n]+")
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r'"(\\.|[^"\\])*"')


@dataclass
class Token:
    kind: str  # 'ws' | 'comment' | 'string' | 'number' | 'ident' | 'op'
    value: str
    start: int  # absolute char offset into source
    end: int  # absolute char offset (exclusive)
    line: int  # 1-based
    col: int  # 1-based column of first char

    @property
    def is_code(self) -> bool:
        return self.kind not in ("ws", "comment", "string")


def _line_col_map(source: str) -> list[int]:
    """Return list where index i is the char offset at which line (i+1) starts."""
    starts = [0]
    for i, ch in enumerate(source):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _pos_to_line_col(line_starts: list[int], offset: int) -> tuple[int, int]:
    # Binary search for the line containing offset.
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    line = lo + 1
    col = offset - line_starts[lo] + 1
    return line, col


def tokenize(source: str) -> list[Token]:
    """Tokenize ``source`` into a flat list of :class:`Token`.

    Raises ``ValueError`` on an unrecognized character so that malformed input
    is surfaced rather than silently dropped.
    """
    tokens: list[Token] = []
    line_starts = _line_col_map(source)
    i = 0
    n = len(source)
    while i < n:
        line, col = _pos_to_line_col(line_starts, i)

        m = _WS_RE.match(source, i)
        if m:
            tokens.append(Token("ws", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _LINE_COMMENT_RE.match(source, i)
        if m:
            tokens.append(Token("comment", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _BLOCK_COMMENT_RE.match(source, i)
        if m:
            tokens.append(Token("comment", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _STRING_RE.match(source, i)
        if m:
            tokens.append(Token("string", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _DIRECTIVE_RE.match(source, i)
        if m:
            # Treat compiler directives / macro references as opaque idents so
            # they are never mutated but also never crash the lexer.
            tokens.append(Token("ident", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _NUMBER_RE.match(source, i)
        if m:
            tokens.append(Token("number", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        m = _IDENT_RE.match(source, i)
        if m:
            tokens.append(Token("ident", m.group(), i, m.end(), line, col))
            i = m.end()
            continue

        matched_op = None
        for op in _MULTI_CHAR_OPS:
            if source.startswith(op, i):
                matched_op = op
                break
        if matched_op is None and source[i] in _SINGLE_CHAR_OPS:
            matched_op = source[i]
        if matched_op is not None:
            tokens.append(
                Token("op", matched_op, i, i + len(matched_op), line, col)
            )
            i += len(matched_op)
            continue

        raise ValueError(
            f"Unrecognized character {source[i]!r} at line {line}, col {col}"
        )

    return tokens


def code_tokens(tokens: list[Token]) -> list[Token]:
    """Return only the semantically significant tokens (drop ws/comment/string)."""
    return [t for t in tokens if t.is_code]
