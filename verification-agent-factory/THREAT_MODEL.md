# Threat model — verification-agent-factory

## Hallucination / overclaiming
Risk: a generated agent claims more than it can substantiate.
Mitigation: `VerificationAgentManifest` forces explicit "may claim / must not
claim / passing means / timeout means / human review when" strings and rejects
placeholders. `generate-docs` surfaces these in every generated README.

## Unsafe assumptions
Risk: an agent silently reclassifies a design guarantee as an environment
assumption, or requires credentials by default.
Mitigation: the schema rejects `requires_credentials_by_default: true` and
requires non-empty `prohibited_actions` and `required_human_approvals`.

## Data leakage
Risk: secrets, employer/customer names, internal hostnames, or proprietary paths
committed to a public repo.
Mitigation: `audit-public-release` performs a real regex scan for AWS keys, PEM
private keys, GitHub/Slack tokens, hard-coded secret assignments, private git
URLs, internal hostnames, emails, and caller-supplied proprietary markers.
Blocking findings cause a non-zero exit.

## Reproducibility
Risk: non-deterministic generation or agent behaviour.
Mitigation: template rendering and doc generation are deterministic; the mock LLM
adapter is deterministic (same prompt + seed -> same output) and offline.
Generated agents record provenance (input hashes, seed, tool/model version).

## Result-classification
Risk: treating TIMEOUT / ERROR / UNKNOWN as PASS.
Mitigation: the generated `ResultStatus` enum separates `PASS` from
`PROPERTY_COMPILED`, `TIMEOUT`, `ERROR`, and `UNKNOWN`. The spec-to-SVA core
never returns `PASS` from static checks alone.

## Supply chain
Risk: template injection.
Mitigation: templates are inert data; rendering is pure string substitution with
no `eval`/`exec` and no arbitrary key access.
