"""GitHub Actions CI workflow extractor.

Parses ``.github/workflows/*.yml`` and recovers the ``run:`` steps of each job
as EXTRACTED candidate commands, with file+line evidence pointing at the exact
line inside the workflow. CI files are a high-signal source because they encode
a maintainer-verified build/run recipe.

We parse with PyYAML for structure, then re-scan the raw text to attach an
accurate line number to each recovered ``run`` block (PyYAML does not preserve
line numbers on plain scalars without a custom loader).

Constrained: we read ``jobs.<id>.steps[].run`` and ``.steps[].uses`` plus
``env``. We do not evaluate ``${{ }}`` expressions - they are left literal and,
if a command is entirely templated, flagged.
"""

from __future__ import annotations

import re

import yaml

from ..models import (
    CandidateCommand,
    Dependency,
    Evidence,
    Provenance,
    SetupIssue,
    Severity,
    SourceKind,
    ToolRequirement,
)
from .base import (
    ExtractResult,
    classify_phase,
    is_destructive,
    tool_requirements_for,
    tools_in_command,
)

_PIP_RE = re.compile(r"\bpip3?\s+install\s+(.+)$")
_APT_RE = re.compile(r"\bapt(?:-get)?\s+install\s+(?:-y\s+)?(.+)$")


def _find_line(raw_lines: list[str], needle: str, start: int = 0) -> int:
    """Return the 1-based line where ``needle`` first appears at/after ``start``."""
    needle = needle.strip()
    for i in range(start, len(raw_lines)):
        if needle and needle in raw_lines[i]:
            return i + 1
    return start + 1


def extract_ci_workflow(rel_path: str, text: str) -> ExtractResult:
    result = ExtractResult()
    raw_lines = text.splitlines()

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        result.issues.append(
            SetupIssue(
                severity=Severity.WARNING,
                message=f"CI workflow {rel_path} failed to parse as YAML: {exc}",
                evidence=[
                    Evidence(
                        file=rel_path, line=1, snippet=raw_lines[0] if raw_lines else "",
                        source_kind=SourceKind.CI_WORKFLOW,
                    )
                ],
            )
        )
        return result

    if not isinstance(doc, dict):
        return result

    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return result

    search_cursor = 0
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue

            uses = step.get("uses")
            if isinstance(uses, str):
                _handle_uses(uses, rel_path, raw_lines, result)

            run = step.get("run")
            if not isinstance(run, str):
                continue

            # Each physical line in a multi-line run block is a command.
            block_lines = [ln for ln in run.splitlines() if ln.strip()]
            for cmd_text in block_lines:
                cmd_text = cmd_text.strip()
                if cmd_text.startswith("#"):
                    continue
                line_no = _find_line(raw_lines, cmd_text, search_cursor)
                search_cursor = line_no  # advance so repeated lines map in order
                ev = Evidence(
                    file=rel_path,
                    line=line_no,
                    snippet=cmd_text,
                    source_kind=SourceKind.CI_WORKFLOW,
                )
                _collect_deps(cmd_text, ev, result)

                if _fully_templated(cmd_text):
                    result.issues.append(
                        SetupIssue(
                            severity=Severity.INFO,
                            message=(
                                f"CI step in job '{job_id}' is fully templated "
                                f"('{cmd_text}'); actual command depends on GitHub "
                                "context and cannot be recovered statically."
                            ),
                            evidence=[ev],
                        )
                    )
                    continue

                cmd = CandidateCommand(
                    command=cmd_text,
                    phase=classify_phase(cmd_text, str(job_id)),
                    provenance=Provenance.EXTRACTED,
                    evidence=[ev],
                    target_name=f"ci:{job_id}",
                    tools=tools_in_command(cmd_text),
                    destructive=is_destructive(cmd_text),
                )
                result.commands.append(cmd)
                result.tools.extend(
                    tool_requirements_for(cmd_text, Provenance.EXTRACTED, [ev])
                )

    return result


def _handle_uses(uses: str, rel_path: str, raw_lines: list[str], result: ExtractResult):
    line_no = _find_line(raw_lines, uses)
    ev = Evidence(
        file=rel_path, line=line_no, snippet=f"uses: {uses}",
        source_kind=SourceKind.CI_WORKFLOW,
    )
    action = uses.split("@", 1)[0]
    if action.endswith("setup-python") or "setup-python" in action:
        result.tools.append(
            ToolRequirement(
                name="python",
                category="python",
                provenance=Provenance.EXTRACTED,
                evidence=[ev],
                note="CI uses actions/setup-python.",
            )
        )


def _collect_deps(cmd: str, ev: Evidence, result: ExtractResult) -> None:
    pip = _PIP_RE.search(cmd)
    if pip:
        for pkg in _split_pkgs(pip.group(1)):
            result.dependencies.append(
                Dependency(name=pkg, manager="pip",
                           provenance=Provenance.EXTRACTED, evidence=[ev])
            )
    apt = _APT_RE.search(cmd)
    if apt:
        for pkg in _split_pkgs(apt.group(1)):
            result.dependencies.append(
                Dependency(name=pkg, manager="apt",
                           provenance=Provenance.EXTRACTED, evidence=[ev])
            )


def _split_pkgs(spec: str) -> list[str]:
    spec = spec.split("#", 1)[0].split("&&", 1)[0].split(";", 1)[0]
    out = []
    for tok in spec.split():
        if not tok or tok.startswith("-") or tok in ("&&", "\\"):
            continue
        out.append(tok)
    return out


def _fully_templated(cmd: str) -> bool:
    without = re.sub(r"\$\{\{.*?\}\}", "", cmd).strip()
    return without == "" or without in ("$", "${")
