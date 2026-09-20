# Security & Safe-Use Notes

This tool performs a **heuristic structural triage** and must not be used as a
CDC/RDC signoff authority. See `THREAT_MODEL.md` for the full analysis.

## Safe use

- Treat every finding as a *review hint*, not a verdict. All findings are tagged
  `heuristic: true`.
- An empty crossing list is **not** a clean result.
- A "2-FF synchronizer candidate" is structural evidence only; it does not prove
  correct metastability handling.
- Always run a commercial CDC/RDC signoff flow for verification-quality results.

## Data handling

- No network or API calls; fully offline and deterministic.
- No secrets, credentials, or telemetry.
- The tool reads only the manifest/glossary files you pass and writes only to
  the paths you specify.
- Bundled examples are public toy designs. Do **not** commit reports or
  manifests derived from proprietary RTL (see `.gitignore`).

## Reporting issues

Open an issue in the shared team repository. Do not include proprietary RTL,
customer names, internal tool names, or paths in reports.
