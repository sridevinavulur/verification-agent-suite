# Evidence

Each capability is tied to the source, the test that proves it, and a command to
reproduce. Run tests from the repo root in the venv (`pytest`).

| Claim | Source | Test | Reproduce |
| --- | --- | --- | --- |
| Requirements decompose into verifiable features | `engine.decompose` | `test_engine.py::test_decompose_assigns_ids_and_categories` | `pytest tests/test_engine.py -k decompose` |
| Items classified into 8 categories | `engine.classify_requirement`, `Category` | `test_engine.py::test_classification_precedence` | `pytest tests/test_engine.py -k classification` |
| Techniques proposed per category (incl. formal for security) | `engine._CATEGORY_TECHNIQUES` | `test_engine.py::test_security_gets_formal_technique` | `pytest tests/test_engine.py -k formal` |
| Plan items are risk-ranked | `engine._risk_for_feature`, `build_plan` sort | `test_engine.py::test_risk_ranked_descending`, `::test_manifest_state_heavy_raises_functional_risk` | `pytest tests/test_engine.py -k risk` |
| Missing reset/CDC requirements flagged from manifest | `engine.find_ambiguities` | `test_engine.py::test_missing_reset_and_cdc_requirements_detected` | `pytest tests/test_engine.py -k missing` |
| Unverifiable requirement flagged (no `fifo`→`if` false negative) | `engine.find_ambiguities`, `_VERIFIABILITY_WORDS` | `test_engine.py::test_unverifiable_requirement_flagged_not_false_positive_on_fifo` | `pytest tests/test_engine.py -k unverifiable` |
| Unreferenced signals surfaced as assumptions | `engine.find_ambiguities` | `test_engine.py::test_unreferenced_signal_becomes_assumption` | `pytest tests/test_engine.py -k assumption` |
| Requirement→tests→coverage traceability matrix | `engine.build_traceability` | `test_engine.py::test_traceability_covered_flag` | `pytest tests/test_engine.py -k traceability` |
| Canonical RTL Intent Manifest consumed by its real field names | `ingest.project_manifest` | `test_ingest.py::test_project_manifest_uses_canonical_fields`, `::test_bundled_manifest_conforms_to_canonical_schema` | `pytest tests/test_ingest.py` |
| Agent never self-approves; proposed vs approved distinguished | `models.ApprovalState`, `engine.build_plan` | `test_approval.py::test_agent_never_emits_approved` | `pytest tests/test_approval.py -k never` |
| Human decisions promote/reject; deep-copy, no clobber | `approval.apply_decisions` | `test_approval.py::test_apply_decisions_promotes_and_rejects`, `::test_already_decided_item_not_reapplied` | `pytest tests/test_approval.py` |
| Typed contracts validate (extra forbidden, bounds) | `models._Strict`, `PlanItem.risk_score` | `test_models.py::test_extra_fields_forbidden`, `::test_risk_score_bounds_enforced` | `pytest tests/test_models.py` |
| Deterministic golden Markdown + JSON | `report.render_markdown`, `serialize.plan_to_json` | `test_golden.py` | `pytest tests/test_golden.py` |
| CLI runs end-to-end (plan/report/approve/schema) | `cli.py` | `test_cli.py` | `pytest tests/test_cli.py` |
| Only offline mock LLM; non-mock refused | `llm.get_adapter` | `test_cli.py::test_cli_rejects_non_mock_llm` | `pytest tests/test_cli.py -k mock` |

## Manual reproduction

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
vplan plan -s examples/fifo_spec.json -i examples/fifo_interface.json \
  -m examples/fifo_manifest.json -e examples/fifo_existing_testplan.json \
  -o /tmp/plan.json --markdown /tmp/plan.md
vplan approve /tmp/plan.json -d examples/fifo_decisions.json -o /tmp/plan.approved.json
```

Golden artifacts: `examples/expected/{fifo,gpio}_plan.{json,md}`,
`examples/expected/fifo_plan.approved.{json,md}`.
