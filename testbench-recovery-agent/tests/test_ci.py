"""Tests for the GitHub Actions CI workflow extractor."""

from __future__ import annotations

from tb_recovery.extractors import extract_ci_workflow
from tb_recovery.models import Provenance

CI = """\
name: sim
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: deps
        run: |
          sudo apt-get install -y verilator
          pip install cocotb pytest
      - name: run
        run: make run
      - name: templated
        run: ${{ steps.x.outputs.cmd }}
"""


def test_recovers_run_steps_with_line_evidence():
    res = extract_ci_workflow(".github/workflows/ci.yml", CI)
    cmds = {c.command: c for c in res.commands}
    assert "make run" in cmds
    assert "sudo apt-get install -y verilator" in cmds
    ev = cmds["make run"].evidence[0]
    assert ev.file == ".github/workflows/ci.yml"
    # The evidence line must actually contain the recovered command.
    assert "make run" in CI.splitlines()[ev.line - 1]


def test_all_ci_commands_extracted():
    res = extract_ci_workflow(".github/workflows/ci.yml", CI)
    for c in res.commands:
        assert c.provenance is Provenance.EXTRACTED
        assert c.evidence


def test_recovers_pip_and_apt_dependencies():
    res = extract_ci_workflow(".github/workflows/ci.yml", CI)
    pip = {d.name for d in res.dependencies if d.manager == "pip"}
    apt = {d.name for d in res.dependencies if d.manager == "apt"}
    assert {"cocotb", "pytest"} <= pip
    assert "verilator" in apt


def test_setup_python_action_adds_python_tool():
    res = extract_ci_workflow(".github/workflows/ci.yml", CI)
    assert any(t.name == "python" for t in res.tools)


def test_fully_templated_step_is_flagged_not_guessed():
    res = extract_ci_workflow(".github/workflows/ci.yml", CI)
    assert all("${{" not in c.command for c in res.commands)
    assert any("templated" in i.message for i in res.issues)


def test_bad_yaml_becomes_warning():
    res = extract_ci_workflow(".github/workflows/ci.yml", "jobs: [unclosed\n")
    assert any(i.severity.value == "warning" for i in res.issues)
