# Release / Public-Disclosure Checklist

Run before pushing to a public repository.

## Secret / data scan
- [ ] No API keys, tokens, passwords, or certificates.
- [ ] No employer/customer/partner names or confidential project names.
- [ ] No proprietary RTL, waveforms, logs, or tool scripts.
- [ ] No internal hostnames, usernames, emails, or absolute filesystem paths.
- [ ] Examples are public toy fixtures only (see `examples/`).

## Claims audit
- [ ] README claims match the code and tests (see `EVIDENCE.md`).
- [ ] No use of prohibited vocabulary ("verified assertion", "formal signoff",
      "autonomous proof") — this tool emits *candidates* only.
- [ ] `CandidateProperty.status` remains `candidate_compiled_offline`.

## Reproducibility
- [ ] Fresh venv: `pip install -e ".[dev]"` succeeds.
- [ ] `ruff check .` is clean.
- [ ] `pytest` is green.
- [ ] `sva-intent demo` runs and emits 5 candidate properties.
- [ ] Goldens regenerated if intended: `python scripts/gen_golden.py`.

## Licensing
- [ ] `LICENSE` present (MIT placeholder).
- [ ] Dependencies license-compatible (pydantic, typer, PyYAML, pytest, ruff).

## Sign-off
- [ ] Human reviewer initials + date: ____________
