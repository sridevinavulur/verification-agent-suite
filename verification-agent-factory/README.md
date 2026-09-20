# verification-agent-factory

Generator for research-grade, verification-integrated agent repositories.
Given a strict manifest describing a hardware-verification agent, the factory
scaffolds a complete, installable Python sub-project with consistent engineering,
safety, and evidence standards.

Public, non-proprietary tooling only. This project does **not** perform formal
verification itself; it generates the scaffolding for agents that do bounded,
human-reviewed verification work.

## Scope (this iteration)

Per prompt pack sections 4.1 / 4.2 and the shared BUILD_STANDARD, this iteration
implements:

- `VerificationAgentManifest` — the full strict Pydantic v2 schema (section 4.2),
  including the mandated explicit claim strings.
- CLI commands:
  - `init-agent` — scaffold a new agent repo from a manifest (real, installable).
  - `validate-manifest` — validate a manifest and report structured errors.
  - `generate-schema` — export the manifest JSON Schema.
  - `generate-docs` — render the manifest into README/Markdown sections.
  - `audit-public-release` — grep a tree for secrets / proprietary markers.
  - `run-mock-demo` — exercise the deterministic mock LLM adapter.
- One real, working generated template: the **spec-to-SVA agent**
  (`sva_generation`). Its generated core actually parses a typed temporal intent,
  grounds every signal against an RTL symbol table, renders a candidate SVA, and
  statically validates it.

Other categories generate a common skeleton plus a generic deterministic core
(clearly marked TODO in the generated code). The templating engine and the one
spec-to-SVA template genuinely work.

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# 1. Validate the bundled example manifest
vaf validate-manifest examples/spec_to_sva_manifest.json

# 2. Scaffold a new agent repository from it
vaf init-agent examples/spec_to_sva_manifest.json --dest /tmp/spec-to-sva-agent

# 3. Audit the generated tree for secrets / proprietary names
vaf audit-public-release /tmp/spec-to-sva-agent

# 4. The generated project is installable and runs:
cd /tmp/spec-to-sva-agent
pip install -e .
spec-to-sva-agent generate examples/requirement_handshake.json examples/rtl_symbols.json
```

`vaf` and `verification-agent-factory` are aliases for the same CLI.

## Safety / non-claims

- The factory does not claim commercial EDA-tool development or formal signoff.
- Generated agents render **candidate** properties; syntax acceptance is
  reported as `PROPERTY_COMPILED`, never as a semantic `PASS`.
- A timeout / error / unknown is never classified as a pass.
- LLM proposes; deterministic tools validate. The mock LLM adapter is
  deterministic and offline by default.
- No secrets, employer/customer names, or proprietary paths are committed;
  `audit-public-release` enforces this.

## Limitations

- Only the spec-to-SVA template emits a full working domain core in this
  iteration. Other categories are generic skeletons with documented TODOs.
- The spec-to-SVA renderer supports bounded-response implication properties only.
- No formal or simulation backend is integrated; validation is static-only.

## Repository layout

```
verification-agent-factory/
  src/verification_agent_factory/
    models.py        # VerificationAgentManifest (section 4.2)
    validators.py    # manifest loading + public-release audit
    docgen.py        # manifest -> Markdown
    scaffold.py      # templating engine
    cli.py           # Typer CLI (6 commands)
    mock_llm.py      # deterministic mock adapter
    templates/       # bundled templates (common + spec_to_sva + generic)
  examples/          # valid + invalid example manifests
  schemas/           # exported JSON Schema
  tests/             # pytest suite
  docs/
```

See `ARCHITECTURE.md`, `THREAT_MODEL.md`, and `EVIDENCE.md` for details.
