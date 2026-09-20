"""Render a human-readable Markdown summary of a :class:`Manifest`.

The Markdown mirrors the JSON manifest but is easier to review. It always
includes the hierarchy graph, per-module inventory, clock/reset candidates with
confidence, procedure summaries, and the explicit list of unresolved constructs
and parser limitations.
"""

from __future__ import annotations

from .models import Manifest, Module


def _fmt_range(rng) -> str:
    if rng is None:
        return ""
    if rng.msb == rng.lsb:
        return f"[{rng.msb}]"
    return f"[{rng.msb}:{rng.lsb}]"


def _loc(loc) -> str:
    if loc is None:
        return "-"
    return f"{loc.file}:{loc.line}:{loc.col}"


def render_markdown(manifest: Manifest) -> str:
    lines: list[str] = []
    a = lines.append

    a("# RTL Intent Manifest")
    a("")
    a(f"- **Tool**: {manifest.provenance.tool} v{manifest.provenance.tool_version}")
    a(f"- **Schema version**: {manifest.schema_version}")
    a(f"- **Parser adapter**: {manifest.parser.adapter} "
      f"v{manifest.parser.adapter_version}")
    a(f"- **Top module**: {manifest.top or '(unresolved / ambiguous)'}")
    a(f"- **Modules**: {len(manifest.modules)}")
    a(f"- **Input files**: {', '.join(manifest.provenance.input_files) or '-'}")
    a("")

    _render_hierarchy(lines, manifest)

    a("## Module inventory")
    a("")
    a("| Module | Ports | Params | Nets | Registers | assign | always_ff | always_comb |")
    a("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for m in manifest.modules:
        s = m.procedure_summary
        a(f"| `{m.name}` | {len(m.ports)} | {len(m.parameters)} | {len(m.nets)} "
          f"| {len(m.registers)} | {s.continuous_assigns} | {s.always_ff} "
          f"| {s.always_comb} |")
    a("")

    for m in manifest.modules:
        _render_module(lines, m)

    _render_unresolved(lines, manifest)
    _render_limitations(lines, manifest)

    return "\n".join(lines) + "\n"


def _render_hierarchy(lines: list[str], manifest: Manifest) -> None:
    a = lines.append
    a("## Hierarchy graph")
    a("")
    if not manifest.hierarchy:
        a("_No instantiations found (flat / leaf design)._")
        a("")
        return
    a("| Parent | Instance | Child module | Defined in inputs |")
    a("| --- | --- | --- | --- |")
    for e in manifest.hierarchy:
        a(f"| `{e.parent_module}` | `{e.instance_name}` | `{e.child_module}` "
          f"| {'yes' if e.child_defined else 'NO (external/black-box)'} |")
    a("")


def _render_module(lines: list[str], m: Module) -> None:
    a = lines.append
    a(f"## Module `{m.name}`")
    a("")
    a(f"_Declared at {_loc(m.location)}._")
    a("")

    if m.parameters:
        a("### Parameters")
        a("")
        a("| Name | Default | Kind | Location |")
        a("| --- | --- | --- | --- |")
        for param in m.parameters:
            kind = "localparam" if param.is_localparam else "parameter"
            a(f"| `{param.name}` | `{param.default or ''}` | {kind} "
              f"| {_loc(param.location)} |")
        a("")

    if m.ports:
        a("### Ports")
        a("")
        a("| Name | Direction | Type | Width | Location |")
        a("| --- | --- | --- | --- | --- |")
        for port in m.ports:
            nk = port.net_kind.value if port.net_kind else ""
            a(f"| `{port.name}` | {port.direction.value} | {nk} | "
              f"`{_fmt_range(port.range)}` | {_loc(port.location)} |")
        a("")

    if m.nets:
        a("### Nets")
        a("")
        a("| Name | Kind | Width | Unpacked | Location |")
        a("| --- | --- | --- | --- | --- |")
        for net in m.nets:
            unpacked = _fmt_range(net.unpacked_range) if net.is_memory else ""
            a(f"| `{net.name}` | {net.net_kind.value} | "
              f"`{_fmt_range(net.range)}` | `{unpacked}` | {_loc(net.location)} |")
        a("")

    if m.registers:
        a("### Registers (nonblocking targets under always_ff)")
        a("")
        a("| Name | Driven in proc # | Location |")
        a("| --- | ---: | --- |")
        for r in m.registers:
            a(f"| `{r.name}` | {r.driven_in_procedure_index} | {_loc(r.location)} |")
        a("")

    if m.continuous_assigns:
        a("### Continuous assignments")
        a("")
        a("| LHS | RHS | Location |")
        a("| --- | --- | --- |")
        for c in m.continuous_assigns:
            a(f"| `{c.lhs}` | `{c.rhs}` | {_loc(c.location)} |")
        a("")

    if m.procedures:
        a("### Procedures")
        a("")
        a("| # | Kind | Sensitivity | Targets | Location |")
        a("| ---: | --- | --- | --- | --- |")
        for proc in m.procedures:
            sens = ", ".join(
                f"{s.edge + ' ' if s.edge else ''}{s.signal}"
                for s in proc.sensitivity
            )
            if proc.is_star_sensitivity:
                sens = "*"
            targets = ", ".join(proc.assignment_targets)
            a(f"| {proc.index} | {proc.kind.value} | {sens or '-'} "
              f"| `{targets}` | {_loc(proc.location)} |")
        a("")

    if m.instances:
        a("### Instances")
        a("")
        a("| Instance | Module | Connections | Location |")
        a("| --- | --- | ---: | --- |")
        for inst in m.instances:
            a(f"| `{inst.name}` | `{inst.module}` | {len(inst.connections)} "
              f"| {_loc(inst.location)} |")
        a("")

    _render_clock_reset(lines, m)


def _render_clock_reset(lines: list[str], m: Module) -> None:
    a = lines.append
    a("### Clock & reset candidates (heuristic)")
    a("")
    if not m.clock_candidates and not m.reset_candidates:
        a("_No clock or reset candidates detected._")
        a("")
        return
    if m.clock_candidates:
        a("**Clocks**")
        a("")
        a("| Signal | Confidence | Rationale |")
        a("| --- | ---: | --- |")
        for c in m.clock_candidates:
            a(f"| `{c.signal}` | {c.confidence:.3f} | {'; '.join(c.rationale)} |")
        a("")
    if m.reset_candidates:
        a("**Resets**")
        a("")
        a("| Signal | Confidence | Polarity | Sync | Rationale |")
        a("| --- | ---: | --- | --- | --- |")
        for r in m.reset_candidates:
            a(f"| `{r.signal}` | {r.confidence:.3f} | {r.polarity.value} "
              f"| {r.sync.value} | {'; '.join(r.rationale)} |")
        a("")


def _render_unresolved(lines: list[str], manifest: Manifest) -> None:
    a = lines.append
    a("## Unresolved constructs")
    a("")
    if not manifest.unresolved:
        a("_None. Every construct in the input was within the supported subset._")
        a("")
        return
    a("These constructs were detected but not fully modeled in v0.1. They are "
      "surfaced here rather than silently dropped.")
    a("")
    a("| Kind | Detail | Location |")
    a("| --- | --- | --- |")
    for u in manifest.unresolved:
        a(f"| {u.kind} | {u.detail} | {_loc(u.location)} |")
    a("")


def _render_limitations(lines: list[str], manifest: Manifest) -> None:
    a = lines.append
    a("## Parser limitations (v0.1 subset)")
    a("")
    a("Supported constructs:")
    a("")
    for s in manifest.parser.supported_constructs:
        a(f"- {s}")
    a("")
    a("**Not** supported (not full SystemVerilog semantics):")
    a("")
    for s in manifest.parser.unsupported_constructs:
        a(f"- {s}")
    a("")
    a("> Clock/reset candidates and confidence scores are **heuristic** name- "
      "and structure-based signals, not a formal determination of clocking or "
      "reset intent.")
    a("")
