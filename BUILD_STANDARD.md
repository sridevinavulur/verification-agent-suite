# Shared Build Standard — Verification Agent Repos

Every repository generated from `verification_ai_agent_prompt_pack.md` MUST follow this
standard. Read the relevant pack section for the agent-specific spec; this file defines the
cross-cutting engineering, safety, and evidence rules.

## Tech stack
- Python 3.11+
- Pydantic v2 for all typed data contracts (models validate, not just annotate)
- Typer for the CLI
- pytest for tests
- ruff for lint/format
- mypy where feasible
- Deterministic **mock LLM adapter** — no real network/API calls in tests or CI
- C++17 only where a pack section explicitly calls for a performance core (expose via a
  subprocess JSON interface or pybind11; keep a pure-Python fallback so tests run without a
  compiler)

## Quality bar (non-negotiable)
Build **meaningful, working tools — not skeletons.** Each repo will be committed to a shared
team git repo and used by real verification engineers. That means:
- Real, functioning logic: an actual (constrained) parser, a real COI/graph traversal, real
  mutation operators, real deterministic checks — code that produces correct output on the
  example inputs, not `pass`/`TODO`/`NotImplementedError` stubs.
- The CLI runs end-to-end on the bundled `examples/` and produces the documented output.
- Tests exercise the real behavior (golden outputs, edge cases), not trivial `assert True`.
- It is fine (and expected) to constrain SCOPE to a subset — but everything inside that
  subset must actually work. Narrow but real beats broad but fake.

## Scope discipline
Build ONLY the initial phase the pack section names ("implement X first", "Phase 0 only",
"v0.1", "start with the schemas and mocked executor"). Do not over-build. Stub later phases
behind clear TODOs and document them in the README roadmap.

## Required files in every repo
- `README.md` — scope, install, quickstart example, limitations, explicit **non-claims**
- `ARCHITECTURE.md` — components, typed input/output contracts, authority boundaries
- `THREAT_MODEL.md` — hallucination, unsafe assumptions, data leakage, reproducibility risks
- `EVIDENCE.md` — each claim tied to source file/function, test name, and reproduce command
- `pyproject.toml` — installable package, pinned-ish deps, ruff+pytest config
- `src/<package_name>/` with `models.py`, `cli.py`, and agent/core modules
- `tests/` — pytest suite that PASSES; include golden-output tests where the pack asks
- `examples/` — public toy inputs only
- `schemas/` — exported JSON Schema for the Pydantic contracts where relevant
- `.github/workflows/ci.yml` — lint + tests on push/PR, no secrets required
- `.gitignore`
- `LICENSE` — MIT placeholder

## Safety / integrity rules (from the pack)
- Never call a candidate assertion/property correct merely because it compiles.
- Never classify a TIMEOUT, ERROR, or INCONCLUSIVE result as a PASS.
- LLM proposes hypotheses/mappings/candidates; deterministic tools validate syntax,
  symbols, constraints, results. Keep the two layers clearly separated in code.
- No agent modifies RTL, assumptions, proof scope, budgets, or signoff conclusions without a
  documented human-approval gate.
- Public, non-proprietary content only. No secrets, employer/customer names, internal tool
  names, credentials, or proprietary paths.
- Record run provenance (git SHA placeholder, input hashes, tool/version, command, seed,
  runtime, memory, status) where the pack section asks for a run ledger.
- Label heuristic results as heuristic; do not present them as sound/formal.

## Result vocabulary (use consistently)
PASS/proven, FAIL, TIMEOUT, ERROR, UNKNOWN/INCONCLUSIVE, "property compiled" (syntax only).

## Definition of done
- `pip install -e .` (or equivalent) succeeds in a fresh venv.
- `ruff check .` is clean.
- `pytest` is green.
- README claims match what the code and tests actually do.
