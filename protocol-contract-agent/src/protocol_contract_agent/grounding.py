"""Grounding: resolve role -> signal-name bindings against an RTL manifest module.

Deterministic. No inference of *which* signal plays a role (that comes from the
ContractRequest). What this module does:

* Look up each requested signal name in the module's ports / nets / registers.
* Build a :class:`GroundedSymbol` with a stable ``symbol_id``, ownership
  (env_input / dut_output / internal), width, and source location.
* Resolve clock/reset either from the request or from manifest candidates,
  never silently choosing when the request is explicit.

Ownership classification is the load-bearing safety feature: it lets the
generator refuse to place a DUT output under an ``assume`` without a review flag.
"""

from __future__ import annotations

from .models import (
    GroundedSymbol,
    MModule,
    PortDirection,
    ResetPolarity,
    ResetSync,
    SignalOwnership,
)


class GroundingError(ValueError):
    """Raised when a required signal name cannot be found in the module."""


def _symbol_id(module: str, name: str) -> str:
    return f"{module}.{name}"


def ground_signal(module: MModule, name: str) -> GroundedSymbol | None:
    """Resolve a signal name to a GroundedSymbol, or None if not found."""
    for p in module.ports:
        if p.name == name:
            ownership = (
                SignalOwnership.ENV_INPUT
                if p.direction == PortDirection.INPUT
                else SignalOwnership.DUT_OUTPUT
                if p.direction == PortDirection.OUTPUT
                else SignalOwnership.UNKNOWN
            )
            return GroundedSymbol(
                name=name,
                symbol_id=_symbol_id(module.name, name),
                ownership=ownership,
                direction=p.direction,
                width_msb=p.range.msb if p.range else None,
                width_lsb=p.range.lsb if p.range else None,
                file=p.location.file if p.location else None,
                line=p.location.line if p.location else None,
            )
    # registers and nets -> internal
    for r in module.registers:
        if r.name == name:
            return GroundedSymbol(
                name=name,
                symbol_id=_symbol_id(module.name, name),
                ownership=SignalOwnership.INTERNAL,
                file=r.location.file if r.location else None,
                line=r.location.line if r.location else None,
            )
    for netv in module.nets:
        if netv.name == name:
            return GroundedSymbol(
                name=name,
                symbol_id=_symbol_id(module.name, name),
                ownership=SignalOwnership.INTERNAL,
                width_msb=netv.range.msb if netv.range else None,
                width_lsb=netv.range.lsb if netv.range else None,
                file=netv.location.file if netv.location else None,
                line=netv.location.line if netv.location else None,
            )
    return None


def require_signal(module: MModule, name: str) -> GroundedSymbol:
    sym = ground_signal(module, name)
    if sym is None:
        raise GroundingError(
            f"signal {name!r} not found in module {module.name!r} "
            f"(ports/nets/registers)"
        )
    return sym


def resolve_clock(module: MModule, requested: str | None) -> GroundedSymbol | None:
    """Resolve the clock. If requested, ground it; else use highest-confidence
    manifest candidate. Returns None if nothing is available."""
    name = requested
    if name is None and module.clock_candidates:
        best = max(module.clock_candidates, key=lambda c: c.confidence)
        name = best.signal
    if name is None:
        return None
    return ground_signal(module, name) or GroundedSymbol(
        name=name,
        symbol_id=_symbol_id(module.name, name),
        ownership=SignalOwnership.ENV_INPUT,
    )


def resolve_reset(
    module: MModule, requested: str | None, forced_polarity: ResetPolarity | None
) -> tuple[GroundedSymbol | None, ResetPolarity, ResetSync]:
    """Resolve reset signal + polarity/sync.

    Polarity comes from: explicit request override > manifest candidate. It is
    NEVER inferred by name. If unknown, it stays ``unknown`` and the caller must
    flag reset behavior for review.
    """
    name = requested
    cand = None
    if name is None and module.reset_candidates:
        cand = max(module.reset_candidates, key=lambda c: c.confidence)
        name = cand.signal
    else:
        for c in module.reset_candidates:
            if c.signal == name:
                cand = c
                break

    polarity = forced_polarity or (cand.polarity if cand else ResetPolarity.UNKNOWN)
    sync = cand.sync if cand else ResetSync.UNKNOWN

    if name is None:
        return None, polarity, sync

    sym = ground_signal(module, name) or GroundedSymbol(
        name=name,
        symbol_id=_symbol_id(module.name, name),
        ownership=SignalOwnership.ENV_INPUT,
    )
    return sym, polarity, sync
