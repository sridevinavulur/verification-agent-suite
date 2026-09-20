# Architecture

## Overview

The Testbench Recovery Agent is a **deterministic, static** repository inspector.
It walks a checkout, dispatches each recognized artifact to a dedicated
extractor, merges the results, adds a small number of clearly-labeled
hypotheses, and selects a recommended smoke-test command. Nothing is executed.

```
repo checkout
     |
     v
recover.recover()  --walks files, classifies by kind-->  extractors/*
     |                                                        |
     |   ExtractResult (commands, deps, tools, maps, issues)  |
     |<-------------------------------------------------------+
     v
merge + dedup (deterministic ordering)
     |
     +--> synthesize HYPOTHESIS commands (evidence-free, rationale required)
     +--> add setup issues (missing sources, sim-without-run, includes)
     +--> select recommended smoke test (non-destructive, evidence-backed)
     v
RecoveryReport  --serialize.py-->  JSON  /  report.py --> Markdown
```

## Components

| Module                         | Responsibility                                              |
|--------------------------------|------------------------------------------------------------|
| `models.py`                    | Pydantic v2 typed contracts (the whole I/O surface).       |
| `extractors/base.py`           | Shared: `ExtractResult`, tool table, phase classification, destructive-command detection. |
| `extractors/makefile.py`       | Variables, targets, recipes (`$(VAR)` expansion), `make <target>`, target->source. |
| `extractors/shell.py`          | Tool/dep-bearing lines from `*.sh` with simple var substitution. |
| `extractors/ci.py`             | GitHub Actions `run:`/`uses:` steps with real line numbers. |
| `extractors/filelist.py`       | `.f` argument files -> sources, incdirs, nested filelists.  |
| `extractors/readme.py`         | Fenced/prompted shell commands from documentation.         |
| `recover.py`                   | Walk, dispatch, merge, dedup, hypotheses, smoke-test pick. |
| `serialize.py`                 | Stable JSON (+ a portable golden variant).                 |
| `report.py`                    | Human-readable Markdown.                                    |
| `sandbox.py`                   | Phase-2 execution-adapter **interface + disabled stub**.   |
| `cli.py`                       | Typer CLI: `inspect`, `summary`, `smoke`, `schema`.        |

## Typed input/output contract

- **Input:** a filesystem path to a repository checkout (read-only).
- **Output:** a `RecoveryReport` (see `schemas/recovery_report.schema.json`).

Every `CandidateCommand`, `Dependency`, `ToolRequirement`, and `TargetSourceMap`
carries a `provenance` field (`extracted` | `hypothesis`). `extracted` items
carry `Evidence(file, line, snippet, source_kind)`; `hypothesis` items carry a
`rationale` and no evidence.

## Authority boundary

- The tool **reports evidence, not verdicts.** It never claims a command works,
  a tool is installed, or a design builds.
- It **never executes** any recovered command. The execution adapter is a
  documented stub that raises `NotImplementedError` (`sandbox.DisabledExecutor`).
- It **never invents** command-line options or tool availability. Tool
  requirements are inferred only from executables literally referenced in the
  repo, and are labeled by provenance.
- Hypotheses are always separable from extracted facts by the `provenance`
  field and are excluded from the JSON `evidence` arrays.

## Determinism

All merges sort by stable keys (provenance, file, line, text). Golden tests
assert byte-stable output. The reproducibility manifest records tool version,
repo root, git SHA (if present), the inspected file list, and per-file SHA-256.
The repo root is recorded *relative to itself* (`.`) and any absolute repo path
is stripped from the recorded `command`, so reports are portable and never leak
a home/username path - output is byte-identical no matter where the repo lives.
