"""Safe SVA fragment renderer.

Same philosophy as sva-intent-engine's renderer: NO free-form interpolation of
untrusted text. Every expression that reaches a property template is first passed
through :func:`safe_expr`, which admits only a small whitelist of SystemVerilog
expression syntax. Anything else raises :class:`RenderError`.

This module renders individual property *bodies* and wraps them into named
``assert/assume/cover property`` blocks in the same compiled-offline style as
``sva-intent-engine`` (e.g. ``p_<name>: assert property (@(posedge clk) ...);``).
Nothing here executes a tool; output is a candidate only.
"""

from __future__ import annotations

import re

from .models import PropertyKind, ResetPolarity

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

_BANNED = (";", "$display", "//", "/*", "\n", "\\", "`")


class RenderError(ValueError):
    """Raised when an expression or property cannot be rendered safely."""


def safe_expr(expr: str) -> str:
    """Validate + normalize a boolean/arithmetic SV expression.

    Rejects statement terminators, comments, line-continuation, macros, and any
    character outside the whitelist. ``$onehot``/``$stable``/``$past`` etc. are
    added by templates, never taken from user text, so ``$`` alone is allowed
    only inside this module's own template strings (not through safe_expr).
    """
    if expr is None or expr.strip() == "":
        raise RenderError("empty expression")
    low = expr.lower()
    for bad in _BANNED:
        if bad in low:
            raise RenderError(f"unsafe token in expression: {bad!r}")
    if "$" in expr:
        raise RenderError("system tasks are not allowed in user expressions")

    pos, n = 0, len(expr)
    while pos < n:
        m = _EXPR_TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            raise RenderError(
                f"unsupported expression syntax near: {expr[pos : pos + 12]!r}"
            )
        pos = m.end()
    return expr.strip()


def clocking(clock: str | None) -> str:
    if not clock:
        raise RenderError("absent clock: every temporal property needs a clock")
    return f"@(posedge {safe_expr(clock)})"


def disable_iff(reset: str | None, polarity: ResetPolarity) -> str:
    """Build a ``disable iff`` clause. Never guesses polarity.

    Returns "" (no disable clause) when reset is absent or polarity is unknown.
    Callers that require an explicit reset must check separately.
    """
    if not reset:
        return ""
    rst = safe_expr(reset)
    if polarity == ResetPolarity.ACTIVE_LOW:
        return f" disable iff (!{rst})"
    if polarity == ResetPolarity.ACTIVE_HIGH:
        return f" disable iff ({rst})"
    return ""  # unknown polarity -> do not guess


def _directive(kind: PropertyKind) -> str:
    return {
        PropertyKind.ASSERT: "assert property",
        PropertyKind.ASSUME: "assume property",
        PropertyKind.COVER: "cover property",
    }[kind]


def wrap(name: str, kind: PropertyKind, body: str) -> str:
    """Wrap a rendered body into a named property block (sva-intent style)."""
    return f"{name}: {_directive(kind)} (\n  {body}\n);"


# --------------------------------------------------------------------------- #
# Body builders (each returns the inner expression AFTER clocking/disable)
# --------------------------------------------------------------------------- #


def body_invariant(clock: str, reset: str | None, pol: ResetPolarity, cond: str) -> str:
    return f"{clocking(clock)}{disable_iff(reset, pol)} {safe_expr(cond)}"


def body_implication(
    clock: str,
    reset: str | None,
    pol: ResetPolarity,
    ante: str,
    cons: str,
    *,
    overlapping: bool = True,
) -> str:
    op = "|->" if overlapping else "|=>"
    return (
        f"{clocking(clock)}{disable_iff(reset, pol)} "
        f"({safe_expr(ante)}) {op} ({safe_expr(cons)})"
    )


def body_bounded_response(
    clock: str,
    reset: str | None,
    pol: ResetPolarity,
    ante: str,
    cons: str,
    lo: int,
    hi: int,
    *,
    overlapping: bool = True,
) -> str:
    if lo < 0 or hi < 0:
        raise RenderError("invalid timing range: negative delay")
    if hi < lo:
        raise RenderError(f"invalid timing range: max {hi} < min {lo}")
    op = "|->" if overlapping else "|=>"
    rng = f"##[{lo}:{hi}]" if lo != hi else f"##{lo}"
    return (
        f"{clocking(clock)}{disable_iff(reset, pol)} "
        f"({safe_expr(ante)}) {op} {rng} ({safe_expr(cons)})"
    )


def body_stable_while(
    clock: str, reset: str | None, pol: ResetPolarity, stall: str, data: str
) -> str:
    return (
        f"{clocking(clock)}{disable_iff(reset, pol)} "
        f"({safe_expr(stall)}) |=> $stable({safe_expr(data)})"
    )


def body_onehot0(clock: str, reset: str | None, pol: ResetPolarity, vec: str) -> str:
    return f"{clocking(clock)}{disable_iff(reset, pol)} $onehot0({safe_expr(vec)})"


def body_no_change_beyond(
    clock: str, reset: str | None, pol: ResetPolarity, guard: str, cons: str
) -> str:
    """Guard |=> consequent (used for no-overflow / no-underflow)."""
    return (
        f"{clocking(clock)}{disable_iff(reset, pol)} "
        f"({safe_expr(guard)}) |=> ({safe_expr(cons)})"
    )


def body_reset_state(clock: str, reset: str, pol: ResetPolarity, cons: str) -> str:
    """Property ABOUT reset: while reset asserted, expect state. No disable-iff."""
    if pol == ResetPolarity.UNKNOWN:
        raise RenderError("reset_state requires known reset polarity (do not guess)")
    active = safe_expr(reset) if pol == ResetPolarity.ACTIVE_HIGH else f"!{safe_expr(reset)}"
    return f"{clocking(clock)} ({active}) |-> ({safe_expr(cons)})"


def body_cover_seq(
    clock: str, reset: str | None, pol: ResetPolarity, expr: str
) -> str:
    return f"{clocking(clock)}{disable_iff(reset, pol)} {safe_expr(expr)}"
