"""Interop adapter for the canonical RTL Intent Manifest schema.

The triage engine consumes a small ``RTLIntentManifest`` (see ``models.py``): a
flat ``{name -> RTLSymbol}`` map with backward-dependency ``drivers`` edges used
for cone-of-influence traversal and source citations.

The *canonical* manifest emitted by the ``rtl-intent-ingestor`` tool
(``rtl-intent-ingestor/schemas/manifest.schema.json``) is a richer, per-module
structure (ports, nets, registers, continuous assigns, procedures, hierarchy).
This module deterministically **projects** that canonical structure down onto the
triage engine's flat symbol/driver model. It is a pure text->model transform: no
RTL is parsed, executed, or modified.

Two entry points, plus auto-detection:

* :func:`from_canonical_manifest` -- ingest a canonical manifest document.
* :func:`load_manifest` -- load a manifest file, auto-detecting whether it is the
  repo's native fixture or the canonical schema, keeping full back-compat with the
  existing ``examples/toy_counter/manifest.json`` fixture.

Driver (fan-in) edges are reconstructed structurally:

* a continuous assign ``lhs = rhs`` makes every identifier in ``rhs`` a driver of
  ``lhs``;
* a procedure makes its ``condition_signals`` and the RHS identifiers of each
  assignment drivers of that assignment's ``lhs`` (and of the block's
  ``assignment_targets`` when per-assignment RHS is unavailable).

This mirrors the intent of the reference ``compute_cone`` fan-in graph while
staying entirely within this repository (no import of ``spec-to-cov-agent`` or
``rtl-intent-ingestor`` code).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import RTLIntentManifest, RTLSymbol, SourceLocation

# A conservative Verilog/SVA identifier extractor. It deliberately ignores
# numeric literals (``1'b1``, ``8``), operators, and keywords so that only signal
# names survive as candidate drivers.
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")

# Tokens that look like identifiers but are Verilog keywords / operators, never
# signals. Kept small and explicit -- this is a structural heuristic, not a parser.
_NON_SIGNAL_TOKENS = frozenset(
    {
        "begin",
        "end",
        "if",
        "else",
        "case",
        "endcase",
        "default",
        "posedge",
        "negedge",
        "or",
        "and",
        "not",
        "assign",
        "wire",
        "reg",
        "logic",
        "b",
        "d",
        "h",
        "o",
    }
)


def _extract_signals(expr: str) -> list[str]:
    """Return identifiers referenced in a Verilog expression, order-preserving.

    Based-number width/base markers such as the ``b`` in ``1'b1`` are dropped:
    any identifier immediately preceded by ``'`` is a base char, not a signal.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _IDENT_RE.finditer(expr):
        tok = m.group(0)
        start = m.start()
        if start > 0 and expr[start - 1] == "'":
            continue  # base char of a sized literal, e.g. 1'b1
        if tok in _NON_SIGNAL_TOKENS:
            continue
        if tok[0].isdigit():
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _loc(obj: dict[str, Any] | None, fallback_file: str) -> SourceLocation:
    """Project a canonical SourceLocation (col/end_* extra fields) onto ours."""
    if not obj:
        return SourceLocation(file=fallback_file, line=1)
    return SourceLocation(
        file=obj.get("file", fallback_file),
        line=int(obj.get("line", 1)),
    )


def _looks_canonical(doc: dict[str, Any]) -> bool:
    """Heuristic: the canonical manifest has ``modules`` and no flat ``symbols``."""
    return "modules" in doc and "symbols" not in doc


