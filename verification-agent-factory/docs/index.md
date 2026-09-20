# verification-agent-factory docs

See the top-level `README.md` for scope, install, quickstart, and non-claims;
`ARCHITECTURE.md` for components and contracts; `THREAT_MODEL.md` for safety
risks and mitigations; and `EVIDENCE.md` for claim-to-test traceability.

## CLI reference

| Command | Purpose |
| --- | --- |
| `vaf init-agent <manifest> --dest <dir>` | Scaffold a new agent repo. |
| `vaf validate-manifest <manifest>` | Validate a manifest; structured errors. |
| `vaf generate-schema [--out f]` | Export the manifest JSON Schema. |
| `vaf generate-docs <manifest> [--out f]` | Render manifest -> README sections. |
| `vaf audit-public-release <dir> [-m marker]` | Scan for secrets / proprietary markers. |
| `vaf run-mock-demo [--seed n]` | Exercise the deterministic mock LLM adapter. |
