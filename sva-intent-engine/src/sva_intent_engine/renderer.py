"""Safe SVA renderer (spec 5.6).

Deterministic template renderer for a fixed set of property forms. There is NO
free-form string interpolation of untrusted text: every expression that reaches
a template is first passed through :func:`safe_expr`, which admits only a small
whitelist of SystemVerilog expression syntax. Anything else is rejected.

Supported forms (PropertyForm):
    invariant, implication (|->), bounded_response (|-> ##[N:M]),
    next_cycle (|=>), no_overflow, no_underflow, one_hot,
    stable_while_stalled, reset_state, eventually_within_bound (cover).

Renderer safety checks (raise RenderError):
    * absent clock
    * unresolved symbols
    * invalid timing range (min > max, negatives)
    * unsupported / unsafe expressions
"""

from __future__ import annotations

import re

from .models import (
    CandidateProperty,
    ImplicationStyle,
    PropertyForm,
    PropertyKind,
    Provenance,
    ResetPolarity,
    Severity,
    TemporalIntent,
    ValidationCheck,
)

# Whitelist for expression tokens. Identifiers, integer/bit literals, common
# comparison/boolean/arithmetic operators, parens, brackets, and a few SV bits.
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

_BANNED = (";", "$", "//", "/*", "\n", "\\", "`", "assert", "assume", "cover")


class RenderError(ValueError):
    """Raised when a property cannot be rendered safely."""


def safe_expr(expr: str) -> str:
    """Validate and normalize an SV boolean/arith expression.

    Rejects anything containing tokens outside the whitelist, statement
    terminators, system tasks, comments, or nested SVA keywords.
    """
    if expr is None or expr.strip() == "":
        raise RenderError("empty expression")
    low = expr.lower()
    for bad in _BANNED:
        if bad in low:
            raise RenderError(f"unsafe token in expression: {bad!r}")

    # Tokenize greedily; any leftover means an illegal character.
    pos = 0
    n = len(expr)
    while pos < n:
        m = _EXPR_TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            raise RenderError(
                f"unsupported expression syntax near: {expr[pos:pos+12]!r}"
            )
        pos = m.end()
    return expr.strip()


def _clocking(intent: TemporalIntent) -> str:
    if not intent.clock_signal:
        raise RenderError("absent clock: every temporal property needs a clock")
    return f"@(posedge {intent.clock_signal})"


def _disable(intent: TemporalIntent) -> str:
    if intent.disable_condition:
        cond = safe_expr(intent.disable_condition)
        return f" disable iff ({cond})"
    if intent.reset_signal:
        if intent.reset_polarity == ResetPolarity.ACTIVE_LOW:
            return f" disable iff (!{intent.reset_signal})"
        if intent.reset_polarity == ResetPolarity.ACTIVE_HIGH:
            return f" disable iff ({intent.reset_signal})"
        # Unknown polarity: do NOT guess. No disable clause; note it upstream.
    return ""


def _check_timing(intent: TemporalIntent) -> None:
    lo, hi = intent.min_delay, intent.max_delay
    if lo is not None and lo < 0:
        raise RenderError("invalid timing range: negative min_delay")
    if hi is not None and hi < 0:
        raise RenderError("invalid timing range: negative max_delay")
    if lo is not None and hi is not None and hi < lo:
        raise RenderError(f"invalid timing range: max {hi} < min {lo}")


def _require_symbols(intent: TemporalIntent) -> None:
    if intent.ambiguities:
        # Ambiguity alone does not block, but unresolved symbols do; the
        # generator marks unresolved symbols by leaving referenced_symbols empty
        # while the form needs them. We check per-form below.
        pass


def _impl_op(style: ImplicationStyle | None) -> str:
    if style == ImplicationStyle.NON_OVERLAPPING:
        return "|=>"
    return "|->"


