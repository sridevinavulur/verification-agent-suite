"""Safe SVA renderer for security property forms.

Deterministic template renderer for a fixed whitelist of security-oriented
property forms. There is NO free-form interpolation of untrusted text: every
expression that reaches a template is first passed through :func:`safe_expr`,
which admits only a small whitelist of SystemVerilog expression syntax.
Anything else raises :class:`RenderError` (rejected, never silently emitted).

Emitted properties are CANDIDATES. Compiling / rendering is not verifying.
"""

from __future__ import annotations

import re

# Whitelist for expression tokens: identifiers, sized/decimal literals, common
# comparison/boolean/bitwise operators, parens/brackets, concat, ranges,
# hierarchy member access. No statements, no system tasks, no macros.
_EXPR_TOKEN = re.compile(
    r"""
    (?:
        \s+                              # whitespace
      | [A-Za-z_][A-Za-z0-9_]*           # identifier
      | \d+'[bBhHdDoO][0-9a-fA-FxXzZ_]+  # sized literal e.g. 4'hF
      | \d+                              # decimal literal
      | ==|!=|<=|>=|<|>                  # comparisons
      | &&|\|\||!                        # boolean
      | [&|^~]                           # bitwise
      | [-+*]                            # arithmetic (no division)
      | \(|\)|\[|\]                      # grouping / index
      | \.                               # hierarchy member
      | \{|\}|,                          # concat
      | :                               # range within []
    )
    """,
    re.VERBOSE,
)

_BANNED = (";", "$", "//", "/*", "\n", "\\", "`", "assert", "assume", "cover", "property")


class RenderError(ValueError):
    """Raised when an expression or property cannot be rendered safely."""


def safe_expr(expr: str) -> str:
    """Validate ``expr`` against the whitelist and return it stripped.

    Raises RenderError if the expression contains anything outside the
    whitelist or any banned substring.
    """
    if not expr or not expr.strip():
        raise RenderError("empty expression")
    lowered = expr.lower()
    for bad in _BANNED:
        if bad in lowered:
            raise RenderError(f"banned token in expression: {bad!r}")
    # The whole string must be consumable by repeated whitelist tokens.
    pos = 0
    while pos < len(expr):
        m = _EXPR_TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            raise RenderError(f"unsafe token at offset {pos} in {expr!r}")
        pos = m.end()
    return expr.strip()


def clocking(clock: str, reset: str | None) -> str:
    """Render the ``@(posedge clk) disable iff (rst)`` clocking prefix."""
    safe_expr(clock)
    prefix = f"@(posedge {clock})"
    if reset:
        safe_expr(reset)
        prefix += f" disable iff ({reset})"
    return prefix


def render_never(name: str, clock: str, reset: str | None, cond: str) -> str:
    cond = safe_expr(cond)
    return f"assert property ({clocking(clock, reset)} !({cond}));  // {name}"


def render_always(name: str, clock: str, reset: str | None, cond: str) -> str:
    cond = safe_expr(cond)
    return f"assert property ({clocking(clock, reset)} ({cond}));  // {name}"


def render_implication(
    name: str, clock: str, reset: str | None, ante: str, cons: str, next_cycle: bool
) -> str:
    ante = safe_expr(ante)
    cons = safe_expr(cons)
    op = "|=>" if next_cycle else "|->"
    return f"assert property ({clocking(clock, reset)} ({ante}) {op} ({cons}));  // {name}"


def render_bounded_response(
    name: str,
    clock: str,
    reset: str | None,
    ante: str,
    cons: str,
    min_delay: int,
    max_delay: int,
) -> str:
    if min_delay < 0 or max_delay < 0:
        raise RenderError("delays must be non-negative")
    if max_delay < min_delay:
        raise RenderError("max_delay must be >= min_delay")
    ante = safe_expr(ante)
    cons = safe_expr(cons)
    return (
        f"assert property ({clocking(clock, reset)} ({ante}) |-> "
        f"##[{min_delay}:{max_delay}] ({cons}));  // {name}"
    )


def render_lockstep_equal(
    name: str, clock: str, reset: str | None, a: str, b: str
) -> str:
    a = safe_expr(a)
    b = safe_expr(b)
    return f"assert property ({clocking(clock, reset)} ({a}) == ({b}));  // {name}"


def render_reachable(name: str, clock: str, reset: str | None, cond: str) -> str:
    cond = safe_expr(cond)
    return f"cover property ({clocking(clock, reset)} ({cond}));  // {name}"
