"""Tests for the Makefile extractor - real command recovery + evidence."""

from __future__ import annotations

from tb_recovery.extractors import extract_makefile
from tb_recovery.models import Provenance, TargetPhase

MK = """\
TOP := counter
FILELIST := rtl/counter.f
BUILD := build

.PHONY: build run clean

build: $(FILELIST)
\tverilator --binary -f $(FILELIST) --top-module $(TOP) -o $(TOP)_sim

run: build
\t./$(BUILD)/$(TOP)_sim

clean:
\trm -rf $(BUILD)
"""


def test_recovers_recipe_commands_with_variable_expansion():
    res = extract_makefile("Makefile", MK)
    cmds = {c.command for c in res.commands}
    # $(FILELIST), $(TOP), $(BUILD) must be expanded from the assignments.
    assert "verilator --binary -f rtl/counter.f --top-module counter -o counter_sim" in cmds
    assert "./build/counter_sim" in cmds
    assert "rm -rf build" in cmds


def test_synthesizes_make_target_invocations():
    res = extract_makefile("Makefile", MK)
    cmds = {c.command for c in res.commands}
    assert "make build" in cmds
    assert "make run" in cmds
    assert "make clean" in cmds


def test_every_command_is_extracted_with_evidence():
    res = extract_makefile("Makefile", MK)
    for c in res.commands:
        assert c.provenance is Provenance.EXTRACTED
        assert c.evidence, f"{c.command} has no evidence"
        ev = c.evidence[0]
        assert ev.file == "Makefile"
        assert ev.line >= 1


def test_clean_is_flagged_destructive():
    res = extract_makefile("Makefile", MK)
    clean = [c for c in res.commands if c.command == "rm -rf build"]
    assert clean and clean[0].destructive is True
    assert clean[0].phase is TargetPhase.CLEAN


def test_phase_classification():
    res = extract_makefile("Makefile", MK)
    by_cmd = {c.command: c for c in res.commands}
    assert by_cmd["make build"].phase is TargetPhase.BUILD
    assert by_cmd["./build/counter_sim"].phase is TargetPhase.RUN


def test_tool_requirements_detected():
    res = extract_makefile("Makefile", MK)
    names = {t.name for t in res.tools}
    assert "verilator" in names


def test_unexpanded_include_becomes_issue():
    mk = "include common.mk\n\nbuild:\n\techo hi\n"
    res = extract_makefile("Makefile", mk)
    assert any("include" in i.message for i in res.issues)
