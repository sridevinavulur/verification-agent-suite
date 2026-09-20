# Contributing to verification-agent-suite

Thanks for your interest. This is a monorepo of **independent, single-purpose** verification
tools. Each top-level directory is its own installable Python package with its own tests, docs,
and CI job. Please keep contributions scoped to one package per pull request where possible.

Read [`BUILD_STANDARD.md`](BUILD_STANDARD.md) first — it defines the engineering, safety, and
evidence rules every package follows. This guide is the short version.

## Ground rules (non-negotiable)

These come from the suite's design philosophy and apply to every package:

- **Deterministic-first.** An LLM may *propose* (hypotheses, mappings, candidate assertions,
  configurations). Deterministic code must *validate* syntax, symbols, constraints, and results.
  Keep the two layers clearly separated.
- **No unearned conclusions.** A candidate assertion is never "verified" because it compiles.
  A `TIMEOUT` / `ERROR` / `INCONCLUSIVE` result is never a `PASS`. Heuristics are labeled as
  heuristic.
- **Human-in-the-loop.** No tool modifies RTL, assumptions, proof scope, budgets, or signoff
  conclusions without a documented human-approval gate.
- **Public, non-proprietary content only.** Never commit employer/customer names, internal tool
  or project names, proprietary RTL, credentials, absolute local paths, usernames, or emails.
  Examples must use public toy designs.
- **Offline by default.** LLM usage goes through a deterministic mock adapter so tests and CI
  run without network access or API keys.

## Development setup

Each package targets **Python 3.11+**. Work inside the package you're changing:

```bash
cd <package-name>
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you open a PR

Run these in the package directory and make sure they pass:

```bash
ruff check .        # lint/format
pytest -q           # tests (must be green)
mypy src            # where the package ships type hints
```

- Add or update tests for any behavior change. Prefer **golden-output tests** for anything that
  emits structured reports, and update goldens only via the package's regenerate script.
- Update the package's `README.md` and `EVIDENCE.md` if you change behavior or claims. Every
  claim in `EVIDENCE.md` must map to a source location, a test, and a reproduce command.
- Keep new dependencies minimal and justify them. Prefer the standard library.

## Commit & PR conventions

- Small, focused commits with clear messages (imperative mood: "add X", "fix Y").
- One package per PR when practical; note cross-package interface changes explicitly (e.g.
  changes to the canonical RTL Intent Manifest produced by `rtl-intent-ingestor`, which several
  tools consume).
- CI runs `ruff` + `pytest` for every package on Python 3.11 and 3.12; PRs must be green.

## Reporting issues

Open an issue describing the package, the input, the expected vs. actual behavior, and a minimal
public reproducer. Never paste proprietary RTL, logs, or paths into an issue.

## License

By contributing, you agree that your contributions are licensed under the repository's
[MIT License](LICENSE).
