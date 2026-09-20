# Security & Data Policy

## Data policy (public-only)

This repository and any output committed from it must contain **public,
non-proprietary content only**. Do **not** commit:

- proprietary or customer/employer RTL, or manifests derived from it
- customer, employer, partner, or internal project names
- internal tool names, hostnames, usernames, or private filesystem paths
- credentials, tokens, API keys, or certificates
- non-redistributable EDA tool output or documentation

The bundled `examples/` are original generic toy RTL and are safe to publish.

## What the tool records

Provenance stores input-file **SHA-256 hashes and basenames**, the tool/schema
version, and the command string — not file contents. Note that a generated
manifest still contains **signal names and source file:line locations** from the
RTL you point it at. If you run the tool on non-public RTL, the resulting
manifest is not public-safe; do not commit it.

## Before publishing

Run a release audit (secret scan, name/path scan, license check) on anything you
intend to push, especially generated manifests. See the release-audit prompt in
the team prompt pack.

## Reporting

This is a research prototype. Report issues via the repository's issue tracker.
Do not include proprietary data in a report.
