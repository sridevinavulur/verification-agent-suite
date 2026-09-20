"""Repository scaffolding engine.

Given a validated :class:`VerificationAgentManifest`, :func:`scaffold` writes a
complete, installable sub-project to disk. The generated project:

- is a real Python package (``pip install -e .`` works),
- ships a Typer CLI, Pydantic models, a deterministic agent core, tests,
  examples, an exported JSON Schema, and CI,
- embeds the manifest and manifest-derived docs.

The templating engine is a small, safe, brace-based renderer (``{{ key }}``) over
an explicit context dict. There is no arbitrary code execution and no external
template dependency, so the factory has zero runtime template deps.

Only one full category template is implemented in this iteration: **spec-to-SVA**
(``sva_generation``). Other categories reuse the common skeleton plus a generic
agent core; the spec-to-SVA template additionally emits a real, working
requirement-to-SVA renderer so the generated project is meaningful, not a stub.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from . import __version__
from .docgen import render_readme
from .models import AgentCategory, VerificationAgentManifest

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(text: str, context: dict[str, str]) -> str:
    """Render ``{{ key }}`` placeholders from ``context``.

    Raises ``KeyError`` if a placeholder has no value, so a broken template fails
    loudly instead of emitting literal ``{{ ... }}`` into a shipped file.
    """

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"template variable '{key}' is not defined in context")
        return context[key]

    return _VAR_RE.sub(repl, text)


def _read_template(name: str) -> str:
    """Read a bundled template file from the package's ``templates`` dir."""
    base = resources.files("verification_agent_factory").joinpath("templates")
    return base.joinpath(name).read_text(encoding="utf-8")


@dataclass
class ScaffoldResult:
    """What was written."""

    root: Path
    files: list[Path]


MIT_LICENSE = """MIT License

Copyright (c) {{ year }} {{ owner_role }}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _build_context(m: VerificationAgentManifest) -> dict[str, str]:
    return {
        "agent_id": m.agent_id,
        "package_name": m.package_name,
        "display_name": m.display_name,
        "version": m.version,
        "mission": m.mission,
        "category": m.category.value,
        "owner_role": m.owner_role,
        "license": m.license,
        "year": str(datetime.now(UTC).year),
        "factory_version": __version__,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _write(path: Path, content: str, written: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(path)


def scaffold(
    manifest: VerificationAgentManifest,
    dest: Path,
    *,
    overwrite: bool = False,
) -> ScaffoldResult:
    """Write a complete agent sub-project rooted at ``dest``.

    ``dest`` is created if it does not exist. If it exists and is non-empty,
    ``overwrite`` must be True or a ``FileExistsError`` is raised.
    """
    dest = dest.resolve()
    if dest.exists() and any(dest.iterdir()) and not overwrite:
        raise FileExistsError(
            f"destination {dest} is not empty (use overwrite=True to replace)"
        )

    ctx = _build_context(manifest)
    pkg = manifest.package_name
    written: list[Path] = []

    def rendered(rel: str, tmpl: str) -> None:
        """Render a template file and write it to ``dest / rel``."""
        _write(dest / rel, render_template(_read_template(tmpl), ctx), written)

    def verbatim(rel: str, tmpl: str) -> None:
        """Copy a template file verbatim (no substitution) to ``dest / rel``."""
        _write(dest / rel, _read_template(tmpl), written)

    def raw(rel: str, content: str) -> None:
        _write(dest / rel, content, written)

    # --- top-level metadata & docs ----------------------------------------
    raw("README.md", render_readme(manifest))
    raw(
        "LICENSE",
        render_template(MIT_LICENSE, ctx)
        if manifest.license.upper() == "MIT"
        else f"{manifest.license} license — see project owner.\n",
    )
    rendered("ARCHITECTURE.md", "ARCHITECTURE.md.tmpl")
    rendered("THREAT_MODEL.md", "THREAT_MODEL.md.tmpl")
    rendered("EVIDENCE.md", "EVIDENCE.md.tmpl")
    rendered("CONTRIBUTING.md", "CONTRIBUTING.md.tmpl")
    rendered("SECURITY.md", "SECURITY.md.tmpl")
    rendered("RELEASE_CHECKLIST.md", "RELEASE_CHECKLIST.md.tmpl")
    verbatim(".gitignore", "gitignore.tmpl")
    rendered("Dockerfile", "Dockerfile.tmpl")
    rendered("pyproject.toml", "pyproject.toml.tmpl")
    rendered(".github/workflows/ci.yml", "ci.yml.tmpl")

    # --- embedded manifest + schema + benchmark ---------------------------
    manifest_json = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
    raw("agent_manifest.json", manifest_json + "\n")
    schema_json = json.dumps(
        VerificationAgentManifest.model_json_schema(), indent=2, sort_keys=True
    )
    raw("schemas/manifest.schema.json", schema_json + "\n")
    bench_json = json.dumps(
        manifest.benchmark_manifest.model_dump(mode="json"), indent=2, sort_keys=True
    )
    raw("benchmark_manifest.json", bench_json + "\n")

    # --- python package ---------------------------------------------------
    src = f"src/{pkg}"
    rendered(f"{src}/__init__.py", "pkg_init.py.tmpl")
    rendered(f"{src}/models.py", "pkg_models.py.tmpl")
    verbatim(f"{src}/mock_llm.py", "pkg_mock_llm.py.tmpl")

    # Category-specific agent core. Only spec-to-SVA has a real generator core;
    # everything else gets the generic deterministic core.
    if manifest.category == AgentCategory.SVA_GENERATION:
        rendered(f"{src}/agent.py", "spec_to_sva/agent.py.tmpl")
        verbatim(f"{src}/validators.py", "spec_to_sva/validators.py.tmpl")
        rendered(f"{src}/cli.py", "spec_to_sva/cli.py.tmpl")
        verbatim("examples/requirement_handshake.json", "spec_to_sva/example_requirement.json.tmpl")
        verbatim("examples/rtl_symbols.json", "spec_to_sva/example_symbols.json.tmpl")
        raw("tests/__init__.py", "")
        rendered("tests/test_agent.py", "spec_to_sva/test_agent.py.tmpl")
        rendered("tests/test_models.py", "spec_to_sva/test_models.py.tmpl")
    else:
        rendered(f"{src}/agent.py", "generic/agent.py.tmpl")
        verbatim(f"{src}/validators.py", "generic/validators.py.tmpl")
        rendered(f"{src}/cli.py", "generic/cli.py.tmpl")
        verbatim("examples/input_example.json", "generic/example_input.json.tmpl")
        raw("tests/__init__.py", "")
        rendered("tests/test_agent.py", "generic/test_agent.py.tmpl")

    rendered("docs/index.md", "docs_index.md.tmpl")

    return ScaffoldResult(root=dest, files=written)
