# Testbench Recovery Agent

Statically inspect a public RTL/verification repository checkout and reconstruct
a reproducible map of **how to build, elaborate, run, and analyze** its
verification targets - with **file+line evidence** for every recovered command.

This is a **static recovery tool**, not a build system and not an executor. It
reads Makefiles, shell build scripts, GitHub Actions CI workflows, `.f` file
lists, and READMEs; it never runs any command it finds. (Spec: prompt-pack
section 6.11 "Testbench Recovery Agent"; engineering rules: `BUILD_STANDARD.md`.)

## What it does (v0.1, static inspection only)

Given a repo path, `tb-recover` emits a typed `RecoveryReport` containing:

- **Candidate build/run commands with evidence** - each tagged `EXTRACTED`
  (present verbatim in a repo file, with `file:line`) or `HYPOTHESIS`
  (a heuristic inference, evidence-free, with an explicit rationale).
- **Dependency inventory** - `pip`/`apt` installs recovered from scripts/CI.
- **Simulator / formal-tool requirements** - e.g. Verilator, Icarus, Questa,
  VCS, Xcelium, SymbiYosys, Yosys, JasperGold - detected from referenced
  executables, never assumed to be installed.
- **Target-to-source mapping** - Makefile targets and `.f` file lists resolved
  to the source files they consume.
- **Unresolved setup issues** - e.g. a target that references a missing source
  file, a simulator required but no run command found, a fully-templated CI step.
- **Reproducibility manifest** - tool version, repo root, git SHA (if any),
  inspected file list, and per-file SHA-256 hashes. Output is portable: the repo
  root is recorded relative to itself (`.`) and no absolute/home path is emitted,
  so reports are byte-identical across checkouts (see `examples/expected/`).
- **Recommended minimal smoke-test command** - the least-destructive,
  evidence-backed command most likely to exercise the flow (CI/Makefile evidence
  preferred over docs, which drift).

## Install

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Inspect the bundled toy fixture repo:

```sh
tb-recover inspect examples/toy_repo
tb-recover summary examples/toy_repo         # Markdown
tb-recover smoke   examples/toy_repo         # just the smoke-test command
tb-recover schema                            # JSON Schema of the contract
```

Example (`smoke`) output on the fixture:

```
# EXTRACTED from .github/workflows/ci.yml:20
make run
```

## Provenance: EXTRACTED vs HYPOTHESIS

Every candidate command carries a `provenance` field. This is the core safety
property of the tool:

| provenance   | meaning                                                        |
|--------------|----------------------------------------------------------------|
| `extracted`  | The command is literally in a repo file. `evidence` is non-empty (`file`, `line`, `snippet`). |
| `hypothesis` | The tool *inferred* a likely command. `evidence` is empty; `rationale` explains the guess. |

The tool never fabricates command-line options and never claims a tool is
installed - it only reports that a tool *appears required* based on referenced
executables.

## Scope and limitations (non-claims)

- **Static only.** v0.1 executes nothing. The sandboxed execution adapter
  (`sandbox.py`) is a documented Phase-2 stub that raises `NotImplementedError`.
- **Constrained parsers.** The Makefile parser handles variables (`=`, `:=`,
  `?=`, `+=`), targets, and recipes with best-effort `$(VAR)` expansion. It does
  **not** implement conditionals, `include` following, pattern rules, or full
  GNU make semantics - unhandled constructs are surfaced as INFO issues.
- **CI:** GitHub Actions only; `run:` and `uses:` steps. `${{ }}` expressions
  are left literal; fully-templated steps are flagged, not guessed.
- **Not a correctness oracle.** A recovered command being present in the repo
  does **not** mean it currently works, that the tool is installed, or that the
  design builds. The tool reports evidence, not verdicts.
- **Public content only.** The fixture is synthetic. No proprietary RTL, tool
  names beyond public ones, credentials, or internal paths are included.

## Roadmap

- Phase 2: sandboxed, resource-limited, allow-listed optional execution adapter
  (interface already defined in `sandbox.py`).
- More build systems (CMake target graph, FuseSoC `.core`, Bender, DVSim).
- Non-GitHub CI (GitLab CI, Jenkinsfile).

## Repository docs

- `ARCHITECTURE.md` - components, data contracts, authority boundary
- `THREAT_MODEL.md` - hallucination, unsafe assumptions, reproducibility risks
- `EVIDENCE.md` - each claim tied to code, test, and reproduce command

## License

MIT (placeholder). See `LICENSE`.
