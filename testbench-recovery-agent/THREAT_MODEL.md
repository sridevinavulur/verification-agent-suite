# Threat Model

Scope: a static tool that reads repository files and emits a structured recovery
report. It does not execute anything and does not modify the repository.

## 1. Hallucination / fabricated commands

**Risk:** presenting a command that is not actually in the repo as if it were.
**Mitigations:**
- Every `EXTRACTED` command must carry `Evidence(file, line, snippet)`; the
  extractors only emit such a command from a line they actually read.
- Inferred commands are a separate `HYPOTHESIS` provenance with **empty
  evidence** and a required `rationale`. They are visually and structurally
  distinct in both JSON and Markdown.
- The tool never fabricates command-line flags: recovered commands are copied
  verbatim (after `$(VAR)` expansion using assignments found in the same file).

## 2. Unsafe assumptions about tool availability

**Risk:** claiming a simulator/formal tool is installed or usable.
**Mitigations:**
- `ToolRequirement` means "this executable is *referenced*", not "installed".
- No environment probing, no `which`, no version claims are made.
- A simulator referenced with no recovered run command produces a WARNING
  setup issue rather than a confident run recommendation.

## 3. Accidental execution / destructive actions

**Risk:** running a recovered command, especially a destructive one.
**Mitigations:**
- The tool executes nothing. `sandbox.DisabledExecutor.run` raises
  `NotImplementedError` by design.
- Commands matching a destructive pattern (`rm -rf`, `make clean`, `git clean`,
  `mkfs`, `dd if=`, redirects to `/dev/`, recursive chmod/chown) are flagged
  `destructive=True` and are excluded from smoke-test selection.

## 4. Reproducibility risks

**Risk:** non-deterministic or non-portable output; unverifiable claims.
**Mitigations:**
- Deterministic merging/sorting; a golden test asserts byte-stable output.
- `ReproManifest` records tool version, git SHA, inspected files, and per-file
  SHA-256 so a report can be tied to an exact checkout.
- Reports are portable *by construction*: the repo root is recorded relative to
  itself (`.`), all other paths are repo-relative, and any absolute repo path is
  stripped from the recorded `command`. No home/username/absolute path is ever
  emitted, so reports are byte-identical across checkouts and safe to commit.
- The golden serializer additionally normalizes the remaining checkout-specific
  fields (git SHA, file hashes) to keep goldens portable while remaining valid
  reports.

## 5. Data leakage / public-safety

**Risk:** committing proprietary paths, tool names, or credentials.
**Mitigations:**
- The bundled fixture is synthetic and public. Only public, well-known tool
  names appear in the knowledge table.
- The tool reads local files but never transmits anything; there is no network
  access and no LLM call.
- Users are warned (README, `.gitignore`) not to commit reports generated from
  non-public repositories.

## 6. Parser-scope overclaiming

**Risk:** implying full Make/CI semantics.
**Mitigations:**
- Constrained parsers with limitations documented in the README and surfaced at
  runtime as INFO issues (e.g. unfollowed `include`, fully-templated CI steps).
- The tool reports *candidate* commands; it makes no correctness guarantee.
