"""Adapter: canonical RTL Intent Manifest -> reviewer fixture model.

The ``rtl-intent-ingestor`` tool is the *canonical producer* of the RTL Intent
Manifest (schema ``rtl-intent`` / ``schema_version`` 0.1.0). Its manifest is far
richer than the constrained :class:`~assertion_review.models.RtlIntentManifest`
fixture this reviewer needs. This module maps the canonical manifest down to the
subset the reviewer uses (signal name, role, width, reset polarity, plus
clock/reset candidate lists), so the two tools actually compose.

Only deterministic structural facts are carried across. Nothing here calls an
LLM. Heuristic fields from the producer (clock/reset *candidates* and their
inferred polarity) are propagated verbatim and stay labelled as candidates.

The canonical schema is read-only truth; see
``rtl-intent-ingestor/schemas/manifest.schema.json`` and
``rtl-intent-ingestor/src/rtl_intent/models.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ManifestSignal, ResetPolarity, RtlIntentManifest, SignalRole

# Direction string (canonical PortDirection) -> reviewer SignalRole.
_DIRECTION_ROLE = {
    "input": SignalRole.INPUT,
    "output": SignalRole.OUTPUT,
    "inout": SignalRole.INOUT,
}

# Canonical ResetPolarity string -> reviewer ResetPolarity.
_POLARITY_MAP = {
    "active_high": ResetPolarity.ACTIVE_HIGH,
    "active_low": ResetPolarity.ACTIVE_LOW,
    "unknown": ResetPolarity.UNKNOWN,
}


def _width_from_range(rng: dict[str, Any] | None) -> int:
    """Best-effort bit width from a canonical ``Range`` ({msb, lsb}).

    The canonical parser keeps ``msb``/``lsb`` as verbatim source text (it does
    not evaluate parameter arithmetic), so a width is only computed when both
    bounds are plain integers. Otherwise the reviewer default of 1 is used --
    we never *guess* a width from an unevaluated expression.
    """
    if not rng:
        return 1
    try:
        msb = int(str(rng["msb"]).strip())
        lsb = int(str(rng["lsb"]).strip())
    except (KeyError, ValueError):
        return 1
    return abs(msb - lsb) + 1


def _is_canonical(data: dict[str, Any]) -> bool:
    """True if ``data`` looks like a canonical ingestor manifest.

    The canonical manifest is keyed by ``modules``/``provenance``/``parser`` and
    never has the reviewer fixture's flat ``signals`` list.
    """
    return "modules" in data and "signals" not in data


def from_rtl_intent_manifest(
    data: dict[str, Any],
    *,
    module: str | None = None,
) -> RtlIntentManifest:
    """Map a canonical RTL Intent Manifest dict to :class:`RtlIntentManifest`.

    :param data: the parsed canonical manifest JSON (dict).
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

    clock_names = [c["signal"] for c in mod.get("clock_candidates", [])]
    reset_cands = mod.get("reset_candidates", [])
    reset_names = [r["signal"] for r in reset_cands]
    # Reset polarity is a heuristic emitted by the producer; carry it verbatim.
    reset_polarity: dict[str, ResetPolarity] = {
        r["signal"]: _POLARITY_MAP.get(r.get("polarity", "unknown"), ResetPolarity.UNKNOWN)
        for r in reset_cands
    }
    clock_set = set(clock_names)
    reset_set = set(reset_names)

    signals: list[ManifestSignal] = []
    seen: set[str] = set()

    def _role_for(name: str, default: SignalRole) -> SignalRole:
        # Clock/reset candidacy takes precedence over raw port direction so the
        # reviewer's name-semantics/polarity checks see the right role.
        if name in clock_set:
            return SignalRole.CLOCK
        if name in reset_set:
            return SignalRole.RESET
        return default

    # Ports first (they carry direction).
    for port in mod.get("ports", []):
        name = port["name"]
        if name in seen:
            continue
        seen.add(name)
        base = _DIRECTION_ROLE.get(port.get("direction", ""), SignalRole.UNKNOWN)
        signals.append(
            ManifestSignal(
                name=name,
                role=_role_for(name, base),
                width=_width_from_range(port.get("range")),
                reset_polarity=reset_polarity.get(name, ResetPolarity.UNKNOWN),
            )
        )

    # Internal nets (wire/reg/logic that are not ports).
    for net in mod.get("nets", []):
        name = net["name"]
        if name in seen:
            continue
        seen.add(name)
        signals.append(
            ManifestSignal(
                name=name,
                role=_role_for(name, SignalRole.INTERNAL),
                width=_width_from_range(net.get("range")),
                reset_polarity=reset_polarity.get(name, ResetPolarity.UNKNOWN),
            )
        )

    return RtlIntentManifest(
        top=mod.get("name", want or ""),
        signals=signals,
        clock_candidates=clock_names,
        reset_candidates=reset_names,
    )


def load_manifest(
    path: str | Path,
    *,
    manifest_format: str = "auto",
    module: str | None = None,
) -> RtlIntentManifest:
    """Load an RTL Intent Manifest from disk into :class:`RtlIntentManifest`.

    ``manifest_format``:
      * ``"auto"``      -- detect canonical vs. reviewer fixture (default).
      * ``"canonical"`` -- force the canonical ingestor adapter.
      * ``"fixture"``   -- force the reviewer's own fixture format.

    Both formats are accepted so the reviewer stays backward-compatible with its
    hand-written fixtures while also ingesting the canonical producer output.
    """
    text = Path(path).read_text()
    if manifest_format == "fixture":
        return RtlIntentManifest.model_validate_json(text)

    data = json.loads(text)
    if manifest_format == "canonical" or (manifest_format == "auto" and _is_canonical(data)):
        return from_rtl_intent_manifest(data, module=module)
    if manifest_format == "auto":
        return RtlIntentManifest.model_validate(data)
    raise ValueError(f"unknown manifest_format: {manifest_format!r}")
