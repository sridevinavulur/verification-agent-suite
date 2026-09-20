"""Signal ownership classification grounded in RTL Intent Manifest directions."""

from __future__ import annotations

from ..models import Ownership, SignalClassification
from ..parsers.manifest import ManifestView


def classify_signals(
    signals: set[str], manifest: ManifestView
) -> list[SignalClassification]:
    """Classify each signal into an :class:`Ownership` bucket.

    Boundary port direction (from the manifest) takes precedence over the
    internal-state set, so a registered output is classified as ``DUT_OUTPUT``.
    """
    out: list[SignalClassification] = []
    for sig in sorted(signals):
        out.append(_classify_one(sig, manifest))
    return out


def _classify_one(sig: str, manifest: ManifestView) -> SignalClassification:
    if not manifest.loaded:
        return SignalClassification(
            signal=sig,
            ownership=Ownership.UNKNOWN,
            rationale="No RTL Intent Manifest provided; ownership cannot be grounded.",
        )
    direction = manifest.direction_of(sig)
    if direction == "input":
        return SignalClassification(
            signal=sig,
            ownership=Ownership.ENVIRONMENT_INPUT,
            rationale=f"'{sig}' is an input port of top module '{manifest.top}'.",
        )
    if direction == "output":
        return SignalClassification(
            signal=sig,
            ownership=Ownership.DUT_OUTPUT,
            rationale=f"'{sig}' is an output port of top module '{manifest.top}'.",
        )
    if direction == "inout":
        return SignalClassification(
            signal=sig,
            ownership=Ownership.DUT_OUTPUT,
            rationale=(
                f"'{sig}' is an inout port of top '{manifest.top}'; treated as "
                "DUT-driven for constraint-hygiene purposes."
            ),
        )
    if sig in manifest.internal_signals:
        return SignalClassification(
            signal=sig,
            ownership=Ownership.INTERNAL_STATE,
            rationale=f"'{sig}' is a register/internal net inside the DUT (not a boundary port).",
        )
    return SignalClassification(
        signal=sig,
        ownership=Ownership.UNKNOWN,
        rationale=f"'{sig}' not found among manifest ports or internal signals.",
    )
