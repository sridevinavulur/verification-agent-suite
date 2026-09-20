# Evidence — verification-agent-factory

Each claim is tied to a source location, a test, and a reproduce command. This is
implementation evidence, not experimental-performance evidence.

| ID | Claim | Source | Test | Reproduce |
| --- | --- | --- | --- | --- |
| C1 | `VerificationAgentManifest` validates the full section-4.2 field set and rejects invalid manifests. | `src/verification_agent_factory/models.py` | `tests/test_models.py` | `pytest tests/test_models.py` |
| C2 | Invalid example manifests are caught with structured errors. | `src/verification_agent_factory/validators.py::validate_manifest_file` | `tests/test_validators.py::test_invalid_overclaim_manifest`, `::test_invalid_credentials_manifest` | `pytest tests/test_validators.py` |
| C3 | `audit-public-release` actually greps for secrets and proprietary markers. | `src/verification_agent_factory/validators.py::audit_public_release` | `tests/test_validators.py::test_audit_detects_*` | `pytest -k audit` |
| C4 | `init-agent` writes a real, importable, runnable sub-project. | `src/verification_agent_factory/scaffold.py` | `tests/test_scaffold.py::test_generated_project_is_importable_and_runs` | `pytest tests/test_scaffold.py` |
| C5 | The spec-to-SVA template renders a deterministic golden SVA and rejects ungrounded signals. | generated `agent.py` / `validators.py` (from `templates/spec_to_sva/`) | `tests/test_scaffold.py` (subprocess) + generated `tests/test_agent.py` | see C4 |
| C6 | `generate-schema` and `generate-docs` produce the JSON Schema and manifest-derived README. | `cli.py`, `docgen.py` | `tests/test_cli.py`, `tests/test_docgen.py` | `pytest tests/test_cli.py tests/test_docgen.py` |
| C7 | The mock LLM adapter is deterministic and offline. | `src/verification_agent_factory/mock_llm.py` | `tests/test_cli.py::test_run_mock_demo_deterministic` | `pytest -k mock_demo` |

Tool/model version: mock LLM `mock-llm-deterministic-v1`. Release tag: `TBD-placeholder`.

## Non-claims
No formal verification is performed. No commercial EDA tool is developed. Generated
agents produce candidate artifacts only, pending human review and independent validation.
