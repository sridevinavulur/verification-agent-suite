"""Tests for the manifest -> Markdown generator."""

from __future__ import annotations

import json
from pathlib import Path

from verification_agent_factory.docgen import render_claims_section, render_readme
from verification_agent_factory.models import VerificationAgentManifest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _manifest() -> VerificationAgentManifest:
    return VerificationAgentManifest.model_validate(
        json.loads((EXAMPLES / "spec_to_sva_manifest.json").read_text())
    )


def test_claims_section_has_mandated_strings():
    text = render_claims_section(_manifest())
    for phrase in [
        "This agent may claim",
        "This agent must not claim",
        "A passing result means",
        "A timeout or unknown result means",
        "Human review is required when",
    ]:
        assert phrase in text


def test_readme_contains_title_and_limitations():
    text = render_readme(_manifest())
    assert "# Spec-to-SVA Agent" in text
    assert "Known limitations and non-claims" in text
    assert "Authority boundary" in text


def test_readme_deterministic():
    a = render_readme(_manifest())
    b = render_readme(_manifest())
    assert a == b
