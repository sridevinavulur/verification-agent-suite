"""Loader for the canonical RTL Intent Manifest.

The Manifest is produced by the sibling ``rtl-intent-ingestor`` tool and is the
*only* trusted source of RTL symbols for grounding. We deliberately model only
the subset of the schema this agent needs (symbols and clock/reset candidates)
rather than re-deriving the whole schema, but we validate the parts we read.

We do NOT parse RTL here. If a symbol is not in the Manifest, it is unresolved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ManifestSymbol:
    """A flattened RTL symbol usable for grounding."""

    module: str
    name: str
    kind: str  # port | net | register | parameter
    detail: str = ""


@dataclass
class ManifestView:
    """A queryable, flattened view over a canonical Manifest."""

    top: str | None
    symbols: list[ManifestSymbol] = field(default_factory=list)
    clock_candidates: list[str] = field(default_factory=list)
    reset_candidates: list[str] = field(default_factory=list)
    module_names: list[str] = field(default_factory=list)

    def find(self, name: str) -> list[ManifestSymbol]:
        """Exact (case-insensitive) matches for ``name``."""
        low = name.lower()
        return [s for s in self.symbols if s.name.lower() == low]

    def find_alias(self, name: str) -> list[ManifestSymbol]:
        """Substring / suffix alias matches (heuristic, lower confidence).

        Matches when the manifest symbol *ends with* the requested name or the
        requested name ends with the symbol, guarded to length >= 3 to avoid
        matching trivially short tokens.
        """
        low = name.lower()
        if len(low) < 3:
            return []
        out: list[ManifestSymbol] = []
        for s in self.symbols:
            sl = s.name.lower()
            if sl == low:
                continue
            if sl.endswith("_" + low) or low.endswith("_" + sl) or low in sl.split("_"):
                out.append(s)
        return out


def load_manifest(path: str | Path) -> ManifestView:
    """Load and flatten a canonical Manifest JSON file into a ManifestView."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return build_view(raw)


def build_view(raw: dict) -> ManifestView:
    """Flatten a parsed Manifest dict into a :class:`ManifestView`.

    Tolerant of missing optional keys (the schema marks most of them optional).
    """
    symbols: list[ManifestSymbol] = []
    clocks: list[str] = []
    resets: list[str] = []
    module_names: list[str] = []

    for mod in raw.get("modules", []):
        mname = mod.get("name", "")
        module_names.append(mname)
        for port in mod.get("ports", []):
            symbols.append(
                ManifestSymbol(module=mname, name=port["name"], kind="port",
                               detail=port.get("direction", ""))
            )
        for net in mod.get("nets", []):
            symbols.append(
                ManifestSymbol(module=mname, name=net["name"], kind="net",
                               detail=net.get("net_kind", ""))
            )
        for reg in mod.get("registers", []):
            symbols.append(
                ManifestSymbol(module=mname, name=reg["name"], kind="register")
            )
        for param in mod.get("parameters", []):
            symbols.append(
                ManifestSymbol(module=mname, name=param["name"], kind="parameter")
            )
        for cc in mod.get("clock_candidates", []):
            sig = cc.get("signal")
            if sig and sig not in clocks:
                clocks.append(sig)
        for rc in mod.get("reset_candidates", []):
            sig = rc.get("signal")
            if sig and sig not in resets:
                resets.append(sig)

    return ManifestView(
        top=raw.get("top"),
        symbols=symbols,
        clock_candidates=clocks,
        reset_candidates=resets,
        module_names=module_names,
    )
