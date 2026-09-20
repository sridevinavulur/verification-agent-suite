"""Typed data contracts for the Testbench Recovery Agent.

All output the tool emits is one of these Pydantic v2 models. The central
distinction encoded here is *provenance*:

* ``EXTRACTED``  - the command/fact was read verbatim (or trivially normalized)
  from a repository file and carries a file+line ``Evidence`` pointer.
* ``HYPOTHESIS`` - the command/fact was *inferred* by a heuristic and is NOT
  directly present in the repo. It must never be presented as authoritative.

This mirrors the safety rule from the pack: clearly distinguish commands
extracted from repository evidence from hypotheses, and do not invent tool
availability or command-line options.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Provenance(StrEnum):
    """Where a candidate/fact came from."""

    EXTRACTED = "extracted"
    HYPOTHESIS = "hypothesis"


class SourceKind(StrEnum):
    """The kind of repository artifact an extractor consumed."""

    MAKEFILE = "makefile"
    SHELL = "shell"
    CI_WORKFLOW = "ci_workflow"
    FILELIST = "filelist"
    README = "readme"


class TargetPhase(StrEnum):
    """Classification of what a recovered command is for."""

    BUILD = "build"
    ELABORATE = "elaborate"
    RUN = "run"
    ANALYZE = "analyze"
    CLEAN = "clean"
    SETUP = "setup"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class Evidence(BaseModel):
    """A pointer back to the exact source location that justified a claim."""

    model_config = ConfigDict(frozen=True)

    file: str = Field(..., description="Repo-relative path of the source file.")
    line: int = Field(..., ge=1, description="1-based line number.")
    snippet: str = Field(..., description="Verbatim (stripped) source line.")
    source_kind: SourceKind


class ToolRequirement(BaseModel):
    """A simulator / formal / build tool the repo appears to need."""

    name: str = Field(..., description="Canonical tool name, e.g. 'verilator'.")
    category: str = Field(
        ...,
        description="One of: simulator, formal, synthesis, build, lint, python, other.",
    )
    provenance: Provenance
    evidence: list[Evidence] = Field(default_factory=list)
    note: str | None = None


class Dependency(BaseModel):
    """A software dependency (package, language runtime, apt/pip install, etc.)."""

    name: str
    manager: str = Field(
        ..., description="e.g. pip, apt, brew, submodule, env, unknown."
    )
    version: str | None = None
    provenance: Provenance
    evidence: list[Evidence] = Field(default_factory=list)


class CandidateCommand(BaseModel):
    """A build/elaborate/run/analyze command recovered from the repo."""

    command: str = Field(..., description="The shell command as recovered.")
    phase: TargetPhase
    provenance: Provenance
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Empty only for HYPOTHESIS commands.",
    )
    target_name: str | None = Field(
        None, description="Makefile target / CI job / script name if known."
    )
    tools: list[str] = Field(
        default_factory=list, description="Tool names referenced by this command."
    )
    working_dir: str | None = Field(
        None, description="Directory the command should run from, if known."
    )
    rationale: str | None = Field(
        None, description="Why a HYPOTHESIS was proposed (empty for EXTRACTED)."
    )
    destructive: bool = Field(
        False, description="True if the command deletes/overwrites (e.g. 'make clean')."
    )


class TargetSourceMap(BaseModel):
    """Maps a named target to the source/filelist files it consumes."""

    target_name: str
    sources: list[str] = Field(default_factory=list)
    filelists: list[str] = Field(default_factory=list)
    provenance: Provenance
    evidence: list[Evidence] = Field(default_factory=list)


class SetupIssue(BaseModel):
    """An unresolved problem that would block reproducing a target."""

    severity: Severity
    message: str
    evidence: list[Evidence] = Field(default_factory=list)


class ReproManifest(BaseModel):
    """Reproducibility manifest: what was inspected and with what tool."""

    tool_name: str = "testbench-recovery-agent"
    tool_version: str
    repo_root: str = Field(
        ...,
        description="Inspected repo root, recorded relative to itself ('.') so "
        "reports are portable and never leak the machine's absolute path.",
    )
    git_sha: str | None = Field(
        None, description="git HEAD SHA if the checkout is a git repo, else None."
    )
    inspected_files: list[str] = Field(default_factory=list)
    file_hashes: dict[str, str] = Field(
        default_factory=dict, description="sha256 of each inspected file."
    )
    command: str = Field(..., description="The CLI invocation that produced this run.")


class RecoveryReport(BaseModel):
    """Top-level output contract for a single repository inspection."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    repro: ReproManifest
    candidate_commands: list[CandidateCommand] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    tool_requirements: list[ToolRequirement] = Field(default_factory=list)
    target_source_map: list[TargetSourceMap] = Field(default_factory=list)
    setup_issues: list[SetupIssue] = Field(default_factory=list)
    recommended_smoke_test: CandidateCommand | None = Field(
        None,
        description="The minimal, non-destructive command most likely to work.",
    )
