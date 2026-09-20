"""Consume the canonical RTL Intent Manifest for signal-ownership facts.

We deliberately do NOT depend on the rtl-intent-ingestor package (repos are
built independently). Instead we read the manifest JSON directly against the
canonical schema at
``rtl-intent-ingestor/schemas/manifest.schema.json`` and extract only the
fields this agent needs: the top module's port directions, plus register/net
names for internal-state detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ManifestView:
    """A minimal, typed projection of a manifest for ownership classification."""

    top: str | None = None
    # port name -> direction ("input"/"output"/"inout") for the DUT boundary.
    top_inputs: set[str] = field(default_factory=set)
    top_outputs: set[str] = field(default_factory=set)
    top_inouts: set[str] = field(default_factory=set)
    # register / internal net names across all modules (internal state).
    internal_signals: set[str] = field(default_factory=set)
    loaded: bool = False

    def direction_of(self, signal: str) -> str | None:
        if signal in self.top_inputs:
            return "input"
        if signal in self.top_outputs:
            return "output"
        if signal in self.top_inouts:
            return "inout"
        return None


def _pick_top(data: dict) -> dict | None:
    modules = data.get("modules", [])
    if not modules:
        return None
    top_name = data.get("top")
    if top_name:
        for m in modules:
            if m.get("name") == top_name:
                return m
    # Fall back to the single module, else the first.
    return modules[0]


def load_manifest(path: str | Path) -> ManifestView:
    data = json.loads(Path(path).read_text())
    return manifest_view_from_dict(data)


def manifest_view_from_dict(data: dict) -> ManifestView:
    view = ManifestView(loaded=True)
    view.top = data.get("top")
    top_mod = _pick_top(data)

    if top_mod is not None:
        view.top = view.top or top_mod.get("name")
        for port in top_mod.get("ports", []):
            name = port.get("name")
            direction = port.get("direction")
            if not name:
                continue
            if direction == "input":
                view.top_inputs.add(name)
            elif direction == "output":
                view.top_outputs.add(name)
            elif direction == "inout":
                view.top_inouts.add(name)

    # Internal state: registers + non-port nets across ALL modules. Ports of
    # the top are boundary; anything else that is a register/net is internal.
    all_port_names: set[str] = set()
    for mod in data.get("modules", []):
        for port in mod.get("ports", []):
            if port.get("name"):
                all_port_names.add(port["name"])
    for mod in data.get("modules", []):
        for reg in mod.get("registers", []):
            if reg.get("name"):
                view.internal_signals.add(reg["name"])
        for net in mod.get("nets", []):
            if net.get("name"):
                view.internal_signals.add(net["name"])
    # A top output that is also a register is still an output at the boundary;
    # boundary classification (output) takes precedence in the classifier.
    view.internal_signals -= all_port_names & (
        view.top_inputs | view.top_outputs | view.top_inouts
    )
    return view
