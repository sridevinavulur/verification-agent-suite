"""Deterministic, parameterized contract templates, one per protocol.

Each template takes a resolved :class:`_Ctx` (grounded roles + clock/reset) and
produces the protocol-specific assumptions, guarantees, cover/negative
properties, dependencies, and checklist additions.

Design rules enforced structurally here:
* Assumptions are placed only on env inputs. If a role we'd normally *assume*
  turns out to be a DUT output, we downgrade it to a flagged item
  (``ownership_ok=False``) instead of silently constraining an output.
* Every property references only GroundedSymbols.
* Reset behavior is explicit; if polarity is unknown, reset-dependent guarantees
  that need polarity are skipped with a warning rather than guessed.
* FIFO / credit multiple-outstanding state (occupancy / outstanding count) is
  modeled with an explicit note that a single-transaction abstraction is NOT
  assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import sva
from .models import (
    Assumption,
    ChecklistItem,
    ContractProperty,
    GroundedSymbol,
    Guarantee,
    NegativeScenario,
    PropertyKind,
    ResetPolarity,
    Severity,
    SignalOwnership,
    Warning,
)


@dataclass
class _Ctx:
    module: str
    clock: str | None
    reset: str | None
    reset_polarity: ResetPolarity
    roles: dict[str, GroundedSymbol]
    depth: int | None = None
    max_credits: int | None = None
    min_delay: int | None = None
    max_delay: int | None = None
    warnings: list[Warning] = field(default_factory=list)


@dataclass
class _Result:
    assumptions: list[Assumption] = field(default_factory=list)
    guarantees: list[Guarantee] = field(default_factory=list)
    properties: list[ContractProperty] = field(default_factory=list)
    negatives: list[NegativeScenario] = field(default_factory=list)
    checklist: list[ChecklistItem] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


def _pname(ctx: _Ctx, suffix: str) -> str:
    return f"p_{ctx.module}_{suffix}"


def _assume_env(
    ctx: _Ctx,
    aid: str,
    desc: str,
    body: str,
    syms: list[GroundedSymbol],
) -> Assumption:
    """Build an assumption, verifying all referenced signals are env inputs.

    If any referenced signal is a DUT output/internal, mark ownership_ok=False so
    the reviewer is forced to decide (never silently constrain an output)."""
    bad = [s for s in syms if s.ownership != SignalOwnership.ENV_INPUT]
    ok = len(bad) == 0
    reason = None
    if not ok:
        names = ", ".join(f"{s.name}({s.ownership.value})" for s in bad)
        reason = (
            f"assumption references non-input signal(s): {names}. "
            "Constraining a DUT output/internal as an environment assumption "
            "requires explicit human review."
        )
        ctx.warnings.append(
            Warning(
                code="assume_on_output",
                message=f"[{aid}] {reason}",
                severity=Severity.WARNING,
            )
        )
    return Assumption(
        id=aid,
        description=desc,
        sva=body,
        referenced_symbols=syms,
        ownership_ok=ok,
        review_reason=reason,
    )


def _prop_from_assume(a: Assumption, ctx: _Ctx, suffix: str) -> ContractProperty:
    return ContractProperty(
        name=_pname(ctx, suffix),
        property_kind=PropertyKind.ASSUME,
        role="assumption",
        description=a.description,
        sva_text=sva.wrap(_pname(ctx, suffix), PropertyKind.ASSUME, a.sva),
        referenced_symbols=a.referenced_symbols,
        notes=([a.review_reason] if a.review_reason else []),
    )


def _prop_from_guar(g: Guarantee, ctx: _Ctx, suffix: str, depends=None) -> ContractProperty:
    return ContractProperty(
        name=_pname(ctx, suffix),
        property_kind=PropertyKind.ASSERT,
        role="guarantee",
        description=g.description,
        sva_text=sva.wrap(_pname(ctx, suffix), PropertyKind.ASSERT, g.sva),
        referenced_symbols=g.referenced_symbols,
        depends_on=depends or [],
    )


def _cover(ctx: _Ctx, suffix: str, desc: str, body: str, syms) -> ContractProperty:
    return ContractProperty(
        name=_pname(ctx, suffix),
        property_kind=PropertyKind.COVER,
        role="cover",
        description=desc,
        sva_text=sva.wrap(_pname(ctx, suffix), PropertyKind.COVER, body),
        referenced_symbols=syms,
    )


def _neg_prop(ctx: _Ctx, n: NegativeScenario, suffix: str) -> ContractProperty:
    return ContractProperty(
        name=_pname(ctx, suffix),
        property_kind=n.property_kind,
        role="negative",
        description=n.description,
        sva_text=sva.wrap(_pname(ctx, suffix), n.property_kind, n.sva),
        referenced_symbols=n.referenced_symbols,
    )


def _reset_ck(ctx: _Ctx) -> ChecklistItem:
    if ctx.reset is None:
        return ChecklistItem(
            id="reset_present",
            question="No reset was resolved. Confirm the interface truly has no "
            "reset, or supply one.",
            severity=Severity.WARNING,
            auto_status="WARN",
        )
    if ctx.reset_polarity == ResetPolarity.UNKNOWN:
        return ChecklistItem(
            id="reset_polarity",
            question=f"Reset {ctx.reset!r} polarity is UNKNOWN. Confirm polarity; "
            "properties that need it were skipped.",
            severity=Severity.ERROR,
            auto_status="FAIL",
        )
    return ChecklistItem(
        id="reset_polarity",
        question=f"Confirm reset {ctx.reset!r} is {ctx.reset_polarity.value} "
        "and that disable-iff semantics match the intended reset behavior.",
        severity=Severity.INFO,
        auto_status="REVIEW",
    )


# --------------------------------------------------------------------------- #
# valid/ready
# --------------------------------------------------------------------------- #


def valid_ready(ctx: _Ctx) -> _Result:
    r = _Result()
    valid = ctx.roles["valid"]
    ready = ctx.roles["ready"]
    data = ctx.roles.get("data")
    pol = ctx.reset_polarity
    clk = ctx.clock

    # Environmental assumption: the *upstream* side of whichever signal is an
    # input. We do not assume anything on a DUT output.
    # valid stability: if valid && !ready, valid must stay high next cycle
    # (standard AXI-stream style). Whether this is an assume or assert depends
    # on ownership: if valid is an input, it is an env assumption; if valid is a
    # DUT output, it is a design guarantee.
    valid_stable_body = sva.body_implication(
        clk, ctx.reset, pol, f"{valid.name} && !{ready.name}", valid.name,
        overlapping=False,
    )
    if valid.ownership == SignalOwnership.ENV_INPUT:
        a = _assume_env(
            ctx, "a_valid_stable",
            "While valid is asserted and not accepted, valid remains asserted "
            "until handshake completes (source holds valid).",
            valid_stable_body, [valid, ready],
        )
        r.assumptions.append(a)
        r.properties.append(_prop_from_assume(a, ctx, "valid_stable_assume"))
    else:
        g = Guarantee(
            id="g_valid_stable",
            description="While valid is asserted and not accepted, valid remains "
            "asserted (DUT source holds valid until handshake).",
            sva=valid_stable_body,
            referenced_symbols=[valid, ready],
        )
        r.guarantees.append(g)
        r.properties.append(_prop_from_guar(g, ctx, "valid_stable"))

    # data stability while stalled (only if data present)
    if data is not None:
        data_stable = sva.body_stable_while(
            clk, ctx.reset, pol, f"{valid.name} && !{ready.name}", data.name
        )
        if valid.ownership == SignalOwnership.ENV_INPUT:
            a = _assume_env(
                ctx, "a_data_stable",
                "Payload data is held stable while valid is asserted and not "
                "yet accepted.",
                data_stable, [valid, ready, data],
            )
            r.assumptions.append(a)
            r.properties.append(_prop_from_assume(a, ctx, "data_stable_assume"))
        else:
            g = Guarantee(
                id="g_data_stable",
                description="Payload data is held stable while valid is asserted "
                "and not yet accepted.",
                sva=data_stable,
                referenced_symbols=[valid, ready, data],
            )
            r.guarantees.append(g)
            r.properties.append(_prop_from_guar(g, ctx, "data_stable"))

    # Cover: a completed handshake.
    r.properties.append(
        _cover(
            ctx, "handshake_cover",
            "Cover at least one completed valid/ready handshake.",
            sva.body_cover_seq(clk, ctx.reset, pol, f"{valid.name} && {ready.name}"),
            [valid, ready],
        )
    )

    # Negative: ready must not be a precondition that violates handshake -- we
    # assert that acceptance only happens when valid is high (no accept w/o valid).
    neg = NegativeScenario(
        id="n_accept_without_valid",
        description="A transfer (ready high) must not be claimed complete without "
        "valid; assert ready implies valid is meaningful only when valid is set. "
        "Here we cover the illegal combination for review, not assert it away.",
        sva=sva.body_cover_seq(clk, ctx.reset, pol, f"{ready.name} && !{valid.name}"),
        property_kind=PropertyKind.COVER,
        referenced_symbols=[valid, ready],
    )
    r.negatives.append(neg)
    r.properties.append(_neg_prop(ctx, neg, "accept_without_valid_cover"))

    r.checklist.extend(
        [
            _reset_ck(ctx),
            ChecklistItem(
                id="vr_direction",
                question=f"Confirm role directions: valid={valid.ownership.value}, "
                f"ready={ready.ownership.value}. Is 'valid' produced by the side "
                "you intend to constrain?",
                severity=Severity.WARNING,
                auto_status="REVIEW",
            ),
            ChecklistItem(
                id="vr_no_combinational_deadlock",
                question="Confirm ready does not combinationally depend on valid in "
                "a way that creates a deadlock (not checked structurally here).",
                severity=Severity.INFO,
                auto_status="REVIEW",
            ),
        ]
    )
    return r


# --------------------------------------------------------------------------- #
# request/grant
# --------------------------------------------------------------------------- #


def req_grant(ctx: _Ctx) -> _Result:
    r = _Result()
    req = ctx.roles["req"]
    grant = ctx.roles["grant"]
    pol = ctx.reset_polarity
    clk = ctx.clock

    # Guarantee: grant is only asserted in response to a request (no spurious
    # grant). This constrains grant (typically a DUT output).
    no_spurious = sva.body_implication(
        clk, ctx.reset, pol, grant.name, req.name, overlapping=True
    )
    g = Guarantee(
        id="g_no_spurious_grant",
        description="Grant is asserted only while (or after) a request is present "
        "(no spurious grant).",
        sva=no_spurious,
        referenced_symbols=[grant, req],
    )
    r.guarantees.append(g)
    r.properties.append(_prop_from_guar(g, ctx, "no_spurious_grant"))

    # Bounded response: request -> grant within [min,max] if provided.
    if ctx.max_delay is not None:
        lo = ctx.min_delay if ctx.min_delay is not None else 1
        body = sva.body_bounded_response(
            clk, ctx.reset, pol, req.name, grant.name, lo, ctx.max_delay,
        )
        g2 = Guarantee(
            id="g_grant_latency",
            description=f"A sustained request receives a grant within "
            f"[{lo}:{ctx.max_delay}] cycles.",
            sva=body,
            referenced_symbols=[req, grant],
        )
        r.guarantees.append(g2)
        r.properties.append(
            _prop_from_guar(g2, ctx, "grant_latency", depends=[_pname(ctx, "no_spurious_grant")])
        )
    else:
        r.warnings.append(
            Warning(
                code="no_latency_bound",
                message="No max_delay provided: grant-latency guarantee omitted "
                "(a cycle bound is never invented).",
                severity=Severity.WARNING,
            )
        )

    # Assumption on the environment side: request is stable until granted (only
    # if req is an env input).
    req_stable = sva.body_implication(
        clk, ctx.reset, pol, f"{req.name} && !{grant.name}", req.name, overlapping=False
    )
    if req.ownership == SignalOwnership.ENV_INPUT:
        a = _assume_env(
            ctx, "a_req_stable",
            "A request is held stable until it is granted.",
            req_stable, [req, grant],
        )
        r.assumptions.append(a)
        r.properties.append(_prop_from_assume(a, ctx, "req_stable_assume"))

    # Cover: a granted request.
    r.properties.append(
        _cover(
            ctx, "grant_cover",
            "Cover at least one request that is granted.",
            sva.body_cover_seq(clk, ctx.reset, pol, f"{req.name} && {grant.name}"),
            [req, grant],
        )
    )

    r.checklist.extend(
        [
            _reset_ck(ctx),
            ChecklistItem(
                id="rg_multi_requestor",
                question="If multiple requestors share this grant, confirm this "
                "single-requestor contract is per-requestor and mutual exclusion "
                "of grants is a SEPARATE property (not modeled as one).",
                severity=Severity.WARNING,
                auto_status="REVIEW",
            ),
            ChecklistItem(
                id="rg_ownership",
                question=f"Confirm grant ({grant.ownership.value}) is a DUT output "
                f"and req ({req.ownership.value}) is the requestor side.",
                severity=Severity.WARNING,
                auto_status="REVIEW",
            ),
        ]
    )
    return r


# --------------------------------------------------------------------------- #
# FIFO
# --------------------------------------------------------------------------- #


def fifo(ctx: _Ctx) -> _Result:
    r = _Result()
    push = ctx.roles["push"]
    pop = ctx.roles["pop"]
    full = ctx.roles.get("full")
    empty = ctx.roles.get("empty")
    count = ctx.roles.get("count")
    pol = ctx.reset_polarity
    clk = ctx.clock

    # No overflow: never push when full.
    if full is not None:
        no_of_body = sva.body_no_change_beyond(
            clk, ctx.reset, pol, f"{full.name} && {push.name}", "1'b0"
        )
        neg = NegativeScenario(
            id="n_overflow",
            description="Overflow: a push while full must never occur (asserted as "
            "the negation of the bad event).",
            sva=sva.body_invariant(clk, ctx.reset, pol, f"!({full.name} && {push.name})"),
            property_kind=PropertyKind.ASSERT,
            referenced_symbols=[full, push],
        )
        r.negatives.append(neg)
        r.properties.append(_neg_prop(ctx, neg, "no_overflow"))
        del no_of_body  # kept for readability; invariant form used above

    # No underflow: never pop when empty.
    if empty is not None:
        neg = NegativeScenario(
            id="n_underflow",
            description="Underflow: a pop while empty must never occur.",
            sva=sva.body_invariant(clk, ctx.reset, pol, f"!({empty.name} && {pop.name})"),
            property_kind=PropertyKind.ASSERT,
            referenced_symbols=[empty, pop],
        )
        r.negatives.append(neg)
        r.properties.append(_neg_prop(ctx, neg, "no_underflow"))

    # Occupancy consistency (multiple outstanding entries -- explicitly NOT a
    # single-transaction model). Requires a count signal and known depth.
    if count is not None and ctx.depth is not None:
        g = Guarantee(
            id="g_count_bound",
            description=f"Occupancy count never exceeds depth {ctx.depth} "
            "(models MULTIPLE outstanding entries, not a single transaction).",
            sva=sva.body_invariant(clk, ctx.reset, pol, f"{count.name} <= {ctx.depth}"),
            referenced_symbols=[count],
        )
        r.guarantees.append(g)
        r.properties.append(_prop_from_guar(g, ctx, "count_bound"))

        # full/empty consistency with count.
        if full is not None:
            g2 = Guarantee(
                id="g_full_iff_count",
                description=f"full is asserted exactly when count == depth "
                f"({ctx.depth}).",
                sva=sva.body_invariant(
                    clk, ctx.reset, pol,
                    f"{full.name} == ({count.name} == {ctx.depth})",
                ),
                referenced_symbols=[full, count],
            )
            r.guarantees.append(g2)
            r.properties.append(_prop_from_guar(g2, ctx, "full_iff_count"))
        if empty is not None:
            g3 = Guarantee(
                id="g_empty_iff_count",
                description="empty is asserted exactly when count == 0.",
                sva=sva.body_invariant(
                    clk, ctx.reset, pol, f"{empty.name} == ({count.name} == 0)"
                ),
                referenced_symbols=[empty, count],
            )
            r.guarantees.append(g3)
            r.properties.append(_prop_from_guar(g3, ctx, "empty_iff_count"))
    elif count is not None and ctx.depth is None:
        r.warnings.append(
            Warning(
                code="no_depth",
                message="count present but depth not provided: count-bound and "
                "full/empty-consistency guarantees omitted (depth not invented).",
                severity=Severity.WARNING,
            )
        )

    # Reset-state property: after reset, FIFO is empty (needs polarity + empty).
    if empty is not None and ctx.reset is not None and pol != ResetPolarity.UNKNOWN:
        body = sva.body_reset_state(clk, ctx.reset, pol, empty.name)
        g = Guarantee(
            id="g_reset_empty",
            description="While reset is asserted, the FIFO reports empty.",
            sva=body,
            referenced_symbols=[empty],
        )
        r.guarantees.append(g)
        r.properties.append(_prop_from_guar(g, ctx, "reset_empty"))
    elif empty is not None and pol == ResetPolarity.UNKNOWN:
        r.warnings.append(
            Warning(
                code="reset_polarity_unknown",
                message="reset polarity unknown: reset-empty guarantee skipped "
                "(polarity is never guessed).",
                severity=Severity.WARNING,
            )
        )

    # Covers: fill to full, drain to empty, simultaneous push+pop.
    if full is not None:
        r.properties.append(
            _cover(ctx, "fill_cover", "Cover reaching full.",
                   sva.body_cover_seq(clk, ctx.reset, pol, full.name), [full])
        )
    if empty is not None:
        r.properties.append(
            _cover(ctx, "drain_cover", "Cover reaching empty after activity.",
                   sva.body_cover_seq(clk, ctx.reset, pol, empty.name), [empty])
        )
    r.properties.append(
        _cover(ctx, "concurrent_cover", "Cover simultaneous push and pop.",
               sva.body_cover_seq(clk, ctx.reset, pol, f"{push.name} && {pop.name}"),
               [push, pop])
    )

    r.checklist.extend(
        [
            _reset_ck(ctx),
            ChecklistItem(
                id="fifo_outstanding",
                question="Confirm occupancy is modeled with a real count/pointer "
                "(multiple outstanding entries), NOT collapsed to a single "
                "in-flight transaction.",
                severity=Severity.WARNING,
                auto_status="REVIEW" if count is not None else "WARN",
                detail=None if count is not None else "no count role bound",
            ),
            ChecklistItem(
                id="fifo_depth",
                question="Confirm the declared depth matches the RTL parameter.",
                severity=Severity.WARNING,
                auto_status="REVIEW" if ctx.depth is not None else "WARN",
            ),
            ChecklistItem(
                id="fifo_push_pop_ownership",
                question=f"push ({push.ownership.value}) / pop ({pop.ownership.value})"
                ": confirm which side drives each and whether push/pop can be "
                "asserted while full/empty (protocol choice).",
                severity=Severity.INFO,
                auto_status="REVIEW",
            ),
        ]
    )
    return r


# --------------------------------------------------------------------------- #
# interrupt
# --------------------------------------------------------------------------- #


def interrupt(ctx: _Ctx) -> _Result:
    r = _Result()
    irq = ctx.roles["irq"]
    src = ctx.roles.get("source")  # event/status source
    clear = ctx.roles.get("clear")  # write-1-to-clear or ack
    pol = ctx.reset_polarity
    clk = ctx.clock

    # Guarantee: irq stays asserted until cleared/acked (level-sensitive).
    if clear is not None:
        body = sva.body_implication(
            clk, ctx.reset, pol, f"{irq.name} && !{clear.name}", irq.name,
            overlapping=False,
        )
        g = Guarantee(
            id="g_irq_sticky",
            description="Interrupt remains asserted until it is cleared/acknowledged "
            "(level-sensitive, sticky).",
            sva=body,
            referenced_symbols=[irq, clear],
        )
        r.guarantees.append(g)
        r.properties.append(_prop_from_guar(g, ctx, "irq_sticky"))

        # After clear with no new source, irq deasserts next cycle.
        if src is not None:
            body2 = sva.body_implication(
                clk, ctx.reset, pol, f"{clear.name} && !{src.name}", f"!{irq.name}",
                overlapping=False,
            )
            g2 = Guarantee(
                id="g_irq_clears",
                description="After a clear with no pending source event, the "
                "interrupt deasserts on the next cycle.",
                sva=body2,
                referenced_symbols=[irq, clear, src],
            )
            r.guarantees.append(g2)
            r.properties.append(
                _prop_from_guar(g2, ctx, "irq_clears", depends=[_pname(ctx, "irq_sticky")])
            )

    # Rise on source: a source event eventually raises irq (bounded if given).
    if src is not None:
        if ctx.max_delay is not None:
            lo = ctx.min_delay if ctx.min_delay is not None else 1
            body = sva.body_bounded_response(
                clk, ctx.reset, pol, src.name, irq.name, lo, ctx.max_delay,
            )
            g = Guarantee(
                id="g_irq_raise",
                description=f"A source event raises the interrupt within "
                f"[{lo}:{ctx.max_delay}] cycles.",
                sva=body,
                referenced_symbols=[src, irq],
            )
            r.guarantees.append(g)
            r.properties.append(_prop_from_guar(g, ctx, "irq_raise"))
        else:
            r.warnings.append(
                Warning(
                    code="no_irq_latency",
                    message="No max_delay for interrupt latency: raise-latency "
                    "guarantee omitted (bound not invented).",
                    severity=Severity.WARNING,
                )
            )
        # Environmental assumption: source is an env input event.
        if src.ownership == SignalOwnership.ENV_INPUT:
            r.checklist.append(
                ChecklistItem(
                    id="irq_source_env",
                    question="Confirm the interrupt source is an environment event "
                    "and not gated by the DUT in a way that changes the contract.",
                    severity=Severity.INFO,
                    auto_status="REVIEW",
                )
            )

    r.properties.append(
        _cover(ctx, "irq_cover", "Cover the interrupt being asserted.",
               sva.body_cover_seq(clk, ctx.reset, pol, irq.name), [irq])
    )

    # Reset behavior: irq low during reset.
    if ctx.reset is not None and pol != ResetPolarity.UNKNOWN:
        body = sva.body_reset_state(clk, ctx.reset, pol, f"!{irq.name}")
        g = Guarantee(
            id="g_irq_reset_low",
            description="While reset is asserted, the interrupt is deasserted.",
            sva=body,
            referenced_symbols=[irq],
        )
        r.guarantees.append(g)
        r.properties.append(_prop_from_guar(g, ctx, "irq_reset_low"))

    r.checklist.append(_reset_ck(ctx))
    r.checklist.append(
        ChecklistItem(
            id="irq_edge_vs_level",
            question="Confirm whether the interrupt is level or edge sensitive; "
            "these templates assume LEVEL-sensitive sticky behavior.",
            severity=Severity.WARNING,
            auto_status="REVIEW",
        )
    )
    return r


# --------------------------------------------------------------------------- #
# credit-based flow control
# --------------------------------------------------------------------------- #


def credit(ctx: _Ctx) -> _Result:
    r = _Result()
    send = ctx.roles["send"]  # data/valid sent (consumes a credit)
    credit_ret = ctx.roles["credit_return"]  # credit returned from receiver
    credit_cnt = ctx.roles.get("credit_count")  # available credits (sender side)
    pol = ctx.reset_polarity
    clk = ctx.clock

    # Core guarantee: never send without an available credit.
    if credit_cnt is not None:
        neg = NegativeScenario(
            id="n_send_without_credit",
            description="A send must never occur when no credits are available "
            "(credit underflow).",
            sva=sva.body_invariant(
                clk, ctx.reset, pol, f"!({send.name} && ({credit_cnt.name} == 0))"
            ),
            property_kind=PropertyKind.ASSERT,
            referenced_symbols=[send, credit_cnt],
        )
        r.negatives.append(neg)
        r.properties.append(_neg_prop(ctx, neg, "no_send_without_credit"))

        # Credit count never exceeds max (multiple outstanding credits -- NOT a
        # single-transaction model).
        if ctx.max_credits is not None:
            g = Guarantee(
                id="g_credit_bound",
                description=f"Available credits never exceed max_credits "
                f"{ctx.max_credits} (tracks MULTIPLE outstanding credits).",
                sva=sva.body_invariant(
                    clk, ctx.reset, pol, f"{credit_cnt.name} <= {ctx.max_credits}"
                ),
                referenced_symbols=[credit_cnt],
            )
            r.guarantees.append(g)
            r.properties.append(_prop_from_guar(g, ctx, "credit_bound"))
        else:
            r.warnings.append(
                Warning(
                    code="no_max_credits",
                    message="max_credits not provided: credit-bound guarantee "
                    "omitted (limit not invented).",
                    severity=Severity.WARNING,
                )
            )
    else:
        r.warnings.append(
            Warning(
                code="no_credit_count",
                message="credit_count role not bound: cannot express "
                "no-send-without-credit as a grounded property.",
                severity=Severity.ERROR,
            )
        )

    # Assumption on env: credit returns only correspond to real prior sends is a
    # protocol invariant on the RECEIVER side; if credit_return is an env input,
    # assume it is only pulsed when the receiver has freed a slot. Flag for review.
    if credit_ret.ownership == SignalOwnership.ENV_INPUT:
        r.checklist.append(
            ChecklistItem(
                id="credit_return_source",
                question="Confirm credit_return is only asserted by the receiver "
                "when it genuinely frees a buffer slot (conservation of credits). "
                "This is an environment assumption that must be justified.",
                severity=Severity.WARNING,
                auto_status="REVIEW",
            )
        )

    # Cover: send while credits available, and credits exhausted then replenished.
    r.properties.append(
        _cover(ctx, "send_cover", "Cover a send.",
               sva.body_cover_seq(clk, ctx.reset, pol, send.name), [send])
    )
    if credit_cnt is not None:
        r.properties.append(
            _cover(ctx, "credit_exhausted_cover",
                   "Cover credits reaching zero (back-pressure exercised).",
                   sva.body_cover_seq(clk, ctx.reset, pol, f"{credit_cnt.name} == 0"),
                   [credit_cnt])
        )

    # Reset: credits reset to a known initial value is NOT assumed (value unknown);
    # flag it for review rather than invent an init value.
    r.checklist.append(
        ChecklistItem(
            id="credit_reset_value",
            question="Confirm the credit count's reset/initial value. It is NOT "
            "assumed here (no init value is invented).",
            severity=Severity.WARNING,
            auto_status="WARN",
        )
    )
    r.checklist.append(_reset_ck(ctx))
    return r


# Role requirements per protocol: (required roles, optional roles).
REQUIRED_ROLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "valid_ready": (("valid", "ready"), ("data",)),
    "req_grant": (("req", "grant"), ()),
    "fifo": (("push", "pop"), ("full", "empty", "count")),
    "interrupt": (("irq",), ("source", "clear")),
    "credit": (("send", "credit_return"), ("credit_count",)),
}

GENERATORS = {
    "valid_ready": valid_ready,
    "req_grant": req_grant,
    "fifo": fifo,
    "interrupt": interrupt,
    "credit": credit,
}
