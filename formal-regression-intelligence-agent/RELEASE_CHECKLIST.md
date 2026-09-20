# Release Checklist

Run before pushing to a public remote.

## Secrets / data hygiene
- [ ] No API keys, tokens, passwords, or private URLs (`git grep -iE "api_key|secret|token|password"`).
- [ ] No employer / customer / partner / internal project names.
- [ ] No proprietary RTL, real telemetry, waveform data, or internal tool names.
- [ ] No internal hostnames, usernames, emails, or absolute filesystem paths in committed files.
- [ ] Bundled ledger is the synthetic public toy only (`examples/sample_ledger.jsonl`).

## Correctness / reproducibility
- [ ] Fresh venv: `pip install -e ".[dev]"` succeeds.
- [ ] `ruff check .` is clean.
- [ ] `mypy src/formal_regression_intelligence` is clean.
- [ ] `pytest` is green.
- [ ] `python scripts/make_fixtures.py && git diff --exit-code examples/` shows no drift.
- [ ] `python scripts/export_schemas.py && git diff --exit-code schemas/` shows no drift.

## Claims
- [ ] README claims match code + tests (see `EVIDENCE.md`).
- [ ] All findings labelled HEURISTIC; no root-cause or signoff claims.
- [ ] Non-claims section present and accurate.

## Licensing
- [ ] `LICENSE` present (MIT placeholder).
- [ ] Dependencies (pydantic, typer) are compatibly licensed.
