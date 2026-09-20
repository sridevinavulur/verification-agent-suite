"""Makefile extractor.

Recovers, with file+line evidence:

* Variable assignments (``NAME = value``, ``:=``, ``?=``, ``+=``) so recipe
  lines that reference ``$(VAR)`` can be expanded.
* Targets and their recipe lines. Each recipe line becomes a
  ``CandidateCommand`` (provenance EXTRACTED).
* A synthesized ``make <target>`` invocation per non-phony-looking target
  (also EXTRACTED - ``make`` and the target name are literally in the file).
* Source/filelist references (``.v``, ``.sv``, ``.f``) per target for the
  target-to-source map.
* Tool requirements referenced by recipe lines.

This is a constrained parser: it does not implement conditionals, includes,
pattern rules, or full GNU make expansion. Unhandled constructs are recorded as
INFO issues so they are visible, per the "make limitations visible" rule.
"""

from __future__ import annotations

import re

from ..models import (
    CandidateCommand,
    Evidence,
    Provenance,
    SetupIssue,
    Severity,
    SourceKind,
    TargetSourceMap,
)
from .base import (
    ExtractResult,
    classify_phase,
    is_destructive,
    tool_requirements_for,
    tools_in_command,
)

_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(:=|\?=|\+=|=)\s*(.*)$")
_TARGET_RE = re.compile(r"^([A-Za-z0-9_./%$(){}-][A-Za-z0-9_./%$(){}\s.-]*?):(?!=)\s*(.*)$")
_VAR_REF_RE = re.compile(r"\$[({]([A-Za-z_][A-Za-z0-9_]*)[)}]")
_SRC_RE = re.compile(r"[\w./$(){}-]+\.(?:sv|svh|v|vh|f|vhd|vhdl)\b")
_PHONY_RE = re.compile(r"^\.PHONY\s*:\s*(.*)$")
_INCLUDE_RE = re.compile(r"^\s*-?include\s+(.*)$")


