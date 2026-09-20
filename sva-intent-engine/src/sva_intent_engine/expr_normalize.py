"""Deterministic natural-language -> SV boolean expression normalization.

This is intentionally tiny and conservative. It maps a small set of well-known
phrase shapes to SystemVerilog boolean expressions, using ONLY signal names that
were grounded. Anything it cannot map returns ``None`` with a reason, so the
caller records an ambiguity and does NOT emit a property.

It never invents a signal name: a phrase like "grant is high" only normalizes if
'grant' resolved to an RTL symbol.

Supported shapes (case-insensitive):
    "<sig> is asserted" / "<sig> is high"        -> sig
    "<sig> is deasserted" / "<sig> is low"       -> !sig
    "<sig1> and <sig2> are high/asserted"        -> sig1 && sig2
    "<sig> must be high" / "<sig> is high"       -> sig
    "<sig> equals the maximum value"             -> <sig>_at_max sentinel (rejected)
    "no overflow" / "overflow is prevented"      -> handled by form, not here
"""

from __future__ import annotations

import re

# resolved-name set is passed in so we only accept grounded signals.

_ASSERT_RE = re.compile(
    r"^\s*(?P<sig>[A-Za-z_][A-Za-z0-9_]*)\s+(?:is|must be)\s+"
    r"(?:asserted|high|set|active|true)\s*$",
    re.IGNORECASE,
)
_DEASSERT_RE = re.compile(
    r"^\s*(?P<sig>[A-Za-z_][A-Za-z0-9_]*)\s+(?:is|must be)\s+"
    r"(?:deasserted|low|clear|cleared|inactive|false)\s*$",
    re.IGNORECASE,
)
_AND_RE = re.compile(
    r"^\s*(?P<a>[A-Za-z_][A-Za-z0-9_]*)\s+and\s+(?P<b>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?:are|is)\s+(?:high|asserted|set|active|true)\s*$",
    re.IGNORECASE,
)
_ZERO_RE = re.compile(
    r"^\s*(?:the\s+)?(?P<sig>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+value)?\s+(?:is|must be)\s+zero\s*$",
    re.IGNORECASE,
)
_BARE_RE = re.compile(r"^\s*(?P<sig>[A-Za-z_][A-Za-z0-9_]*)\s*$")


def normalize(phrase: str, resolved: set[str]) -> tuple[str | None, str | None]:
    """Return (expr, reason). expr is None if not normalizable.

    ``resolved`` is the set of signal names that grounded successfully.
    """
    if phrase is None:
        return None, "no phrase"
    phrase = phrase.strip().rstrip(".")
    # Strip trailing temporal qualifiers -- the timing is carried structurally
    # by the intent (min/max delay), not inside the boolean expression.
    phrase = re.sub(
        r"\s+(?:on\s+the\s+next\s+cycle|within\s+\d+(?:\s+to\s+\d+)?\s+cycles?"
        r"|after\s+\d+\s+cycles?)\s*$",
        "",
        phrase,
        flags=re.IGNORECASE,
    ).strip()

    m = _AND_RE.match(phrase)
    if m:
        a, b = m.group("a"), m.group("b")
        if a in resolved and b in resolved:
            return f"{a} && {b}", None
        missing = [s for s in (a, b) if s not in resolved]
        return None, f"ungrounded signal(s): {missing}"

    m = _ASSERT_RE.match(phrase)
    if m:
        sig = m.group("sig")
        return (sig, None) if sig in resolved else (None, f"ungrounded: {sig}")

    m = _DEASSERT_RE.match(phrase)
    if m:
        sig = m.group("sig")
        return (f"!{sig}", None) if sig in resolved else (None, f"ungrounded: {sig}")

    m = _ZERO_RE.match(phrase)
    if m:
        sig = m.group("sig")
        return (f"{sig} == 0", None) if sig in resolved else (None, f"ungrounded: {sig}")

    m = _BARE_RE.match(phrase)
    if m:
        sig = m.group("sig")
        return (sig, None) if sig in resolved else (None, f"ungrounded: {sig}")

    return None, f"unsupported phrase shape: {phrase!r}"