def from_canonical_manifest(
    doc: dict[str, Any],
    *,
    qualify: bool = True,
) -> RTLIntentManifest:
    """Project a canonical RTL Intent Manifest document onto ``RTLIntentManifest``.

    Args:
        doc: the parsed canonical manifest JSON (per
            ``rtl-intent-ingestor/schemas/manifest.schema.json``).
        qualify: when True (default), symbol names are qualified as
            ``<top>.<name>`` to match hierarchical trace names. When the trace
            uses bare signal names, pass ``qualify=False``.

    The result is deterministic: symbols and drivers are sorted, and each symbol
    references only symbols that exist in this design, so the engine's cone
    traversal terminates.
    """
    modules: list[dict[str, Any]] = doc.get("modules", []) or []
    top = doc.get("top")
    if not top and modules:
        top = modules[0].get("name")
    design_top = top or "top"

    # Choose the module to project. Prefer the declared top; otherwise the first.
    module: dict[str, Any] | None = None
    for m in modules:
        if m.get("name") == top:
            module = m
            break
    if module is None and modules:
        module = modules[0]
    if module is None:
        return RTLIntentManifest(design_top=design_top, symbols={})

    prefix = f"{design_top}." if qualify else ""
    mod_file = (module.get("location") or {}).get("file", f"{design_top}.sv")

    def qname(name: str) -> str:
        return f"{prefix}{name}"

    # -- pass 1: declare every symbol (ports, nets, registers) --------------
    symbols: dict[str, RTLSymbol] = {}
    # Map bare -> qualified so driver reconstruction can resolve local names.
    bare_to_q: dict[str, str] = {}

    def declare(name: str, kind: str, loc: dict[str, Any] | None, **flags: bool) -> None:
        q = qname(name)
        bare_to_q[name] = q
        if q in symbols:
            # Keep the first declaration but upgrade flags (e.g. is_reset).
            for k, v in flags.items():
                if v:
                    setattr(symbols[q], k, True)
            return
        symbols[q] = RTLSymbol(
            name=q,
            kind=kind,
            width=1,
            location=_loc(loc, mod_file),
            drivers=[],
            **flags,
        )

    clock_names = {c.get("signal") for c in module.get("clock_candidates", []) or []}
    reset_names = {r.get("signal") for r in module.get("reset_candidates", []) or []}

    for port in module.get("ports", []) or []:
        name = port.get("name")
        if not name:
            continue
        direction = port.get("direction", "input")
        kind = "port_in" if direction == "input" else "port_out"
        declare(
            name,
            kind,
            port.get("location"),
            is_clock=name in clock_names,
            is_reset=name in reset_names,
        )

    for net in module.get("nets", []) or []:
        name = net.get("name")
        if not name:
            continue
        declare(name, net.get("net_kind", "wire"), net.get("location"))

    for reg in module.get("registers", []) or []:
        name = reg.get("name")
        if not name:
            continue
        # A register overrides an earlier net/port kind to 'reg'.
        q = qname(name)
        if q in symbols:
            symbols[q].kind = "reg"
        else:
            declare(name, "reg", reg.get("location"))

    # -- pass 2: reconstruct driver (fan-in) edges --------------------------
    def add_drivers(target_bare: str, rhs_signals: list[str]) -> None:
        tq = bare_to_q.get(target_bare)
        if tq is None:
            # Target not declared (e.g. hierarchical/foreign): declare as wire so
            # the cone traversal still has a node and citation.
            declare(target_bare, "wire", None)
            tq = bare_to_q[target_bare]
        sym = symbols[tq]
        for src in rhs_signals:
            if src == target_bare:
                continue  # self-loop (registered feedback) adds nothing to cone
            sq = bare_to_q.get(src)
            if sq is None:
                continue  # references something not in this module; skip safely
            if sq not in sym.drivers:
                sym.drivers.append(sq)

    for ca in module.get("continuous_assigns", []) or []:
        lhs = ca.get("lhs")
        if not lhs:
            continue
        lhs_name = _extract_signals(lhs)
        target = lhs_name[0] if lhs_name else lhs
        add_drivers(target, _extract_signals(ca.get("rhs", "")))

    for proc in module.get("procedures", []) or []:
        cond = list(proc.get("condition_signals", []) or [])
        assigns = proc.get("assignments", []) or []
        if assigns:
            for a in assigns:
                lhs = a.get("lhs")
                if not lhs:
                    continue
                lhs_name = _extract_signals(lhs)
                target = lhs_name[0] if lhs_name else lhs
                rhs_sigs = _extract_signals(a.get("rhs", "")) + cond
                add_drivers(target, rhs_sigs)
        else:
            # Only block-level targets are known; attribute the condition signals.
            for target in proc.get("assignment_targets", []) or []:
                add_drivers(target, cond)

    # Deterministic ordering of drivers.
    for sym in symbols.values():
        sym.drivers = sorted(set(sym.drivers))

    return RTLIntentManifest(design_top=design_top, symbols=symbols)


def load_manifest(
    source: dict[str, Any] | str | Path,
    *,
    qualify: bool = True,
) -> RTLIntentManifest:
    """Load a manifest, auto-detecting native vs canonical schema.

    Keeps full back-compat with the repo's native ``RTLIntentManifest`` fixture
    (``examples/toy_counter/manifest.json``) while transparently accepting a
    canonical ``rtl-intent-ingestor`` manifest.
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        text = p.read_text() if p.exists() else str(source)
        doc = json.loads(text)
    else:
        doc = source

    if _looks_canonical(doc):
        return from_canonical_manifest(doc, qualify=qualify)
    return RTLIntentManifest.model_validate(doc)
