"""Heuristic clock/reset candidate detection.

These functions are explicitly HEURISTIC (labelled as such in the manifest via
confidence scores and rationale strings). They combine two evidence sources:

1. Name-based lexical hints (``clk``, ``clock``, ``rst``, ``reset``, ``rst_n``).
2. Structural evidence from ``always_ff`` sensitivity lists (edge signals are
   strong clock candidates; edge signals whose name looks like a reset and which
   appear alongside a clock edge are strong async-reset candidates).

Nothing here is a formal claim about clock/reset roles. Confidence is a bounded
heuristic score in [0, 1].
"""

from __future__ import annotations

from .models import (
    ClockCandidate,
    Module,
    ProcedureKind,
    ResetCandidate,
    ResetPolarity,
    ResetSync,
)

_CLOCK_NAME_HINTS = ("clk", "clock", "clkin", "gclk", "aclk", "hclk")
_RESET_NAME_HINTS = ("rst", "reset", "resetn", "rstn", "nreset", "aresetn")
_ACTIVE_LOW_SUFFIXES = ("_n", "n", "_b", "_l")


def _looks_like_clock(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _CLOCK_NAME_HINTS)


def _looks_like_reset(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _RESET_NAME_HINTS)


def _reset_polarity_from_name(name: str) -> ResetPolarity:
    low = name.lower()
    # Names ending in n/_n/rstn/aresetn conventionally denote active-low.
    if low.endswith(("_n", "n_", "rstn", "resetn", "aresetn", "_b", "_l")):
        return ResetPolarity.ACTIVE_LOW
    if low.startswith("n") and _looks_like_reset(low):
        return ResetPolarity.ACTIVE_LOW
    return ResetPolarity.UNKNOWN


def detect_clock_reset(module: Module) -> None:
    """Populate ``module.clock_candidates`` and ``module.reset_candidates``.

    Deterministic given the module structure. Scores are stable so golden JSON
    comparisons are meaningful.
    """
    port_names = {p.name for p in module.ports}
    loc_by_name = {p.name: p.location for p in module.ports}

    clock_scores: dict[str, tuple[float, list[str]]] = {}
    reset_scores: dict[str, tuple[float, list[str]]] = {}
    reset_polarity: dict[str, ResetPolarity] = {}
    reset_sync: dict[str, ResetSync] = {}

    def bump_clock(sig: str, amount: float, reason: str) -> None:
        score, reasons = clock_scores.get(sig, (0.0, []))
        clock_scores[sig] = (min(1.0, score + amount), [*reasons, reason])

    def bump_reset(sig: str, amount: float, reason: str) -> None:
        score, reasons = reset_scores.get(sig, (0.0, []))
        reset_scores[sig] = (min(1.0, score + amount), [*reasons, reason])

    # 1. Structural evidence from always_ff sensitivity lists.
    for proc in module.procedures:
        if proc.kind != ProcedureKind.ALWAYS_FF:
            continue
        edge_signals = [s for s in proc.sensitivity if s.edge]
        for s in edge_signals:
            if _looks_like_reset(s.signal):
                bump_reset(
                    s.signal,
                    0.5,
                    f"edge-sensitive in always_ff (proc #{proc.index}) with reset-like name",
                )
                reset_sync[s.signal] = ResetSync.ASYNCHRONOUS
                # negedge on active-low reset is the classic pattern.
                if s.edge == "negedge":
                    reset_polarity[s.signal] = ResetPolarity.ACTIVE_LOW
            else:
                bump_clock(
                    s.signal,
                    0.6,
                    f"edge-sensitive in always_ff (proc #{proc.index})",
                )

    # 2. Name-based evidence over ports.
    for name in sorted(port_names):
        if _looks_like_clock(name):
            bump_clock(name, 0.4, "name matches clock convention")
        if _looks_like_reset(name):
            bump_reset(name, 0.4, "name matches reset convention")

    # Detect synchronous reset used inside an always_ff body but not in the
    # sensitivity list (e.g. `if (rst) q <= 0;`). Heuristic and weak.
    for proc in module.procedures:
        if proc.kind != ProcedureKind.ALWAYS_FF:
            continue
        sens_names = {s.signal for s in proc.sensitivity}
        for tok in proc.condition_signals:
            if _looks_like_reset(tok) and tok in port_names and tok not in sens_names:
                bump_reset(
                    tok,
                    0.35,
                    f"reset-like name in always_ff control condition (proc #{proc.index})",
                )
                reset_sync.setdefault(tok, ResetSync.SYNCHRONOUS)

    # Emit sorted, deterministic candidate lists (highest score first, then name).
    module.clock_candidates = [
        ClockCandidate(
            signal=sig,
            confidence=round(score, 3),
            rationale=reasons,
            location=loc_by_name.get(sig),
        )
        for sig, (score, reasons) in sorted(
            clock_scores.items(), key=lambda kv: (-kv[1][0], kv[0])
        )
    ]

    module.reset_candidates = [
        ResetCandidate(
            signal=sig,
            confidence=round(score, 3),
            polarity=reset_polarity.get(
                sig, _reset_polarity_from_name(sig)
            ),
            sync=reset_sync.get(sig, ResetSync.UNKNOWN),
            rationale=reasons,
            location=loc_by_name.get(sig),
        )
        for sig, (score, reasons) in sorted(
            reset_scores.items(), key=lambda kv: (-kv[1][0], kv[0])
        )
    ]
