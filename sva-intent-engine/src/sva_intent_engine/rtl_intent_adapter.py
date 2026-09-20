"""Adapter: canonical RTL Intent Manifest -> grounding-engine manifest model.

``rtl-intent-ingestor`` is the canonical *producer* of the RTL Intent Manifest
(schema ``rtl-intent`` / ``schema_version`` 0.1.0). This engine's own
:class:`~sva_intent_engine.models.RTLManifest` is a minimal fixture shape. This
module maps the canonical manifest down to that fixture so the grounding engine
can consume the real producer output rather than a bespoke hand-written shape.

Only deterministic structural facts are carried across (ports, nets, registers,
clock/reset candidates, source locations). Nothing here calls an LLM. Reset
polarity emitted by the producer is a heuristic; it is propagated into
``signal_type`` verbatim so the grounding engine's existing polarity logic can
use it, and it stays a candidate, not a proven fact.

The canonical schema is read-only truth; see
``rtl-intent-ingestor/schemas/manifest.schema.json`` and
``rtl-intent-ingestor/src/rtl_intent/models.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RTLManifest, RTLSymbol

# Canonical NetKind -> engine symbol ``kind``. Ports override this with "port".
_NETKIND_KIND = {"wire": "wire", "reg": "reg", "logic": "wire"}


def _width_from_range(rng: dict[str, Any] | None) -> int | None:
    """Best-effort bit width from a canonical ``Range`` ({msb, lsb}).

    The producer keeps ``msb``/``lsb`` as verbatim source text and does not
    evaluate parameter arithmetic, so a width is only returned when both bounds
    are plain integers; otherwise ``None`` (unknown) -- never a guess.
    """
    if not rng:
        return 1
    try:
        msb = int(str(rng["msb"]).strip())
        lsb = int(str(rng["lsb"]).strip())
    except (KeyError, ValueError):
        return None
    return abs(msb - lsb) + 1


def _loc(item: dict[str, Any]) -> tuple[str | None, int | None]:
    loc = item.get("location")
    if not isinstance(loc, dict):
        return None, None
    return loc.get("file"), loc.get("line")


def _is_canonical(data: dict[str, Any]) -> bool:
    """True if ``data`` looks like a canonical ingestor manifest.

    The canonical manifest is keyed by ``modules``/``provenance``/``parser``; the
    engine fixture uses ``design_top``/``symbols``.
    """
    return "modules" in data and "design_top" not in data


def from_rtl_intent_manifest(
    data: dict[str, Any],
    *,
    module: str | None = None,
) -> RTLManifest:
    """Map a canonical RTL Intent Manifest dict to :class:`RTLManifest`.

    :param data: parsed canonical manifest JSON (dict).
    :param module: which module to project; defaults to ``top`` then the first
        module in the manifest.
    """
    modules: list[dict[str, Any]] = data.get("modules", [])
    if not modules:
        raise ValueError("canonical manifest has no modules to project")

    want = module or data.get("top")
    mod: dict[str, Any] | None = None
    if want is not None:
        mod = next((m for m in modules if m.get("name") == want), None)
    if mod is None:
        mod = modules[0]

    reset_cands = mod.get("reset_candidates", [])
    clock_names = [c["signal"] for c in mod.get("clock_candidates", [])]
    reset_names = [r["signal"] for r in reset_cands]
    clock_set = set(clock_names)
    reset_set = set(reset_names)
    # Producer's heuristic reset polarity -> engine ``signal_type`` (candidate).
    reset_polarity: dict[str, str] = {
        r["signal"]: r.get("polarity", "unknown")
        for r in reset_cands
        if r.get("polarity") in ("active_high", "active_low")
    }

    symbols: list[RTLSymbol] = []
    seen: set[str] = set()

    def _kind_for(name: str, default: str) -> str:
        # Clock/reset candidacy is surfaced as the symbol kind so downstream
        # readers can see it; grounding also uses the candidate lists directly.
        if name in clock_set:
            return "clock"
        if name in reset_set:
            return "reset"
        return default

    def _sid(prefix: str, name: str) -> str:
        return f"{prefix}_{name}"

    # Ports first (they carry direction).
    for port in mod.get("ports", []):
        name = port["name"]
        if name in seen:
            continue
        seen.add(name)
        file, line = _loc(port)
        kind = _kind_for(name, "port")
        symbols.append(
            RTLSymbol(
                symbol_id=_sid("s", name),
                name=name,
                kind=kind,
                direction=port.get("direction"),
                width=_width_from_range(port.get("range")),
                signal_type=reset_polarity.get(name),
                file=file,
                line=line,
            )
        )

    # Internal nets (wire/reg/logic that are not ports).
    for net in mod.get("nets", []):
        name = net["name"]
        if name in seen:
            continue
        seen.add(name)
        file, line = _loc(net)
        default_kind = _NETKIND_KIND.get(net.get("net_kind", ""), "net")
        symbols.append(
            RTLSymbol(
                symbol_id=_sid("s", name),
                name=name,
                kind=_kind_for(name, default_kind),
                width=_width_from_range(net.get("range")),
                signal_type=reset_polarity.get(name),
                file=file,
                line=line,
            )
        )

    # Registers not already captured as a net/port (structural state elements).
    for reg in mod.get("registers", []):
        name = reg["name"]
        if name in seen:
            continue
        seen.add(name)
        file, line = _loc(reg)
        symbols.append(
            RTLSymbol(
                symbol_id=_sid("s", name),
                name=name,
                kind=_kind_for(name, "reg"),
                signal_type=reset_polarity.get(name),
                file=file,
                line=line,
            )
        )

    return RTLManifest(
        design_top=mod.get("name", want or ""),
        symbols=symbols,
        clock_candidates=clock_names,
        reset_candidates=reset_names,
    )


def load_manifest(
    path: str | Path,
    *,
    manifest_format: str = "auto",
    module: str | None = None,
) -> RTLManifest:
    """Load an RTL Intent Manifest from disk into :class:`RTLManifest`.

    ``manifest_format``:
      * ``"auto"``      -- detect canonical vs. engine fixture (default).
      * ``"canonical"`` -- force the canonical ingestor adapter.
      * ``"fixture"``   -- force the engine's own fixture format.
    """
    text = Path(path).read_text()
    if manifest_format == "fixture":
        return RTLManifest.model_validate_json(text)

    data = json.loads(text)
    if manifest_format == "canonical" or (manifest_format == "auto" and _is_canonical(data)):
        return from_rtl_intent_manifest(data, module=module)
    if manifest_format == "auto":
        return RTLManifest.model_validate(data)
    raise ValueError(f"unknown manifest_format: {manifest_format!r}")