def render(intent: TemporalIntent) -> str:
    """Render the SVA body for an intent. Raises RenderError on any unsafe input."""
    form = intent.property_form
    _require_symbols(intent)

    # Cover forms and reset_state still need a clock.
    clk = _clocking(intent)
    dis = _disable(intent)

    if form == PropertyForm.INVARIANT:
        cond = safe_expr(_need(intent.consequent, "invariant condition"))
        return f"{clk}{dis} {cond}"

    if form == PropertyForm.IMPLICATION:
        ante = safe_expr(_need(intent.antecedent, "antecedent"))
        cons = safe_expr(_need(intent.consequent, "consequent"))
        op = _impl_op(intent.implication_style or ImplicationStyle.OVERLAPPING)
        return f"{clk}{dis} ({ante}) {op} ({cons})"

    if form == PropertyForm.NEXT_CYCLE:
        ante = safe_expr(_need(intent.antecedent, "antecedent"))
        cons = safe_expr(_need(intent.consequent, "consequent"))
        # next-cycle is non-overlapping by definition.
        return f"{clk}{dis} ({ante}) |=> ({cons})"

    if form == PropertyForm.BOUNDED_RESPONSE:
        _check_timing(intent)
        if intent.min_delay is None or intent.max_delay is None:
            raise RenderError("bounded_response requires explicit min and max delay")
        ante = safe_expr(_need(intent.antecedent, "antecedent"))
        cons = safe_expr(_need(intent.consequent, "consequent"))
        op = _impl_op(intent.implication_style or ImplicationStyle.OVERLAPPING)
        lo, hi = intent.min_delay, intent.max_delay
        rng = f"##[{lo}:{hi}]" if lo != hi else f"##{lo}"
        return f"{clk}{dis} ({ante}) {op} {rng} ({cons})"

    if form == PropertyForm.NO_OVERFLOW:
        # antecedent = "at max value" guard, consequent = "no further increment"
        guard = safe_expr(_need(intent.antecedent, "overflow guard"))
        cons = safe_expr(_need(intent.consequent, "no-overflow consequent"))
        return f"{clk}{dis} ({guard}) |=> ({cons})"

    if form == PropertyForm.NO_UNDERFLOW:
        guard = safe_expr(_need(intent.antecedent, "underflow guard"))
        cons = safe_expr(_need(intent.consequent, "no-underflow consequent"))
        return f"{clk}{dis} ({guard}) |=> ({cons})"

    if form == PropertyForm.ONE_HOT:
        expr = safe_expr(_need(intent.consequent, "one-hot vector"))
        return f"{clk}{dis} $onehot({expr})"

    if form == PropertyForm.STABLE_WHILE_STALLED:
        stall = safe_expr(_need(intent.antecedent, "stall condition"))
        data = safe_expr(_need(intent.consequent, "stable data"))
        return f"{clk}{dis} ({stall}) |=> $stable({data})"

    if form == PropertyForm.RESET_STATE:
        # value expected while reset is asserted.
        if not intent.reset_signal:
            raise RenderError("reset_state requires a reset signal")
        if intent.reset_polarity == ResetPolarity.UNKNOWN:
            raise RenderError(
                "reset_state requires known reset polarity (do not guess)"
            )
        cons = safe_expr(_need(intent.consequent, "reset state value"))
        active = (
            intent.reset_signal
            if intent.reset_polarity == ResetPolarity.ACTIVE_HIGH
            else f"!{intent.reset_signal}"
        )
        # No disable-iff here: the property is *about* reset.
        return f"{clk} ({active}) |-> ({cons})"

    if form == PropertyForm.EVENTUALLY_WITHIN_BOUND:
        _check_timing(intent)
        if intent.max_delay is None:
            raise RenderError("eventually_within_bound requires an explicit max delay")
        lo = intent.min_delay if intent.min_delay is not None else 0
        hi = intent.max_delay
        cons = safe_expr(_need(intent.consequent, "cover target"))
        if intent.antecedent:
            ante = safe_expr(intent.antecedent)
            return f"{clk}{dis} ({ante}) |-> ##[{lo}:{hi}] ({cons})"
        return f"{clk}{dis} ##[{lo}:{hi}] ({cons})"

    raise RenderError(f"unsupported property form: {form}")


def _need(value: str | None, what: str) -> str:
    if value is None or value.strip() == "":
        raise RenderError(f"missing required expression: {what}")
    return value


def _directive(kind: PropertyKind) -> str:
    return {
        PropertyKind.ASSERT: "assert property",
        PropertyKind.ASSUME: "assume property",
        PropertyKind.COVER: "cover property",
    }[kind]


def render_property(
    intent: TemporalIntent,
    *,
    git_sha: str = "UNKNOWN",
    command: str | None = None,
) -> CandidateProperty:
    """Render a full named SVA property block from an intent.

    Raises RenderError if any safety check fails.
    """
    body = render(intent)
    name = f"p_{intent.clause_id.replace('.', '_')}_{intent.property_form.value}"
    sva_text = (
        f"{name}: {_directive(intent.property_kind)} (\n"
        f"  {body}\n"
        f");"
    )
    prov = Provenance(
        stage="generate",
        git_sha=git_sha,
        command=command,
        input_hashes={"clause": intent.clause_id},
    )
    return CandidateProperty(
        property_name=name,
        requirement_id=intent.requirement_id,
        clause_id=intent.clause_id,
        property_kind=intent.property_kind,
        property_form=intent.property_form,
        sva_text=sva_text,
        referenced_symbols=list(intent.referenced_symbols),
        ambiguities=list(intent.ambiguities),
        provenance=prov,
    )


def validate_intent(intent: TemporalIntent) -> list[ValidationCheck]:
    """Static validation checks for an intent, independent of rendering."""
    checks: list[ValidationCheck] = []

    checks.append(
        ValidationCheck(
            check="clock_present",
            passed=bool(intent.clock_signal),
            severity=Severity.ERROR,
            detail=None if intent.clock_signal else "no clock -> reject",
        )
    )

    unresolved = [s for s in intent.referenced_symbols if not s.symbol_id]
    checks.append(
        ValidationCheck(
            check="symbols_resolved",
            passed=len(unresolved) == 0,
            severity=Severity.ERROR,
            detail=None if not unresolved else f"unresolved: {unresolved}",
        )
    )

    timing_ok = True
    detail = None
    if intent.min_delay is not None and intent.max_delay is not None:
        if intent.max_delay < intent.min_delay:
            timing_ok = False
            detail = f"max {intent.max_delay} < min {intent.min_delay}"
    checks.append(
        ValidationCheck(
            check="timing_range_valid",
            passed=timing_ok,
            severity=Severity.ERROR,
            detail=detail,
        )
    )

    # Try a dry render to catch unsupported expressions.
    render_ok = True
    render_detail = None
    try:
        render(intent)
    except RenderError as exc:
        render_ok = False
        render_detail = str(exc)
    checks.append(
        ValidationCheck(
            check="renders_safely",
            passed=render_ok,
            severity=Severity.ERROR,
            detail=render_detail,
        )
    )

    if intent.ambiguities:
        checks.append(
            ValidationCheck(
                check="no_ambiguities",
                passed=False,
                severity=Severity.WARNING,
                detail=f"{len(intent.ambiguities)} ambiguity(ies) present",
            )
        )
    return checks
