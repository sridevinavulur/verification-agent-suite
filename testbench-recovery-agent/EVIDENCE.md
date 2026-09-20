# Evidence

Each claim below is tied to source code, a test, and a command to reproduce.
Run from the repo root inside the dev venv (`pip install -e ".[dev]"`).

Distinguish **implementation evidence** (the code does X, verified by tests)
from **experimental-performance evidence** (none is claimed - this is a static
tool with deterministic output, not a benchmarked system).

---

### CLAIM-1: Recovers real build/run commands from Makefiles with file+line evidence
- **Text:** The Makefile extractor recovers recipe commands (with `$(VAR)`
  expansion), synthesizes `make <target>` invocations, and attaches evidence.
- **Code:** `src/tb_recovery/extractors/makefile.py` (`extract_makefile`).
- **Tests:** `tests/test_makefile.py::test_recovers_recipe_commands_with_variable_expansion`,
  `::test_synthesizes_make_target_invocations`,
  `::test_every_command_is_extracted_with_evidence`.
- **Reproduce:** `pytest tests/test_makefile.py -q`
- **Limitations:** no conditionals/pattern-rules/`include` following.

### CLAIM-2: Recovers CI (GitHub Actions) run steps with accurate line numbers
- **Text:** The CI extractor parses `run:`/`uses:` steps and points evidence at
  the exact workflow line; fully-templated steps are flagged, not guessed.
- **Code:** `src/tb_recovery/extractors/ci.py` (`extract_ci_workflow`).
- **Tests:** `tests/test_ci.py::test_recovers_run_steps_with_line_evidence`,
  `::test_fully_templated_step_is_flagged_not_guessed`,
  `::test_recovers_pip_and_apt_dependencies`.
- **Reproduce:** `pytest tests/test_ci.py -q`

### CLAIM-3: Recovers sources from `.f` file lists and shell/README commands
- **Text:** The filelist, shell, and README extractors recover source files,
  tool-bearing shell lines, and documented commands respectively.
- **Code:** `extractors/filelist.py`, `extractors/shell.py`, `extractors/readme.py`.
- **Tests:** `tests/test_shell_filelist_readme.py` (11 tests).
- **Reproduce:** `pytest tests/test_shell_filelist_readme.py -q`

### CLAIM-4: EXTRACTED vs HYPOTHESIS provenance is enforced and never conflated
- **Text:** Extracted commands always carry evidence; hypotheses carry a
  rationale and empty evidence, and are selectable/excludable by provenance.
- **Code:** `models.py` (`Provenance`, `CandidateCommand`),
  `recover.py` (`_hypotheses`).
- **Tests:** `tests/test_recover.py::test_python_project_without_install_hypothesizes`,
  `tests/test_cli_models_sandbox.py::test_extracted_command_requires_evidence_semantics`.
- **Reproduce:** `pytest tests/test_recover.py::test_python_project_without_install_hypothesizes -q`

### CLAIM-5: End-to-end recovery on the bundled fixture matches a committed golden
- **Text:** Running the tool on `examples/toy_repo` produces a deterministic
  report that matches the golden byte-for-byte and round-trips through the model.
- **Code:** `recover.py`, `serialize.py`.
- **Tests:** `tests/test_golden.py` (3 tests).
- **Reproduce:** `pytest tests/test_golden.py -q`
- **Golden:** `tests/golden/toy_repo.json`; regenerate with
  `python tests/regenerate_golden.py`.

### CLAIM-6: Recommends a non-destructive, evidence-backed smoke test
- **Text:** The smoke-test selector excludes destructive/clean/setup commands
  and prefers CI/Makefile evidence over documentation.
- **Code:** `recover.py` (`_select_smoke_test`, `is_destructive`).
- **Tests:** `tests/test_recover.py::test_smoke_test_is_nondestructive_and_extracted`.
- **Reproduce:** `tb-recover smoke examples/toy_repo`
- **Expected:** on the fixture, `make run` (EXTRACTED from CI).

### CLAIM-7: Never executes recovered commands (static only)
- **Text:** The optional execution adapter is a disabled Phase-2 stub.
- **Code:** `src/tb_recovery/sandbox.py` (`DisabledExecutor`).
- **Tests:** `tests/test_cli_models_sandbox.py::test_sandbox_refuses_to_execute`.
- **Reproduce:** `pytest tests/test_cli_models_sandbox.py::test_sandbox_refuses_to_execute -q`

### CLAIM-8: Flags unresolved setup issues (missing sources, etc.)
- **Text:** Targets referencing sources absent on disk produce WARNING issues.
- **Code:** `recover.py` (`_unresolved_source_issues`).
- **Tests:** `tests/test_recover.py::test_missing_source_produces_setup_issue`.
- **Reproduce:** `pytest tests/test_recover.py::test_missing_source_produces_setup_issue -q`

---

## Environment
- Tool version: `tb_recovery.__version__` = 0.1.0
- Python: 3.11+ (developed/verified on 3.13)
- Deps: pydantic v2, typer, PyYAML (see `pyproject.toml`)
- Full suite: `pytest -q` (42 tests). Lint: `ruff check .`. Types: `mypy src/tb_recovery`.
