# Security & Data Policy

- **Public content only.** No proprietary RTL, employer/customer names, internal
  tool names, credentials, or proprietary filesystem paths. `examples/` are toy,
  hand-written, public modules.
- **No network calls.** The analysis path is fully local and deterministic; no
  LLM or external service is contacted. No credentials are required.
- **Provenance stores hashes, not contents.** Input SHA-256 is recorded for
  reproducibility; source text is not embedded in outputs beyond the extracted
  signal names and locations already present in the (public) input.
- **Reporting.** For any security concern with this prototype, open an issue
  (no sensitive data in issues).

This is a research prototype; it makes no signoff or security guarantees.
