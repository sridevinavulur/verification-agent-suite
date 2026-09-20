# Security policy — verification-agent-factory

## Reporting
Report suspected vulnerabilities privately to the project owner. Do not open a
public issue for security-sensitive reports.

## Data policy
- Public, non-proprietary inputs only.
- No credentials are required by default; CI runs with no secrets.
- Never commit: API keys, tokens, passwords, certificates, employer/customer/
  partner names, proprietary RTL/logs/waveforms, internal hostnames, usernames,
  or filesystem paths.

## Release
Run `vaf audit-public-release .` before every public push. See RELEASE_CHECKLIST.md.
