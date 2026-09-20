# Architecture — verification-agent-factory

## Components

| Module | Responsibility | Authority |
| --- | --- | --- |
| `models.py` | `VerificationAgentManifest` and nested contracts (Pydantic v2, strict). | Rejects invalid/overclaiming manifests. |
| `validators.py` | Load + validate manifest files; deterministic secret/proprietary audit. | Reports errors; never mutates files. |
| `docgen.py` | Deterministic manifest -> Markdown rendering. | Read-only. |
| `scaffold.py` | Brace-based template engine; writes a full sub-project. | Writes files under `--dest` only. |
| `cli.py` | Typer CLI: 6 commands. | Orchestration only. |
| `mock_llm.py` | Deterministic offline LLM stand-in. | No network. |
| `templates/` | Bundled `.tmpl` files (common, spec_to_sva, generic). | Data, not executed. |

## Typed input/output contracts

- **Input:** a `VerificationAgentManifest` (JSON or YAML). Every field validated;
  `extra="forbid"`.
- **Output of `init-agent`:** a directory tree (`ScaffoldResult`) containing an
  installable Python package, docs, tests, examples, exported schema, and CI.
- **Output of `audit-public-release`:** an `AuditReport` with blocking findings,
  warnings, and files-scanned count.

## Dataflow

```
manifest.json --> validate_manifest_file --> VerificationAgentManifest
    --> scaffold() --> render_template() over templates/ --> files on disk
                   --> render_readme() (docgen) --> README.md
                   --> model_json_schema() --> schemas/manifest.schema.json
```

## Templating engine

`render_template` performs `{{ key }}` substitution over an explicit context
dict. A missing key raises `KeyError` so a broken template fails loudly rather
than shipping a literal placeholder. There is no code execution in templates and
no external template dependency.

## Authority boundary

The factory generates scaffolding. It does not run formal tools, modify RTL, or
make verification claims. Generated agents inherit the safety rules encoded in
their manifest (claims policy, prohibited actions, human-approval gates).

## Category templates

Only `sva_generation` (spec-to-SVA) ships a full working domain core. All other
categories reuse the common skeleton plus a generic deterministic core that is
explicitly marked TODO in the generated code. Adding a new template = adding a
`templates/<name>/` directory and a branch in `scaffold.scaffold`.
