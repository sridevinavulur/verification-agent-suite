# Release Checklist

Run before pushing to a shared/public repo.

## Secrets & proprietary content
- [ ] No API keys, tokens, passwords, certificates, private URLs.
- [ ] No employer/customer/partner or confidential project names.
- [ ] No proprietary RTL, waveforms, tool scripts, logs, or internal paths.
- [ ] Benchmark data is synthetic/public only; SHAs are placeholders. (See `BENCHMARKS.md`.)
- [ ] Generated artifacts excluded: `reports/ledger.db`, `reports/artifacts/` (in `.gitignore`).

## Claims match implementation
- [ ] README/EVIDENCE state the executor is MOCK and policies are heuristic.
- [ ] No claim of proof/signoff, solver optimization, or that mock numbers transfer to
      a real tool.
- [ ] Every EVIDENCE.md claim has a passing test and a reproduce command.

## Definition of done
- [ ] Fresh venv: `python3.11 -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -e ".[dev]"` succeeds.
- [ ] `ruff check .` is clean.
- [ ] `pytest` is green.
- [ ] `plan -> run -> summarize` runs end-to-end on the sample suite.
- [ ] `compare` and `ablate` produce reports under `reports/`.

## Licensing
- [ ] `LICENSE` present (MIT placeholder).
- [ ] Dependencies (`pydantic`, `typer`) are permissively licensed.
