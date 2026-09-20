"""Tests for the scaffolding engine and the generated spec-to-SVA project."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from verification_agent_factory.models import VerificationAgentManifest
from verification_agent_factory.scaffold import render_template, scaffold

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _manifest() -> VerificationAgentManifest:
    return VerificationAgentManifest.model_validate(
        json.loads((EXAMPLES / "spec_to_sva_manifest.json").read_text())
    )


def test_render_template_substitutes():
    assert render_template("hi {{ name }}", {"name": "there"}) == "hi there"


def test_render_template_missing_key_raises():
    with pytest.raises(KeyError):
        render_template("{{ missing }}", {})


def test_scaffold_writes_expected_files(tmp_path: Path):
    result = scaffold(_manifest(), tmp_path / "out")
    names = {f.relative_to(result.root).as_posix() for f in result.files}
    required = {
        "README.md",
        "ARCHITECTURE.md",
        "THREAT_MODEL.md",
        "EVIDENCE.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE",
        ".gitignore",
        "pyproject.toml",
        "Dockerfile",
        "agent_manifest.json",
        "schemas/manifest.schema.json",
        ".github/workflows/ci.yml",
        "src/spec_to_sva_agent/models.py",
        "src/spec_to_sva_agent/cli.py",
        "src/spec_to_sva_agent/agent.py",
        "src/spec_to_sva_agent/validators.py",
        "tests/test_agent.py",
    }
    missing = required - names
    assert not missing, f"missing generated files: {missing}"


def test_scaffold_refuses_nonempty(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "keep.txt").write_text("x")
    with pytest.raises(FileExistsError):
        scaffold(_manifest(), dest)


def test_no_unrendered_placeholders(tmp_path: Path):
    # Match the engine's own placeholder grammar: {{ identifier }}. A bare "{{"
    # (e.g. inside a generated string literal that checks for placeholders) is
    # legitimate and must not trip this test.
    import re

    placeholder = re.compile(r"\{\{\s*[a-zA-Z0-9_]+\s*\}\}")
    result = scaffold(_manifest(), tmp_path / "out")
    for f in result.files:
        if f.suffix in {".py", ".toml", ".md", ".json", ".yml"}:
            text = f.read_text(encoding="utf-8")
            assert not placeholder.search(text), f"unrendered placeholder in {f}"


def test_generated_project_is_ruff_clean(tmp_path: Path):
    """The generated project must itself pass ruff (definition of done)."""
    import shutil

    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not on PATH")
    result = scaffold(_manifest(), tmp_path / "out")
    proc = subprocess.run(
        [ruff, "check", "."], cwd=result.root, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_generated_project_is_importable_and_runs(tmp_path: Path):
    """The generated package must import and produce the golden SVA render.

    We import it in a subprocess with the generated src/ on the path, so the
    test exercises the real generated code end-to-end without a pip install.
    """
    result = scaffold(_manifest(), tmp_path / "out")
    src = result.root / "src"
    script = (
        "import json;"
        "from spec_to_sva_agent.agent import TemporalIntent, generate_candidate;"
        "from spec_to_sva_agent.models import SymbolTable, ResultStatus;"
        "t=SymbolTable(design_top='h',clock_candidates=['clk'],reset_candidates=['rst_n'],"
        "symbols=[{'name':'clk'},{'name':'rst_n'},{'name':'req'},{'name':'gnt'}]);"
        "i=TemporalIntent(requirement_id='R1',source_text='x',property_name='p',"
        "clock_signal='clk',reset_signal='rst_n',reset_active_high=False,"
        "antecedent='req',consequent='gnt',min_delay=1,max_delay=3,"
        "referenced_signals=['req','gnt']);"
        "c=generate_candidate(i,t,seed=0);"
        "print(c.status.value);print(c.sva_text)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=src,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "PROPERTY_COMPILED" in out
    assert "req |-> ##[1:3] gnt;" in out
