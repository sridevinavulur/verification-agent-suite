# Release checklist — verification-agent-factory

- [ ] `ruff check .` clean
- [ ] `pytest` green
- [ ] `pip install -e .` succeeds in a fresh venv
- [ ] `vaf audit-public-release .` reports no blocking findings
- [ ] README claims match implemented + tested behaviour
- [ ] Only public, non-proprietary examples committed
- [ ] LICENSE present
