"""Consume the canonical RTL Intent Manifest (rtl-intent-ingestor schema).

This adapter lets the Reset Intent Agent run on an upstream manifest instead of
raw RTL. It maps the manifest's structural facts
(``modules[].procedures``, ``registers``, ``reset_candidates``) onto the
:class:`~reset_intent_agent.rtl_parser.ParsedModule` records the analyzer
already understands, so a single analysis path serves both input types.

Only fields present in ``rtl-intent-ingestor/schemas/manifest.schema.json`` are
read. Missing/optional fields degrade gracefully.
"""

from __future__ import annotations

from typing import Any

from .models import SourceLocation
from .rtl_parser import (
    AlwaysBlock,
    NbAssign,
    ParsedModule,
    Port,
    SensitivityItem,
    Unsupported,
)


def _loc(d: dict[str, Any] | None, fallback_file: str) -> SourceLocation:
    if not d:
        return SourceLocation(file=fallback_file, line=1)
    return SourceLocation(
        file=d.get("file", fallback_file),
        line=int(d.get("line", 1)),
        col=d.get("col"),
        end_line=d.get("end_line"),
        end_col=d.get("end_col"),
    )


def parsed_modules_from_manifest(manifest: dict[str, Any]) -> list[ParsedModule]:
    """Translate an RTL Intent Manifest dict into ParsedModule records."""
    out: list[ParsedModule] = []
    for m in manifest.get("modules", []):
        file_hint = (m.get("location") or {}).get("file", "manifest")
        pm = ParsedModule(name=m["name"], location=_loc(m.get("location"), file_hint))

        for p in m.get("ports", []):
            pm.ports.append(
                Port(
                    name=p["name"],
                    direction=p["direction"],
                    location=_loc(p.get("location"), file_hint),
                )
            )

        # Build a set of registers (nonblocking targets under edge blocks).
        reg_by_proc: dict[int, list[str]] = {}
        for r in m.get("registers", []):
            reg_by_proc.setdefault(int(r["driven_in_procedure_index"]), []).append(
                r["name"]
            )

        for proc in m.get("procedures", []):
            kind = proc.get("kind", "always")
            sens = []
            is_edge = kind == "always_ff"
            for s in proc.get("sensitivity", []):
                edge = s.get("edge")
                sens.append(SensitivityItem(signal=s["signal"], edge=edge))
                if edge:
                    is_edge = True
            blk = AlwaysBlock(
                index=int(proc.get("index", 0)),
                sensitivity=sens,
                location=_loc(proc.get("location"), file_hint),
                is_edge_sensitive=is_edge,
            )
            _reconstruct_assigns(proc, blk, file_hint, m)
            pm.always_blocks.append(blk)

        # Fold declared reset_candidates that the manifest already found and that
        # our procedure walk may have missed (e.g. no assignment detail).
        _fold_manifest_reset_candidates(m, pm, file_hint)

        for u in manifest.get("unresolved", []):
            pm.unsupported.append(
                Unsupported(kind=u.get("kind", "unresolved"), detail=u.get("detail", ""))
            )
        out.append(pm)
    return out


def _reconstruct_assigns(
    proc: dict[str, Any], blk: AlwaysBlock, file_hint: str, module: dict[str, Any]
) -> None:
    """Rebuild NbAssign records with reset guards from manifest assignments.

    The canonical manifest stores explicit ``assignments`` with lhs/rhs/
    nonblocking. It does not store the if/else nesting, so reset attribution is
    recovered by matching a guard signal (a condition_signal that looks like a
    reset) against a reset-value assignment (rhs is a constant).
    """
    condition_signals = proc.get("condition_signals", [])
    reset_guard = _pick_reset_guard(condition_signals)

    for a in proc.get("assignments", []):
        if not a.get("nonblocking", False):
            continue
        lhs = _base_name(a["lhs"])
        rhs = a["rhs"].strip()
        loc = _loc(a.get("location"), file_hint)
        under_reset = reset_guard is not None and _is_constant(rhs)
        blk.assigns.append(
            NbAssign(
                lhs=lhs,
                rhs=rhs,
                location=loc,
                under_reset=under_reset,
                reset_signal=reset_guard if under_reset else None,
                reset_active_expr=_guard_expr(reset_guard) if under_reset else None,
            )
        )
    if reset_guard:
        blk.reset_guards.append(reset_guard)


def _fold_manifest_reset_candidates(
    m: dict[str, Any], pm: ParsedModule, file_hint: str
) -> None:
    """If the manifest declares reset candidates with a known type, ensure a
    synthetic edge-block guard exists so the analyzer picks up polarity from the
    manifest's ``signal_type`` (active_low/active_high) as guard evidence."""
    for rc in m.get("reset_candidates", []):
        sig = rc.get("signal")
        if not sig:
            continue
        already = any(
            a.reset_signal == sig for b in pm.always_blocks for a in b.assigns
        )
        if already:
            continue
        pol = rc.get("polarity") or rc.get("signal_type")
        # Represent as a guard on the first edge block, if any.
        edge_blocks = [b for b in pm.always_blocks if b.is_edge_sensitive]
        if not edge_blocks:
            continue
        guard = _guard_expr_from_polarity(sig, pol)
        edge_blocks[0].reset_guards.append(sig)
        # attach a zero-target guard so polarity evidence is captured
        edge_blocks[0].assigns.append(
            NbAssign(
                lhs=f"__manifest_reset_{sig}",
                rhs="0",
                location=_loc(rc.get("location"), file_hint),
                under_reset=True,
                reset_signal=sig,
                reset_active_expr=guard,
            )
        )


# --------------------------------------------------------------------------- #
# Small heuristics
# --------------------------------------------------------------------------- #
_RESET_HINT = ("rst", "reset")


def _pick_reset_guard(condition_signals: list[str]) -> str | None:
    for s in condition_signals:
        low = s.lower()
        if any(h in low for h in _RESET_HINT):
            return s
    return None


def _base_name(lhs: str) -> str:
    import re

    m = re.match(r"[A-Za-z_]\w*", lhs.strip())
    return m.group(0) if m else lhs.strip()


def _is_constant(rhs: str) -> bool:
    import re

    return bool(re.fullmatch(r"[0-9]+|\d*'[bBhHdD][0-9a-fA-FxXzZ_]+|'?[01]", rhs.strip()))


def _guard_expr(signal: str | None) -> str | None:
    if signal is None:
        return None
    return f"!{signal}" if signal.lower().endswith("_n") else signal


def _guard_expr_from_polarity(signal: str, polarity: str | None) -> str:
    if polarity == "active_low":
        return f"!{signal}"
    if polarity == "active_high":
        return signal
    return signal
