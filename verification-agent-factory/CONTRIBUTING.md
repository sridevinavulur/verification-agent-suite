# Contributing — verification-agent-factory

1. `python3.11 -m venv .venv && source .venv/bin/activate`
2. `pip install -e ".[dev]"`
3. `ruff check .`
4. `pytest`

## Rules
- LLM proposes; deterministic tools validate. Keep the layers separate.
- Never classify TIMEOUT / ERROR / UNKNOWN as PASS.
- No secrets, proprietary names, or internal paths in commits.
- Add a new category template as templates/<name>/ plus a branch in scaffold.scaffold.
- Small, independently testable commits.
