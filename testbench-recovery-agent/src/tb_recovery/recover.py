"""Repository walker + recovery orchestrator.

Discovers relevant artifacts in a checkout, routes each to the correct static
extractor, merges results, synthesizes a small number of clearly-labeled
HYPOTHESIS commands where evidence is thin, and selects a recommended,
non-destructive smoke-test command.

No file in the repo is executed. Directories that are typically noise
(``.git``, ``node_modules``, ``__pycache__``, build output) are skipped.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from . import __version__
from .extractors import (
    extract_ci_workflow,
    extract_filelist,
    extract_makefile,
    extract_readme,
    extract_shell,
)
from .extractors.base import ExtractResult
from .models import (
    CandidateCommand,
    Dependency,
    Provenance,
    RecoveryReport,
    ReproManifest,
    SetupIssue,
    Severity,
    SourceKind,
    TargetPhase,
    TargetSourceMap,
    ToolRequirement,
)

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".egg-info",
}
_MAKEFILE_NAMES = {"makefile", "gnumakefile"}
_MAX_BYTES = 512 * 1024  # skip absurdly large files defensively


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS or part.endswith(".egg-info")
               for part in path.parts):
            continue
        yield path


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _classify_file(path: Path) -> SourceKind | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in _MAKEFILE_NAMES or suffix == ".mk" or name.endswith(".mk"):
        return SourceKind.MAKEFILE
    if suffix == ".sh":
        return SourceKind.SHELL
    if suffix == ".f":
        return SourceKind.FILELIST
    # CI workflows: only under .github/workflows
    parts = [p.lower() for p in path.parts]
    if "workflows" in parts and ".github" in parts and suffix in (".yml", ".yaml"):
        return SourceKind.CI_WORKFLOW
    if suffix in (".md", ".rst", ".txt") and "readme" in name:
        return SourceKind.README
    if name in ("building.md", "install.md", "usage.md"):
        return SourceKind.README
    return None


def _portable_command(command: str, *roots: Path) -> str:
    """Strip machine-specific repo paths out of the recorded CLI command.

    The ``command`` field records the invocation that produced a report (e.g.
    ``tb-recover inspect /home/alice/checkout``). Persisting the caller's
    absolute path would leak a username/home path and break byte-stable golden
    comparisons across checkouts, so every spelling of the repo root - the path
    exactly as passed and its symlink-resolved form - is rewritten to the
    portable relative form (``.``). Longest match first so a resolved path that
    contains the raw one is handled before its substring.
    """
    forms = {str(r) for r in roots}
    for form in sorted(forms, key=len, reverse=True):
        if form and form in command:
            command = command.replace(form, ".")
    return command


def _git_sha(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        sha = out.stdout.strip()
        return sha or None
    except (OSError, subprocess.SubprocessError):
        return None


def recover(root: Path, command: str) -> RecoveryReport:
    raw_root = root
    root = root.resolve()
    merged = ExtractResult()
    inspected: list[str] = []
    hashes: dict[str, str] = {}

    for path in _iter_files(root):
        kind = _classify_file(path)
        if kind is None:
            continue
        try:
            if path.stat().st_size > _MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = _rel(path, root)
        inspected.append(rel)
        hashes[rel] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()

        if kind is SourceKind.MAKEFILE:
            merged.extend(extract_makefile(rel, text))
        elif kind is SourceKind.SHELL:
            merged.extend(extract_shell(rel, text))
        elif kind is SourceKind.CI_WORKFLOW:
            merged.extend(extract_ci_workflow(rel, text))
        elif kind is SourceKind.FILELIST:
            merged.extend(extract_filelist(rel, text))
        elif kind is SourceKind.README:
            merged.extend(extract_readme(rel, text))

    commands = _dedup_commands(merged.commands)
    dependencies = _dedup_deps(merged.dependencies)
    tools = _dedup_tools(merged.tools)
    tsmap = _merge_target_source(merged.target_source_map)
    issues = list(merged.issues)

    # Synthesize HYPOTHESIS commands + additional setup issues.
    hyp, hyp_issues = _hypotheses(commands, dependencies, tools, root)
    commands.extend(hyp)
    issues.extend(hyp_issues)
    issues.extend(_unresolved_source_issues(tsmap, root))

    smoke = _select_smoke_test(commands)

    repro = ReproManifest(
        tool_version=__version__,
        # Portable-by-construction: the repo root is recorded relative to itself
        # ('.') rather than as the machine's absolute path, so reports never leak
        # a home/username path and stay byte-identical across checkouts. All
        # other paths in the report (inspected_files, file_hashes keys, evidence
        # file pointers) are already repo-relative.
        repo_root=".",
        git_sha=_git_sha(root),
        inspected_files=inspected,
        file_hashes=hashes,
        command=_portable_command(command, root, raw_root),
    )

    return RecoveryReport(
        repro=repro,
        candidate_commands=commands,
        dependencies=dependencies,
        tool_requirements=tools,
        target_source_map=tsmap,
        setup_issues=_dedup_issues(issues),
        recommended_smoke_test=smoke,
    )


# ---------------------------------------------------------------------------
# Merging / dedup helpers (kept deterministic + stably ordered).
# ---------------------------------------------------------------------------

def _cmd_sort_key(c: CandidateCommand):
    prov_rank = 0 if c.provenance is Provenance.EXTRACTED else 1
    ev = c.evidence[0] if c.evidence else None
    return (prov_rank, ev.file if ev else "~", ev.line if ev else 0, c.command)


def _dedup_commands(cmds: list[CandidateCommand]) -> list[CandidateCommand]:
    by_key: dict[tuple[str, str], CandidateCommand] = {}
    for c in cmds:
        key = (c.command, c.provenance.value)
        if key in by_key:
            # Merge evidence from duplicate occurrences.
            existing = by_key[key]
            merged_ev = list(existing.evidence)
            for ev in c.evidence:
                if ev not in merged_ev:
                    merged_ev.append(ev)
            existing.evidence = merged_ev
        else:
            by_key[key] = c.model_copy(deep=True)
    return sorted(by_key.values(), key=_cmd_sort_key)


def _dedup_deps(deps: list[Dependency]) -> list[Dependency]:
    by_key: dict[tuple[str, str], Dependency] = {}
    for d in deps:
        key = (d.name, d.manager)
        if key in by_key:
            for ev in d.evidence:
                if ev not in by_key[key].evidence:
                    by_key[key].evidence.append(ev)
        else:
            by_key[key] = d.model_copy(deep=True)
    return sorted(by_key.values(), key=lambda d: (d.manager, d.name))


def _dedup_tools(tools: list[ToolRequirement]) -> list[ToolRequirement]:
    by_key: dict[str, ToolRequirement] = {}
    for t in tools:
        if t.name in by_key:
            for ev in t.evidence:
                if ev not in by_key[t.name].evidence:
                    by_key[t.name].evidence.append(ev)
        else:
            by_key[t.name] = t.model_copy(deep=True)
    for t in by_key.values():
        t.evidence.sort(key=lambda e: (e.file, e.line))
    return sorted(by_key.values(), key=lambda t: (t.category, t.name))


def _merge_target_source(maps: list[TargetSourceMap]) -> list[TargetSourceMap]:
    by_name: dict[str, TargetSourceMap] = {}
    for m in maps:
        if m.target_name in by_name:
            ex = by_name[m.target_name]
            ex.sources = sorted(set(ex.sources) | set(m.sources))
            ex.filelists = sorted(set(ex.filelists) | set(m.filelists))
            for ev in m.evidence:
                if ev not in ex.evidence:
                    ex.evidence.append(ev)
        else:
            by_name[m.target_name] = m.model_copy(deep=True)
    return sorted(by_name.values(), key=lambda m: m.target_name)


def _dedup_issues(issues: list[SetupIssue]) -> list[SetupIssue]:
    seen: set[tuple[str, str]] = set()
    out: list[SetupIssue] = []
    order = {Severity.BLOCKER: 0, Severity.WARNING: 1, Severity.INFO: 2}
    for i in sorted(issues, key=lambda x: (order[x.severity], x.message)):
        key = (i.severity.value, i.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


# ---------------------------------------------------------------------------
# Hypothesis synthesis (clearly labeled, evidence-free by construction).
# ---------------------------------------------------------------------------

def _hypotheses(
    commands: list[CandidateCommand],
    deps: list[Dependency],
    tools: list[ToolRequirement],
    root: Path,
) -> tuple[list[CandidateCommand], list[SetupIssue]]:
    hyp: list[CandidateCommand] = []
    issues: list[SetupIssue] = []
    have_phases = {c.phase for c in commands}

    # If a Makefile exists but we never saw a plain 'make' default target run,
    # propose 'make' as a hypothesis (target unknown).
    has_make_target = any(
        c.target_name and c.command.startswith("make ") for c in commands
    )
    makefile_present = any(
        e.source_kind is SourceKind.MAKEFILE
        for c in commands for e in c.evidence
    )
    if makefile_present and not has_make_target:
        hyp.append(
            CandidateCommand(
                command="make",
                phase=TargetPhase.BUILD,
                provenance=Provenance.HYPOTHESIS,
                evidence=[],
                target_name=None,
                tools=["make"],
                rationale=(
                    "A Makefile is present but no default target's recipe was "
                    "recovered; 'make' with the default goal is a common entry "
                    "point. Verify the default target before relying on this."
                ),
                destructive=False,
            )
        )

    # If a simulator is required but no RUN command was recovered, note it.
    sim_tools = [t for t in tools if t.category == "simulator"]
    if sim_tools and TargetPhase.RUN not in have_phases:
        issues.append(
            SetupIssue(
                severity=Severity.WARNING,
                message=(
                    "Simulator tool(s) "
                    f"{', '.join(sorted(t.name for t in sim_tools))} appear "
                    "required, but no explicit run command was recovered from "
                    "repository evidence."
                ),
                evidence=[],
            )
        )

    # If a python project file exists but no install command recovered, hypothesize.
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        has_pip = any(d.manager == "pip" for d in deps)
        if not has_pip:
            hyp.append(
                CandidateCommand(
                    command="pip install -e .",
                    phase=TargetPhase.SETUP,
                    provenance=Provenance.HYPOTHESIS,
                    evidence=[],
                    target_name=None,
                    tools=["python"],
                    rationale=(
                        "A pyproject.toml/setup.py is present; an editable install "
                        "is the conventional setup step. Not found verbatim in repo."
                    ),
                    destructive=False,
                )
            )

    return hyp, issues


def _unresolved_source_issues(
    maps: list[TargetSourceMap], root: Path
) -> list[SetupIssue]:
    """Flag mapped source files / filelists that do not exist on disk."""
    issues: list[SetupIssue] = []
    for m in maps:
        for src in list(m.sources) + list(m.filelists):
            if src.startswith(("$", "+", "-")) or "*" in src:
                continue
            # Resolve relative to repo root and to the filelist's own dir.
            candidates = [root / src]
            ev0 = m.evidence[0] if m.evidence else None
            if ev0:
                candidates.append((root / ev0.file).parent / src)
            if not any(c.exists() for c in candidates):
                issues.append(
                    SetupIssue(
                        severity=Severity.WARNING,
                        message=(
                            f"Target '{m.target_name}' references source '{src}' "
                            "which was not found on disk (relative to repo root)."
                        ),
                        evidence=list(m.evidence),
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Smoke-test selection.
# ---------------------------------------------------------------------------

_PHASE_PREF = {
    TargetPhase.RUN: 0,
    TargetPhase.BUILD: 1,
    TargetPhase.ELABORATE: 2,
    TargetPhase.ANALYZE: 3,
    TargetPhase.SETUP: 4,
    TargetPhase.UNKNOWN: 5,
    TargetPhase.CLEAN: 9,
}


def _source_pref(cmd: CandidateCommand) -> int:
    """Prefer CI/Makefile evidence over shell/readme (docs drift)."""
    if not cmd.evidence:
        return 5
    kinds = {e.source_kind for e in cmd.evidence}
    if SourceKind.CI_WORKFLOW in kinds:
        return 0
    if SourceKind.MAKEFILE in kinds:
        return 1
    if SourceKind.SHELL in kinds:
        return 2
    return 3


def _select_smoke_test(commands: list[CandidateCommand]) -> CandidateCommand | None:
    """Pick the minimal, non-destructive, evidence-backed command most likely
    to exercise the flow. Prefers a RUN/BUILD 'make <target>' from CI/Makefile."""
    viable = [
        c for c in commands
        if c.provenance is Provenance.EXTRACTED
        and not c.destructive
        and c.phase not in (TargetPhase.CLEAN, TargetPhase.SETUP)
    ]
    if not viable:
        return None

    def key(c: CandidateCommand):
        is_make = 0 if c.command.startswith("make ") else 1
        return (_PHASE_PREF.get(c.phase, 9), _source_pref(c), is_make, c.command)

    return sorted(viable, key=key)[0].model_copy(deep=True)