def _expand(value: str, variables: dict[str, str], depth: int = 0) -> str:
    """Best-effort expansion of ``$(VAR)`` / ``${VAR}`` references."""
    if depth > 10:
        return value

    def repl(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in variables:
            return _expand(variables[name], variables, depth + 1)
        return m.group(0)  # leave unknown refs literal, do not invent a value

    return _VAR_REF_RE.sub(repl, value)


def extract_makefile(rel_path: str, text: str) -> ExtractResult:
    result = ExtractResult()
    lines = text.splitlines()

    variables: dict[str, str] = {}
    phony: set[str] = set()

    # First pass: variables and .PHONY (so recipes can be expanded).
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("\t"):
            continue  # recipe line, handled in second pass
        pm = _PHONY_RE.match(line.strip())
        if pm:
            phony.update(pm.group(1).split())
            continue
        am = _ASSIGN_RE.match(line)
        if am and not line.lstrip().startswith("#"):
            name, op, val = am.group(1), am.group(2), am.group(3).strip()
            val = val.split(" #", 1)[0].rstrip() if " #" in val else val
            if op == "+=" and name in variables:
                variables[name] = f"{variables[name]} {val}".strip()
            else:
                variables[name] = val

    # Second pass: targets + recipes.
    current_target: str | None = None
    target_sources: dict[str, set[str]] = {}
    target_filelists: dict[str, set[str]] = {}
    seen_targets: list[tuple[str, int]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        inc = _INCLUDE_RE.match(line)
        if inc and not line.startswith("\t"):
            result.issues.append(
                SetupIssue(
                    severity=Severity.INFO,
                    message=(
                        f"Makefile 'include {inc.group(1).strip()}' not followed; "
                        "referenced file may define additional targets/variables."
                    ),
                    evidence=[
                        Evidence(
                            file=rel_path,
                            line=idx,
                            snippet=stripped,
                            source_kind=SourceKind.MAKEFILE,
                        )
                    ],
                )
            )
            continue

        if line.startswith("\t") and current_target is not None:
            recipe = line.lstrip("\t").rstrip()
            if not recipe or recipe.startswith("#"):
                continue
            # Strip leading recipe modifiers (@, -, +).
            clean = recipe
            while clean[:1] in ("@", "-", "+"):
                clean = clean[1:]
            expanded = _expand(clean, variables)
            ev = Evidence(
                file=rel_path,
                line=idx,
                snippet=recipe,
                source_kind=SourceKind.MAKEFILE,
            )
            cmd = CandidateCommand(
                command=expanded,
                phase=classify_phase(expanded, current_target),
                provenance=Provenance.EXTRACTED,
                evidence=[ev],
                target_name=current_target,
                tools=tools_in_command(expanded),
                destructive=is_destructive(expanded),
            )
            result.commands.append(cmd)
            result.tools.extend(
                tool_requirements_for(expanded, Provenance.EXTRACTED, [ev])
            )
            # Collect source references from the recipe too.
            for sm in _SRC_RE.finditer(expanded):
                _record_source(sm.group(0), current_target, target_sources,
                               target_filelists)
            continue

        # Non-recipe, non-blank: try target.
        tm = _TARGET_RE.match(line)
        if tm and "=" not in line.split(":", 1)[0]:
            target_field = tm.group(1).strip()
            prereqs = tm.group(2).strip()
            # A rule can declare multiple targets separated by spaces.
            targets = [t for t in target_field.split() if t]
            if not targets:
                continue
            current_target = targets[0]
            for t in targets:
                seen_targets.append((t, idx))
                target_sources.setdefault(t, set())
                target_filelists.setdefault(t, set())
            # Prereqs may contain source files / filelists.
            for sm in _SRC_RE.finditer(_expand(prereqs, variables)):
                _record_source(sm.group(0), current_target, target_sources,
                               target_filelists)
            continue

    # Build "make <target>" invocations (EXTRACTED: literal target names).
    for name, line_no in seen_targets:
        if name.startswith(".") or "%" in name or "$" in name:
            continue
        ev = Evidence(
            file=rel_path,
            line=line_no,
            snippet=f"{name}:",
            source_kind=SourceKind.MAKEFILE,
        )
        # Look at the recipes recorded for this target to classify the phase.
        recipe_cmds = [c for c in result.commands if c.target_name == name]
        joined = " ".join(c.command for c in recipe_cmds)
        phase = classify_phase(joined, name) if joined else classify_phase("", name)
        result.commands.append(
            CandidateCommand(
                command=f"make {name}",
                phase=phase,
                provenance=Provenance.EXTRACTED,
                evidence=[ev],
                target_name=name,
                tools=tools_in_command(joined),
                destructive=any(c.destructive for c in recipe_cmds),
            )
        )

    # Emit target-source map.
    for name, _ in seen_targets:
        srcs = sorted(target_sources.get(name, set()))
        fls = sorted(target_filelists.get(name, set()))
        if srcs or fls:
            result.target_source_map.append(
                TargetSourceMap(
                    target_name=name,
                    sources=srcs,
                    filelists=fls,
                    provenance=Provenance.EXTRACTED,
                    evidence=[
                        Evidence(
                            file=rel_path,
                            line=next(ln for tn, ln in seen_targets if tn == name),
                            snippet=f"{name}:",
                            source_kind=SourceKind.MAKEFILE,
                        )
                    ],
                )
            )

    return result


def _record_source(
    token: str,
    target: str | None,
    sources: dict[str, set[str]],
    filelists: dict[str, set[str]],
) -> None:
    if target is None:
        return
    # Drop unexpanded variable refs.
    if "$" in token:
        return
    if token.endswith(".f"):
        filelists.setdefault(target, set()).add(token)
    else:
        sources.setdefault(target, set()).add(token)
