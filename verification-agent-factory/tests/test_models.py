"""Tests for the VerificationAgentManifest schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from verification_agent_factory.models import (
    ReleaseMode,
    VerificationAgentManifest,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _valid_data() -> dict:
    return json.loads((EXAMPLES / "spec_to_sva_manifest.json").read_text())


def test_valid_manifest_loads():
    m = VerificationAgentManifest.model_validate(_valid_data())
    assert m.agent_id == "spec-to-sva-agent"
    assert m.package_name == "spec_to_sva_agent"
    assert m.release_status is ReleaseMode.PUBLIC


def test_agent_id_must_be_kebab():
    data = _valid_data()
    data["agent_id"] = "Bad ID"
    with pytest.raises(ValidationError) as exc:
        VerificationAgentManifest.model_validate(data)
    assert "agent_id" in str(exc.value)


def test_version_must_be_semver():
    data = _valid_data()
    data["version"] = "1.0"
    with pytest.raises(ValidationError):
        VerificationAgentManifest.model_validate(data)


def test_claim_strings_reject_placeholder():
    data = _valid_data()
    data["claim_policy"]["may_claim"] = "TBD"
    with pytest.raises(ValidationError):
        VerificationAgentManifest.model_validate(data)


def test_credentials_by_default_rejected():
    data = _valid_data()
    data["security_policy"] = {"requires_credentials_by_default": True}
    with pytest.raises(ValidationError):
        VerificationAgentManifest.model_validate(data)


def test_extra_fields_forbidden():
    data = _valid_data()
    data["bogus_field"] = 1
    with pytest.raises(ValidationError):
        VerificationAgentManifest.model_validate(data)


def test_empty_inputs_rejected():
    data = _valid_data()
    data["inputs"] = []
    with pytest.raises(ValidationError):
        VerificationAgentManifest.model_validate(data)


def test_json_schema_exports():
    schema = VerificationAgentManifest.model_json_schema()
    assert schema["title"] == "VerificationAgentManifest"
    assert "agent_id" in schema["properties"]
