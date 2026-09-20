"""RTL symbol ingestion.

Two supported sources:

1. A simple JSON symbol export (this tool's own light-weight format).
2. The canonical *RTL Intent Manifest* produced by ``rtl-intent-ingestor``
   (``rtl-intent-ingestor/schemas/manifest.schema.json``). From that manifest we
   consume the deterministic, non-heuristic facts only: module ``registers``
   (nonblocking-assign targets under a clock edge) and ``nets``/``ports`` as
   candidate signals. We deliberately do **not** consume heuristic clock/reset
   candidates as authoritative for signal mapping.

Signal mapping downstream is grounded strictly against these symbols; nothing is
invented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RtlSymbol, RtlSymbolTable, SymbolKind


class RtlLoadError(ValueError):
    pass


def _looks_like_intent_manifest(data: dict[str, Any]) -> bool:
    return "modules" in data and "parser" in data


def _load_intent_manifest(data: dict[str, Any], source: str) -> RtlSymbolTable:
    symbols: list[RtlSymbol] = []
    modules = data.get("modules", [])
    top = data.get("top") or (modules[0]["name"] if modules else "")
    for mod in modules:
        mod_name = mod.get("name", "")
        for reg in mod.get("registers", []):
            symbols.append(
                RtlSymbol(name=reg["name"], kind=SymbolKind.REGISTER, module=mod_name)
            )
        for net in mod.get("nets", []):
            symbols.append(
                RtlSymbol(name=net["name"], kind=SymbolKind.SIGNAL, module=mod_name)
            )
        for port in mod.get("ports", []):
            symbols.append(
                RtlSymbol(name=port["name"], kind=SymbolKind.SIGNAL, module=mod_name)
            )
    # de-dup while preserving order
    seen: set[str] = set()
    uniq: list[RtlSymbol] = []
    for s in symbols:
        if s.name not in seen:
            seen.add(s.name)
            uniq.append(s)
    return RtlSymbolTable(module=top, symbols=uniq, source_file=source)


def _load_simple(data: dict[str, Any], source: str) -> RtlSymbolTable:
    raw = data.get("symbols")
    if raw is None:
        raise RtlLoadError("simple RTL symbol file must contain a 'symbols' list")
    if not isinstance(raw, list):
        raise RtlLoadError("'symbols' must be a list")
    symbols = [RtlSymbol.model_validate(s) for s in raw]
    return RtlSymbolTable(
        module=str(data.get("module", "")), symbols=symbols, source_file=source
    )


def load_rtl_symbols(path: str | Path) -> RtlSymbolTable:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RtlLoadError(f"invalid JSON in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise RtlLoadError("top-level RTL symbol JSON must be an object")
    if _looks_like_intent_manifest(data):
        return _load_intent_manifest(data, str(p))
    return _load_simple(data, str(p))
