"""A small, deterministic tokenizer for the constrained Verilog subset.

Handles line/block comments, string literals, sized/based numbers, identifiers,
and the punctuation the subset parser needs. It tracks 1-based line and column
for every token so downstream extraction can attach accurate source locations.

This is intentionally NOT a full SystemVerilog lexer. It is good enough for the
declared subset and hands anything it does not understand to the parser as a
generic token, where it becomes visible (never silently dropped).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TokKind(StrEnum):
    IDENT = "ident"
    NUMBER = "number"
    STRING = "string"
    PUNCT = "punct"
    EOF = "eof"


# Multi-character operators, longest first so the scanner is greedy.
_MULTI_PUNCT = (
    "<=",
    ">=",
    "==",
    "!=",
    "&&",
    "||",
    "<<",
    ">>",
    "**",
    "->",
    "=>",
    "+:",
    "-:",
    "::",
)

_SINGLE_PUNCT = set("()[]{}#@,;:.=+-*/%<>!&|^~?'`")


@dataclass(frozen=True)
class Token:
    kind: TokKind
    text: str
    line: int
    col: int
    end_line: int
    end_col: int


class LexError(ValueError):
    """Raised on an unterminated block comment or string literal."""


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_" or ch == "$"


def _is_ident_part(ch: str) -> bool:
    return ch.isalnum() or ch == "_" or ch == "$"


def tokenize(text: str, *, filename: str = "<mem>") -> list[Token]:
    """Tokenize ``text`` into a list ending with a single EOF token."""
    tokens: list[Token] = []
    i = 0
    n = len(text)
    line = 1
    col = 1

    def advance(count: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if i < n and text[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = text[i]

        # Whitespace.
        if ch in " \t\r\n":
            advance()
            continue

        # Line comment.
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                advance()
            continue

        # Block comment.
        if text.startswith("/*", i):
            start_line, start_col = line, col
            advance(2)
            while i < n and not text.startswith("*/", i):
                advance()
            if i >= n:
                raise LexError(
                    f"{filename}:{start_line}:{start_col}: unterminated block comment"
                )
            advance(2)
            continue

        start_line, start_col = line, col

        # String literal.
        if ch == '"':
            advance()
            buf = ['"']
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i])
                    advance()
                buf.append(text[i])
                advance()
            if i >= n:
                raise LexError(
                    f"{filename}:{start_line}:{start_col}: unterminated string"
                )
            buf.append('"')
            advance()  # closing quote
            tokens.append(
                Token(
                    TokKind.STRING,
                    "".join(buf),
                    start_line,
                    start_col,
                    line,
                    col - 1,
                )
            )
            continue

        # Number: decimal digits, or a sized/based literal like 8'hFF, 'b0, 4'd2.
        if ch.isdigit() or (ch == "'" and i + 1 < n and text[i + 1] in "bBoOdDhHsS"):
            buf = []
            # leading size digits (optional if starting with ')
            while i < n and text[i].isdigit():
                buf.append(text[i])
                advance()
            if i < n and text[i] == "'":
                buf.append(text[i])
                advance()
                # base char
                if i < n and text[i] in "sS":
                    buf.append(text[i])
                    advance()
                if i < n and text[i] in "bBoOdDhH":
                    buf.append(text[i])
                    advance()
                # value chars (hex + underscores + x/z)
                while i < n and (text[i].isalnum() or text[i] in "_xXzZ?"):
                    buf.append(text[i])
                    advance()
            tokens.append(
                Token(
                    TokKind.NUMBER,
                    "".join(buf),
                    start_line,
                    start_col,
                    line,
                    col - 1,
                )
            )
            continue

        # Identifier / keyword (keywords are just identifiers to the lexer).
        if _is_ident_start(ch):
            buf = []
            while i < n and _is_ident_part(text[i]):
                buf.append(text[i])
                advance()
            tokens.append(
                Token(
                    TokKind.IDENT,
                    "".join(buf),
                    start_line,
                    start_col,
                    line,
                    col - 1,
                )
            )
            continue

        # Multi-char punctuation.
        matched = None
        for op in _MULTI_PUNCT:
            if text.startswith(op, i):
                matched = op
                break
        if matched is not None:
            advance(len(matched))
            tokens.append(
                Token(TokKind.PUNCT, matched, start_line, start_col, line, col - 1)
            )
            continue

        # Single-char punctuation.
        if ch in _SINGLE_PUNCT:
            advance()
            tokens.append(
                Token(TokKind.PUNCT, ch, start_line, start_col, line, col - 1)
            )
            continue

        # Anything else: emit as a single-char punct so the parser can flag it.
        advance()
        tokens.append(Token(TokKind.PUNCT, ch, start_line, start_col, line, col - 1))

    tokens.append(Token(TokKind.EOF, "", line, col, line, col))
    return tokens
