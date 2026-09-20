# Security & Safety Notes

- **Read-only.** The tool never modifies SVA, RTL, the RTL Intent Manifest,
  proof scope, budgets, or signoff conclusions. All findings route to a
  human-review queue; changing an assumption is a human action taken outside
  this tool.
- **No network / no LLM calls.** All analysis is deterministic and local. Tests
  and CI run with no secrets and no external services.
- **No soundness claims.** The tool cannot and does not conclude that a proof is
  valid, that constraints are consistent, or that any result is non-vacuous. See
  `THREAT_MODEL.md`.
- **Public content only.** All bundled examples are synthetic. Do not add
  proprietary RTL/SVA, credentials, employer/customer names, or internal tool
  names. `.gitignore` excludes local report outputs.
- **Provenance.** Reports record input SHA-256 hashes and the invoking command
  for reproducibility (not file contents).

Report suspected issues via the shared team repo's normal channel.
