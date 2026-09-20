"""Tests for manifest validation loading and the public-release audit."""

from __future__ import annotations

from pathlib import Path

from verification_agent_factory.validators import (
    audit_public_release,
    validate_manifest_file,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_valid_manifest_file():
    result = validate_manifest_file(EXAMPLES / "spec_to_sva_manifest.json")
    assert result.ok
    assert result.manifest is not None


def test_invalid_overclaim_manifest():
    result = validate_manifest_file(EXAMPLES / "invalid_manifest_overclaim.json")
    assert not result.ok
    joined = "\n".join(result.errors)
    assert "agent_id" in joined  # kebab-case failure surfaced


def test_invalid_credentials_manifest():
    result = validate_manifest_file(EXAMPLES / "invalid_manifest_default_credentials.json")
    assert not result.ok
    assert any("credential" in e for e in result.errors)


def test_audit_detects_secret(tmp_path: Path):
    (tmp_path / "leak.py").write_text('password = "hunter2secret"\n', encoding="utf-8")  # audit: allow
    report = audit_public_release(tmp_path)
    assert not report.clean
    assert any(f.rule == "generic_secret_assignment" for f in report.blocking)


def test_audit_detects_aws_key(tmp_path: Path):
    (tmp_path / "conf.txt").write_text("key=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")  # audit: allow
    report = audit_public_release(tmp_path)
    assert any(f.rule == "aws_access_key" for f in report.blocking)


def test_audit_detects_proprietary_marker(tmp_path: Path):
    (tmp_path / "doc.md").write_text("Internal AcmeCorp RTL details.\n", encoding="utf-8")
    report = audit_public_release(tmp_path, proprietary_markers=["AcmeCorp"])
    assert not report.clean
    assert any("AcmeCorp" in f.rule for f in report.blocking)


def test_audit_clean_dir(tmp_path: Path):
    (tmp_path / "ok.py").write_text("x = 1  # nothing sensitive here\n", encoding="utf-8")
    report = audit_public_release(tmp_path)
    assert report.clean


def test_audit_allow_pragma(tmp_path: Path):
    (tmp_path / "fixture.py").write_text(
        'secret = "planted-but-allowed"  # audit: allow\n', encoding="utf-8"
    )
    report = audit_public_release(tmp_path)
    assert report.clean


def test_audit_allows_example_email(tmp_path: Path):
    (tmp_path / "readme.md").write_text("contact user@example.com\n", encoding="utf-8")
    report = audit_public_release(tmp_path)
    # example.com is allowlisted -> no warning finding for it
    assert not any(f.rule == "email_address" for f in report.warnings)
