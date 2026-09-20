"""Tests for the shell, filelist (.f), and README extractors."""

from __future__ import annotations

from tb_recovery.extractors import (
    extract_filelist,
    extract_readme,
    extract_shell,
)
from tb_recovery.models import Provenance

# --- shell ---------------------------------------------------------------

SH = """\
#!/bin/bash
set -e
BUILD=build
pip install cocotb
iverilog -o $BUILD/tb tb/top.sv rtl/top.sv
vvp $BUILD/tb
echo "done"
"""


def test_shell_recovers_tool_commands_with_var_expansion():
    res = extract_shell("build.sh", SH)
    cmds = {c.command for c in res.commands}
    assert "iverilog -o build/tb tb/top.sv rtl/top.sv" in cmds
    assert "vvp build/tb" in cmds
    # 'echo done' is not tool-relevant and must be skipped.
    assert not any(c.command.startswith("echo") for c in res.commands)


def test_shell_recovers_pip_dependency():
    res = extract_shell("build.sh", SH)
    assert any(d.name == "cocotb" and d.manager == "pip" for d in res.dependencies)


def test_shell_commands_have_evidence():
    res = extract_shell("build.sh", SH)
    for c in res.commands:
        assert c.provenance is Provenance.EXTRACTED
        assert c.evidence and c.evidence[0].file == "build.sh"


# --- filelist ------------------------------------------------------------

FL = """\
// counter filelist
+incdir+rtl
rtl/counter.sv
tb/counter_tb.sv
-timescale 1ns/1ps
sub.f
"""


def test_filelist_recovers_sources_and_nested_filelists():
    res = extract_filelist("rtl/counter.f", FL)
    assert len(res.target_source_map) == 1
    m = res.target_source_map[0]
    assert "rtl/counter.sv" in m.sources
    assert "tb/counter_tb.sv" in m.sources
    assert "sub.f" in m.filelists
    # +incdir+ and -timescale are not sources.
    assert not any(s.startswith(("+", "-")) for s in m.sources)


def test_empty_filelist_yields_issue():
    res = extract_filelist("empty.f", "// nothing here\n+define+FOO\n")
    assert res.target_source_map == []
    assert res.issues


# --- readme --------------------------------------------------------------

README = """\
# Project

Build it:

```sh
make build
verilator --lint-only -f rtl/top.f
```

Run the sim from a prompt:

    $ vvp build/sim

Not a command:

```python
x = 1
```
"""


def test_readme_recovers_fenced_shell_commands():
    res = extract_readme("README.md", README)
    cmds = {c.command for c in res.commands}
    assert "make build" in cmds
    assert "verilator --lint-only -f rtl/top.f" in cmds


def test_readme_recovers_inline_prompt_command():
    res = extract_readme("README.md", README)
    assert any(c.command == "vvp build/sim" for c in res.commands)


def test_readme_ignores_non_shell_fences():
    res = extract_readme("README.md", README)
    assert not any(c.command == "x = 1" for c in res.commands)


def test_readme_commands_marked_extracted_with_evidence():
    res = extract_readme("README.md", README)
    for c in res.commands:
        assert c.provenance is Provenance.EXTRACTED
        assert c.evidence and c.evidence[0].source_kind.value == "readme"
